"""
ub_classifier.py - UB Pattern Classifier (Deliverable 3).

Classifies detected IR changes into specific UB categories.
"""

import re
from typing import Any, Dict, List, Optional

from backend.utils.demangle import demangle
from backend.utils.ir_parser import get_source_location


class UBCategory:
    """Known UB categories for this project."""

    SIGNED_OVERFLOW = "signed_overflow"
    NULL_DEREF = "null_deref"
    STRICT_ALIASING = "strict_aliasing"
    UNINITIALIZED = "uninitialized_use"
    UNKNOWN = "unknown"


class Severity:
    """Severity levels used in reports."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


FIX_SUGGESTIONS = {
    UBCategory.SIGNED_OVERFLOW: (
        "Use unsigned arithmetic, or check bounds before the operation. "
        "Consider __builtin_add_overflow() for safe checked arithmetic."
    ),
    UBCategory.NULL_DEREF: (
        "Move null check BEFORE the first pointer dereference. "
        "Never dereference a pointer before validating it."
    ),
    UBCategory.STRICT_ALIASING: (
        "Use memcpy() for type-punning instead of pointer casts. "
        "Alternatively, compile with -fno-strict-aliasing."
    ),
    UBCategory.UNINITIALIZED: (
        "Initialize all variables at declaration. "
        "Ensure all code paths assign before use."
    ),
    UBCategory.UNKNOWN: (
        "Inspect IR manually: clang -O0/-O2 -g -S -emit-llvm <file>. "
        "Compare basic block structure for clues."
    ),
}


def _classify_signed_overflow(change: Dict[str, Any]) -> bool:
    """
    Detect signed-overflow-sensitive rewrites.

    Supported signals:
    - nsw introduced with branch/block elimination (older behavior)
    - signed add/compare folded to constant return at O2 (clang 22 pattern)
    """
    metrics = change["metrics"]
    nsw_added = metrics["nsw_added"]
    branch_eliminated = metrics["branches_O2"] < metrics["branches_O0"]
    block_loss = metrics["blocks_O2"] < metrics["blocks_O0"]
    folded = metrics.get("signed_overflow_folded", False)
    return folded or (nsw_added and (branch_eliminated or block_loss))


def _classify_null_deref(change: Dict[str, Any]) -> bool:
    """Detect null-check removal with structural simplification."""
    metrics = change["metrics"]
    return (
        metrics["null_checks_O0"] > metrics["null_checks_O2"]
        and metrics["blocks_O2"] < metrics["blocks_O0"]
    )


def _classify_strict_aliasing(change: Dict[str, Any]) -> bool:
    """
    Best-effort strict-aliasing heuristic.

    Supports both typed pointers and LLVM opaque pointer mode.
    """
    o0_ir = change["ir"]["O0"]
    o2_ir = change["ir"]["O2"]

    has_suspicious_bitcast = bool(
        re.search(r"bitcast\s+.+\s+to\s+.+", o0_ir)
    )
    if not has_suspicious_bitcast:
        return False

    o0_loads = len(re.findall(r"\bload\b", o0_ir))
    o2_loads = len(re.findall(r"\bload\b", o2_ir))
    return o2_loads < o0_loads


def _classify_uninitialized(change: Dict[str, Any]) -> bool:
    """Detect likely uninitialized use via alloca + undef exposure."""
    o0_ir = change["ir"]["O0"]
    metrics = change["metrics"]

    has_alloca = "alloca" in o0_ir
    undef_exposed = metrics["undef_exposed"]
    return has_alloca and undef_exposed


def classify_diffs(
    changes: List[Dict[str, Any]], full_ir: Optional[dict] = None
) -> List[Dict[str, Any]]:
    """
    Classify each changed function into a UB category.

    Input: Output of detect_changes()
    Returns: List of findings with category, severity, and details.
    """
    findings: List[Dict[str, Any]] = []

    for change in changes:
        func_name = change["function"]

        if "inlined_at_O2" in change.get("change_types", []):
            findings.append(
                {
                    "function": func_name,
                    "readable_name": demangle(func_name),
                    "category": "inlined",
                    "severity": Severity.INFO,
                    "detail": change.get("note", "Function inlined at -O2."),
                    "fix": "Use -fno-inline during analysis to preserve function boundaries.",
                    "location": None,
                    "confidence": "N/A",
                    "metrics": change["metrics"],
                    "ir": change.get("ir", {}),
                }
            )
            continue

        if _classify_signed_overflow(change):
            category = UBCategory.SIGNED_OVERFLOW
            severity = Severity.CRITICAL
            if change["metrics"].get("signed_overflow_folded", False):
                detail = (
                    "Signed add/compare at -O0 was folded to a constant return "
                    "at -O2 (e.g., x + 1 > x -> 1, x + 1 < x -> 0): "
                    "optimizer assumed signed overflow is undefined."
                )
            else:
                detail = (
                    "'add nsw' at -O2 combined with branch elimination: "
                    "optimizer assumed signed overflow cannot occur, "
                    "eliminating safety checks."
                )
            confidence = "HIGH"
        elif _classify_null_deref(change):
            category = UBCategory.NULL_DEREF
            severity = Severity.CRITICAL
            detail = (
                "Null pointer check at -O0 removed at -O2: "
                "pointer assumed non-null due to prior dereference."
            )
            confidence = "HIGH"
        elif _classify_uninitialized(change):
            category = UBCategory.UNINITIALIZED
            severity = Severity.HIGH
            detail = (
                "alloca loaded before store in execution order: "
                "value is indeterminate (poison/undef at -O2)."
            )
            confidence = "MEDIUM"
        elif _classify_strict_aliasing(change):
            category = UBCategory.STRICT_ALIASING
            severity = Severity.HIGH
            detail = (
                "Type-punned pointer load optimized away at -O2. "
                "Strict aliasing rule violated via incompatible pointer cast."
            )
            confidence = "PARTIAL"
        else:
            category = UBCategory.UNKNOWN
            severity = Severity.MEDIUM
            detail = (
                "CFG changed between -O0 and -O2 but pattern unmatched. "
                "Possibly a UB type not yet covered by the classifier."
            )
            confidence = "LOW"

        location = None
        if full_ir:
            o0_full = full_ir.get("O0_full", "")
            location = get_source_location(change["ir"]["O0"], o0_full)

        findings.append(
            {
                "function": func_name,
                "readable_name": demangle(func_name),
                "category": category,
                "severity": severity,
                "detail": detail,
                "fix": FIX_SUGGESTIONS.get(category, ""),
                "location": location,
                "confidence": confidence,
                "metrics": change["metrics"],
                "ir": change.get("ir", {}),
            }
        )

    return findings
