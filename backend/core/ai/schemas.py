"""Stable request/response schemas for AI explanation features."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AIExplanation(BaseModel):
    """Structured explanation payload rendered by the frontend."""

    summary_plain: str = ""
    what_is_the_ub: str = ""
    what_changed_in_ir: str = ""
    why_optimizer_removed_code: str = ""
    fixes: List[str] = Field(default_factory=list)
    safer_rewrite: Optional[str] = ""
    caveats: str = ""


class AIExplainRequest(BaseModel):
    """Payload for per-finding AI explanation requests."""

    finding: Dict[str, Any] = Field(default_factory=dict)
    source_snippet: Optional[str] = None


class AIExplainResponse(BaseModel):
    """Top-level AI explain response envelope."""

    model: str = ""
    explanation: AIExplanation = Field(default_factory=AIExplanation)


class AIExplainStatus(BaseModel):
    """Availability info used by the frontend to disable AI when not configured."""

    enabled: bool = False
    model: str = ""
    fallback_model: str = ""
    max_chars: int = 0
    reason: str = ""


class IRDiffExplanation(BaseModel):
    """Human-readable IR diff explanation rendered in the LLVM IR Diff panel."""

    before_summary: str = ""
    before_code: str = ""
    after_summary: str = ""
    after_code: str = ""
    key_changes: List[str] = Field(default_factory=list)
    why_it_matters: str = ""
    risk_level: str = "medium"


class IRDiffExplainRequest(BaseModel):
    """Request payload for the IR diff explanation endpoint."""

    o0_ir: str = ""
    o2_ir: str = ""
    source_snippet: Optional[str] = None
    finding_context: Dict[str, Any] = Field(default_factory=dict)


class IRDiffExplainResponse(BaseModel):
    """Response envelope for the IR diff explanation endpoint."""

    model: str = ""
    explanation: IRDiffExplanation = Field(default_factory=IRDiffExplanation)


def phase0_contract_response() -> AIExplainResponse:
    """Return an empty response shape used to lock the API contract in Phase 0."""

    return AIExplainResponse(model="phase-0-contract")
