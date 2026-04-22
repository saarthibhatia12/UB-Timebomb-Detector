"""Prompt construction and response parsing utilities for AI explanations."""

from __future__ import annotations

import json
from difflib import unified_diff
from typing import Any, Dict, List, Mapping, Tuple

from backend.core.ai.groq_client import DEFAULT_MAX_CHARS
from backend.core.ai.schemas import AIExplanation


MAX_IR_DIFF_LINES = 400
SYSTEM_PROMPT = (
    "You are a compiler and undefined-behavior analysis assistant. "
    "Explain findings to a beginner, define jargon, and only use the provided evidence. "
    "Do not invent facts. Use the IR diff and metrics to justify claims. "
    "Return strict JSON with keys: summary_plain, what_is_the_ub, what_changed_in_ir, "
    "why_optimizer_removed_code, fixes, safer_rewrite, caveats."
)

_IMPORTANT_DIFF_TOKENS = (
    "define ",
    "ret ",
    " br ",
    "icmp",
)

_SECONDARY_DIFF_TOKENS = (
    "nsw",
)


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _truncate_text(text: str, max_chars: int, *, suffix: str = "... [truncated]") -> str:
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    if max_chars <= len(suffix):
        return suffix[:max_chars]
    return f"{text[: max_chars - len(suffix)]}{suffix}"


def _line_is_important(diff_line: str) -> bool:
    stripped = diff_line.lstrip("+- ").lower()
    if diff_line.startswith("@@"):
        return True
    if stripped.startswith("define ") or stripped.startswith("@"):
        return True
    return any(token in f" {stripped} " for token in _IMPORTANT_DIFF_TOKENS)


def _line_is_secondary(diff_line: str) -> bool:
    stripped = diff_line.lstrip("+- ").lower()
    return any(token in f" {stripped} " for token in _SECONDARY_DIFF_TOKENS)


def _fit_lines_to_budget(lines: List[str], max_chars: int) -> Tuple[str, bool]:
    if max_chars <= 0:
        return "", bool(lines)

    selected: List[str] = []
    total = 0
    truncated = False

    for line in lines:
        line_len = len(line) + 1
        if total + line_len > max_chars:
            truncated = True
            break
        selected.append(line)
        total += line_len

    if truncated:
        marker = "... [IR diff truncated]"
        if total + len(marker) + 1 <= max_chars:
            selected.append(marker)
        elif selected and len(selected[-1]) >= len(marker):
            selected[-1] = marker
        elif not selected:
            return marker[:max_chars], True

    return "\n".join(selected), truncated


def build_compact_ir_diff(
    o0_ir: str,
    o2_ir: str,
    *,
    max_chars: int,
    max_lines: int = MAX_IR_DIFF_LINES,
) -> Dict[str, Any]:
    """Build a bounded unified diff and prioritize lines that explain optimizer behavior."""

    o0_lines = _as_text(o0_ir).splitlines()
    o2_lines = _as_text(o2_ir).splitlines()

    diff_lines = list(
        unified_diff(
            o0_lines,
            o2_lines,
            fromfile="O0",
            tofile="O2",
            lineterm="",
        )
    )

    if not diff_lines:
        text = "No IR diff available."
        return {
            "text": _truncate_text(text, max_chars),
            "truncated": len(text) > max_chars,
            "line_count": 0,
            "selected_lines": 1,
        }

    if max_lines > 0 and len(diff_lines) > max_lines:
        diff_lines = diff_lines[:max_lines]
        diff_lines.append("... [IR diff line cap reached]")

    full_text = "\n".join(diff_lines)
    if len(full_text) <= max_chars:
        return {
            "text": full_text,
            "truncated": False,
            "line_count": len(diff_lines),
            "selected_lines": len(diff_lines),
        }

    primary_indices = set()
    secondary_indices = set()
    for idx, line in enumerate(diff_lines):
        if _line_is_important(line):
            primary_indices.add(idx)
            if idx > 0:
                primary_indices.add(idx - 1)
            if idx + 1 < len(diff_lines):
                primary_indices.add(idx + 1)
        elif _line_is_secondary(line):
            secondary_indices.add(idx)
            if idx > 0:
                secondary_indices.add(idx - 1)
            if idx + 1 < len(diff_lines):
                secondary_indices.add(idx + 1)

    metadata_indices = {
        idx
        for idx, line in enumerate(diff_lines)
        if line.startswith("---") or line.startswith("+++") or line.startswith("@@")
    }
    change_indices = {
        idx
        for idx, line in enumerate(diff_lines)
        if line.startswith("+") or line.startswith("-")
    }

    seen = set()
    ordered_indices: List[int] = []

    def _append_unique(indices: List[int]) -> None:
        for index in indices:
            if index not in seen:
                seen.add(index)
                ordered_indices.append(index)

    _append_unique(sorted(metadata_indices))
    _append_unique(sorted(primary_indices))
    _append_unique(sorted(secondary_indices))
    _append_unique(sorted(change_indices))
    _append_unique(list(range(len(diff_lines))))

    selected_lines = [diff_lines[idx] for idx in ordered_indices]
    compact_text, truncated = _fit_lines_to_budget(selected_lines, max_chars)

    return {
        "text": compact_text,
        "truncated": truncated,
        "line_count": len(diff_lines),
        "selected_lines": len(compact_text.splitlines()) if compact_text else 0,
    }


