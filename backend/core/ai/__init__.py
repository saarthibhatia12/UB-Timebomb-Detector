"""AI integration package for explainability features."""

from backend.core.ai.groq_client import (
    GroqAPIError,
    GroqClient,
    GroqClientConfig,
    load_groq_config,
)
from backend.core.ai.prompt_builder import (
    MAX_IR_DIFF_LINES,
    SYSTEM_PROMPT,
    build_compact_ir_diff,
    build_ir_diff_explain_prompt,
    build_prompt_payload,
    parse_ai_explanation_content,
    parse_ir_diff_explanation_content,
)
from backend.core.ai.schemas import AIExplainStatus

__all__ = [
    "GroqAPIError",
    "GroqClient",
    "GroqClientConfig",
    "load_groq_config",
    "AIExplainStatus",
    "MAX_IR_DIFF_LINES",
    "SYSTEM_PROMPT",
    "build_compact_ir_diff",
    "build_ir_diff_explain_prompt",
    "build_prompt_payload",
    "parse_ai_explanation_content",
    "parse_ir_diff_explanation_content",
]
