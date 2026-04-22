"""
main.py - FastAPI server for UB Time Bomb Detector.

Includes input validation, size limits, and compilation error handling.
"""

import json
import os
import shutil
import tempfile
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.core.env_loader import load_dotenv_files
from backend.core.ai import (
    GroqAPIError,
    GroqClient,
    AIExplainStatus,
    build_prompt_payload,
    load_groq_config,
    parse_ai_explanation_content,
)
from backend.core.ai.schemas import AIExplainRequest, AIExplainResponse, phase0_contract_response
from backend.core.change_detector import detect_changes
from backend.core.compile_engine import CompilationError, compile_both
from backend.core.report_generator import generate_report
from backend.core.ub_classifier import classify_diffs


app = FastAPI(
    title="UB Time Bomb Detector",
    description="Static analysis tool for detecting undefined behavior time bombs in C/C++ code",
    version="1.0.0",
)

load_dotenv_files()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_SOURCE_SIZE = 50_000
MIN_AI_PAYLOAD_LIMIT = 50_000
AI_PAYLOAD_LIMIT_MULTIPLIER = 10


class AnalyzeRequest(BaseModel):
    """Request payload for source-string analysis."""

    source_code: str = Field(...)
    filename: Optional[str] = Field(default="input.c")


class AnalyzeFileRequest(BaseModel):
    """Request payload for file-path analysis."""

    file_path: str


C_CPP_EXTENSIONS = {".c", ".cpp", ".cc", ".cxx", ".C", ".c++"}


def _estimate_ai_payload_size(request: AIExplainRequest) -> int:
    """Estimate payload size to reject oversized AI explain requests early."""

    finding_blob = json.dumps(request.finding, default=str)
    snippet_blob = request.source_snippet or ""
    return len(finding_blob) + len(snippet_blob)


def _max_ai_payload_size(config_max_chars: int) -> int:
    """Cap request payload size relative to prompt budget."""

    return max(MIN_AI_PAYLOAD_LIMIT, config_max_chars * AI_PAYLOAD_LIMIT_MULTIPLIER)


def _map_groq_error_status(exc: GroqAPIError) -> int:
    """Translate Groq client errors to stable HTTP status codes."""

    if exc.status_code in {400, 401, 403, 404, 429}:
        return exc.status_code

    lowered = str(exc).lower()
    if "timed out" in lowered:
        return 504
    if "groq_api_key" in lowered or "api key is missing" in lowered:
        return 503

    return 502


def _safe_filename(name: str | None) -> str:
    """Normalize user-supplied filename to a safe local basename."""
    fallback = "input.c"
    raw = (name or fallback).strip()
    base = os.path.basename(raw)
    if not base:
        return fallback
    _, ext = os.path.splitext(base)
    if ext not in C_CPP_EXTENSIONS:
        base = f"{base}.c"
    return base


@app.get("/health")
async def health() -> dict:
    """Liveness check endpoint."""
    return {"status": "ok"}


@app.get("/ai-explain/contract", response_model=AIExplainResponse)
async def ai_explain_contract() -> AIExplainResponse:
    """Expose the stable explanation schema for frontend integration scaffolding."""
    return phase0_contract_response()


@app.get("/ai-explain/status", response_model=AIExplainStatus)
async def ai_explain_status() -> AIExplainStatus:
    """Expose whether AI explanations are available without making the UI guess."""

    try:
        config = load_groq_config()
    except GroqAPIError as exc:
        return AIExplainStatus(enabled=False, reason=f"AI configuration error: {str(exc)}")

    if not config.enabled:
        return AIExplainStatus(
            enabled=False,
            model=config.model,
            fallback_model=config.fallback_model,
            max_chars=config.max_chars,
            reason="AI not configured. Set GROQ_API_KEY.",
        )

    return AIExplainStatus(
        enabled=True,
        model=config.model,
        fallback_model=config.fallback_model,
        max_chars=config.max_chars,
        reason="",
    )


@app.post("/ai-explain", response_model=AIExplainResponse)
async def ai_explain(request: AIExplainRequest) -> AIExplainResponse:
    """Generate a per-finding AI explanation using Groq."""

    try:
        config = load_groq_config()
    except GroqAPIError as exc:
        raise HTTPException(status_code=503, detail=f"AI configuration error: {str(exc)}") from exc

    if not config.enabled:
        raise HTTPException(status_code=503, detail="AI not configured. Set GROQ_API_KEY.")

    payload_size = _estimate_ai_payload_size(request)
    max_payload_size = _max_ai_payload_size(config.max_chars)
    if payload_size > max_payload_size:
        raise HTTPException(
            status_code=400,
            detail=f"AI explain payload exceeds size limit ({max_payload_size} chars)",
        )

    try:
        prompt_payload = build_prompt_payload(
            request.finding,
            source_snippet=request.source_snippet,
            max_chars=config.max_chars,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid AI explain payload: {str(exc)}") from exc

    try:
        client = GroqClient(config=config)
        completion = await client.chat_completion(
            messages=prompt_payload["messages"],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        explanation = parse_ai_explanation_content(completion.get("content", ""))
        return AIExplainResponse(
            model=completion.get("model") or config.model,
            explanation=explanation,
        )
    except GroqAPIError as exc:
        raise HTTPException(status_code=_map_groq_error_status(exc), detail=str(exc)) from exc


@app.post("/analyze")
async def analyze_source(request: AnalyzeRequest) -> dict:
    """
    Analyze C source code from request body and return a JSON report.
    """
    source_code = request.source_code
    if len(source_code) > MAX_SOURCE_SIZE:
        raise HTTPException(status_code=400, detail="Source code exceeds size limit")

    work_dir = tempfile.mkdtemp(prefix="ub_analyze_")
    source_path = os.path.join(work_dir, _safe_filename(request.filename))

    try:
        with open(source_path, "w", encoding="utf-8") as f:
            f.write(source_code)

        compiled = compile_both(source_path, work_dir=work_dir, keep_ir=True)
        changes = detect_changes(compiled)
        findings = classify_diffs(changes, full_ir=compiled.get("raw_ir"))
        report = generate_report(findings, source_path, compiled)
        return report

    except CompilationError as exc:
        raise HTTPException(status_code=400, detail=f"Compilation error: {str(exc)}") from exc
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(exc)}") from exc
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


@app.post("/analyze-file")
async def analyze_file(request: AnalyzeFileRequest) -> dict:
    """Analyze an existing .c file from disk and return a JSON report."""
    file_path = request.file_path

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    _, ext = os.path.splitext(file_path)
    if ext not in C_CPP_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only C/C++ files are supported (.c, .cpp, .cc, .cxx)")

    try:
        compiled = compile_both(file_path, keep_ir=True)
        changes = detect_changes(compiled)
        findings = classify_diffs(changes, full_ir=compiled.get("raw_ir"))
        report = generate_report(findings, file_path, compiled)
        return report

    except CompilationError as exc:
        raise HTTPException(status_code=400, detail=f"Compilation error: {str(exc)}") from exc
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(exc)}") from exc


# Run with: uvicorn backend.main:app --reload --port 8000
