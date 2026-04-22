"""
main.py - FastAPI server for UB Time Bomb Detector.

Includes input validation, size limits, and compilation error handling.
"""

import os
import shutil
import tempfile
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.core.change_detector import detect_changes
from backend.core.compile_engine import CompilationError, compile_both
from backend.core.report_generator import generate_report
from backend.core.ub_classifier import classify_diffs


app = FastAPI(
    title="UB Time Bomb Detector",
    description="Static analysis tool for detecting undefined behavior time bombs in C/C++ code",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_SOURCE_SIZE = 50_000


class AnalyzeRequest(BaseModel):
    """Request payload for source-string analysis."""

    source_code: str = Field(...)
    filename: Optional[str] = Field(default="input.c")


class AnalyzeFileRequest(BaseModel):
    """Request payload for file-path analysis."""

    file_path: str


C_CPP_EXTENSIONS = {".c", ".cpp", ".cc", ".cxx", ".C", ".c++"}


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
