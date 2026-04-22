"""Tests for backend.core.ai.prompt_builder."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.core.ai.prompt_builder import (  # noqa: E402
    build_compact_ir_diff,
    build_prompt_payload,
    parse_ai_explanation_content,
)


def _make_o0_ir(extra_ops: int = 80) -> str:
    lines = [
        "define i32 @demo(i32 %x) {",
        "entry:",
    ]
    for idx in range(extra_ops):
        lines.append(f"  %tmp{idx} = add nsw i32 %x, {idx}")
    lines.extend(
        [
            "  %cmp = icmp sgt i32 %x, 0",
            "  br i1 %cmp, label %ret1, label %ret2",
            "ret1:",
            "  ret i32 1",
            "ret2:",
            "  ret i32 0",
            "}",
        ]
    )
    return "\n".join(lines)


def _make_o2_ir() -> str:
    return "\n".join(
        [
            "define i32 @demo(i32 %x) {",
            "entry:",
            "  %cmp = icmp sgt i32 %x, 0",
            "  %sel = select i1 %cmp, i32 1, i32 0",
            "  ret i32 %sel",
            "}",
        ]
    )


def test_build_prompt_payload_respects_total_char_limit():
    finding = {
        "function": "demo",
        "readable_name": "demo",
        "category": "signed_overflow",
        "severity": "critical",
        "confidence": "HIGH",
        "detail": "Signed overflow assumptions changed control flow.",
        "fix": "Use checked arithmetic helpers.",
        "metrics": {
            "blocks_O0": 10,
            "blocks_O2": 3,
            "branches_O0": 6,
            "branches_O2": 1,
            "nsw_added": True,
        },
        "ir": {
            "O0": _make_o0_ir(),
            "O2": _make_o2_ir(),
        },
        "source_snippet": "int demo(int x) { return x + 1 > x; }\n" * 25,
    }

    payload = build_prompt_payload(finding, max_chars=1500)
    total_chars = sum(len(message["content"]) for message in payload["messages"])

    assert len(payload["messages"]) == 2
    assert total_chars <= 1500
    assert payload["chars_used"] <= 1500


def test_build_compact_ir_diff_prioritizes_key_lines_when_truncated():
    compact = build_compact_ir_diff(_make_o0_ir(extra_ops=140), _make_o2_ir(), max_chars=500)

    assert compact["truncated"] is True
    text = compact["text"]
    assert "icmp" in text
    assert "ret i32" in text


def test_parse_ai_explanation_content_from_valid_nested_json():
    content = (
        '{"model":"llama-3.3-70b-versatile","explanation":{'
        '"summary_plain":"summary",'
        '"what_is_the_ub":"ub",'
        '"what_changed_in_ir":"ir",'
        '"why_optimizer_removed_code":"why",'
        '"fixes":["fix1","fix2"],'
        '"safer_rewrite":"rewrite",'
        '"caveats":"none"'
        '}}'
    )

    parsed = parse_ai_explanation_content(content)

    assert parsed.summary_plain == "summary"
    assert parsed.what_is_the_ub == "ub"
    assert parsed.fixes == ["fix1", "fix2"]


def test_parse_ai_explanation_content_extracts_first_json_object():
    content = (
        "Here is your answer:\n"
        "{\"summary_plain\":\"ok\",\"fixes\":\"prefer bounds checks\"}\n"
        "Thanks."
    )

    parsed = parse_ai_explanation_content(content)

    assert parsed.summary_plain == "ok"
    assert parsed.fixes == ["prefer bounds checks"]


def test_parse_ai_explanation_content_falls_back_to_raw_summary():
    content = "not json at all but still useful to show user"

    parsed = parse_ai_explanation_content(content)

    assert parsed.summary_plain.startswith("not json at all")
    assert "not valid JSON" in parsed.caveats