def _metrics_text(metrics: Any) -> str:
    if not isinstance(metrics, Mapping):
        return "{}"
    try:
        return json.dumps(metrics, sort_keys=True)
    except TypeError:
        safe = {str(k): _as_text(v) for k, v in metrics.items()}
        return json.dumps(safe, sort_keys=True)


def build_prompt_payload(
    finding: Mapping[str, Any],
    source_snippet: str | None = None,
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> Dict[str, Any]:
    """Create system+user messages with bounded size and compact IR context."""

    if max_chars <= 0:
        raise ValueError("max_chars must be greater than zero")

    finding_dict = dict(finding or {})
    metrics = finding_dict.get("metrics", {})
    ir_data = finding_dict.get("ir", {}) if isinstance(finding_dict.get("ir", {}), Mapping) else {}

    selected_source = _as_text(
        source_snippet if source_snippet is not None else finding_dict.get("source_snippet", "")
    )

    max_user_chars = max(500, max_chars - len(SYSTEM_PROMPT) - 1)
    source_budget = max(200, int(max_user_chars * 0.2))
    diff_budget = max(400, int(max_user_chars * 0.55))

    compact_diff = build_compact_ir_diff(
        _as_text(ir_data.get("O0", "")),
        _as_text(ir_data.get("O2", "")),
        max_chars=diff_budget,
    )
    source_excerpt = _truncate_text(selected_source, source_budget, suffix="... [source snippet truncated]")

    user_prompt = "\n\n".join(
        [
            "Finding summary:",
            f"- function: {_as_text(finding_dict.get('readable_name') or finding_dict.get('function') or 'unknown')}",
            f"- category: {_as_text(finding_dict.get('category', 'unknown'))}",
            f"- severity: {_as_text(finding_dict.get('severity', 'unknown'))}",
            f"- confidence: {_as_text(finding_dict.get('confidence', 'unknown'))}",
            f"- detail: {_as_text(finding_dict.get('detail', ''))}",
            f"- suggested_fix: {_as_text(finding_dict.get('fix', ''))}",
            f"- metrics: {_metrics_text(metrics)}",
            "Source snippet:",
            source_excerpt or "(not available)",
            "IR diff (O0 vs O2):",
            compact_diff["text"],
        ]
    )
    user_prompt = _truncate_text(user_prompt, max_user_chars, suffix="... [prompt payload truncated]")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    return {
        "messages": messages,
        "context": {
            "category": _as_text(finding_dict.get("category", "unknown")),
            "severity": _as_text(finding_dict.get("severity", "unknown")),
            "confidence": _as_text(finding_dict.get("confidence", "unknown")),
            "detail": _as_text(finding_dict.get("detail", "")),
            "fix": _as_text(finding_dict.get("fix", "")),
        },
        "ir_diff": compact_diff,
        "chars_used": len(SYSTEM_PROMPT) + len(user_prompt),
        "max_chars": max_chars,
    }


def _normalize_fixes(value: Any) -> List[str]:
    if isinstance(value, list):
        return [_as_text(v).strip() for v in value if _as_text(v).strip()]
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    return []


def _normalize_explanation_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "summary_plain": _as_text(payload.get("summary_plain", "")).strip(),
        "what_is_the_ub": _as_text(payload.get("what_is_the_ub", "")).strip(),
        "what_changed_in_ir": _as_text(payload.get("what_changed_in_ir", "")).strip(),
        "why_optimizer_removed_code": _as_text(payload.get("why_optimizer_removed_code", "")).strip(),
        "fixes": _normalize_fixes(payload.get("fixes", [])),
        "safer_rewrite": _as_text(payload.get("safer_rewrite", "")).strip(),
        "caveats": _as_text(payload.get("caveats", "")).strip(),
    }


def _extract_first_json_object(text: str) -> str | None:
    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escaped = False

        for idx in range(start, len(text)):
            char = text[idx]

            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : idx + 1]

        start = text.find("{", start + 1)

    return None


def parse_ai_explanation_content(content: str) -> AIExplanation:
    """Parse model output as AIExplanation with safe JSON fallbacks."""

    normalized = _as_text(content).strip()
    if not normalized:
        return AIExplanation()

    parsed_obj: Any = None
    try:
        parsed_obj = json.loads(normalized)
    except ValueError:
        candidate_json = _extract_first_json_object(normalized)
        if candidate_json:
            try:
                parsed_obj = json.loads(candidate_json)
            except ValueError:
                parsed_obj = None

    if isinstance(parsed_obj, Mapping):
        candidate = parsed_obj.get("explanation") if isinstance(parsed_obj.get("explanation"), Mapping) else parsed_obj
        if isinstance(candidate, Mapping):
            try:
                return AIExplanation(**_normalize_explanation_payload(candidate))
            except Exception:  # noqa: BLE001
                pass

    return AIExplanation(
        summary_plain=_truncate_text(normalized, 1500, suffix="... [raw model output truncated]"),
        caveats="Model output was not valid JSON; returning raw summary.",
    )
