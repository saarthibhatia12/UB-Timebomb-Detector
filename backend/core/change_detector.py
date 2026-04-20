"""
change_detector.py - Behavioral Change Detector (Deliverable 2).

Compares -O0 and -O2 IR per function and detects structural changes.
"""

from typing import Any, Dict, List

from backend.utils.ir_parser import (
    count_basic_blocks,
    count_conditional_branches,
    count_unconditional_branches,
    has_nsw_flag,
    has_null_check,
    has_signed_add_compare_pattern,
    has_undef,
    returns_constant_i32,
)


def detect_changes(compiled_result: dict) -> List[Dict[str, Any]]:
    """
    Analyze compiled IR and detect behavioral changes between -O0 and -O2.

    Input: Output of compile_both()
    Returns: List of changed functions with diff metadata.
    """
    changes: List[Dict[str, Any]] = []

    for func_name, ir_pair in compiled_result["functions"].items():
        o0_ir = ir_pair["O0"]
        o2_ir = ir_pair["O2"]

        # Structural metrics.
        blocks_o0 = count_basic_blocks(o0_ir)
        blocks_o2 = count_basic_blocks(o2_ir)
        branches_o0 = count_conditional_branches(o0_ir)
        branches_o2 = count_conditional_branches(o2_ir)

        # Kept for parity and future diagnostics.
        _ = count_unconditional_branches(o0_ir)
        _ = count_unconditional_branches(o2_ir)

        # Flag changes.
        nsw_o0 = has_nsw_flag(o0_ir)
        nsw_o2 = has_nsw_flag(o2_ir)
        nsw_added = nsw_o2 and not nsw_o0

        # Null-check changes.
        null_checks_o0 = has_null_check(o0_ir)
        null_checks_o2 = has_null_check(o2_ir)
        null_check_removed = null_checks_o0 > null_checks_o2

        # Undef changes (narrow detection in parser helper).
        undef_o0 = has_undef(o0_ir)
        undef_o2 = has_undef(o2_ir)
        undef_exposed = undef_o2 and not undef_o0

        # Clang 22 pattern: signed add-compare at O0 folded to constant at O2.
        has_signed_cmp_o0 = has_signed_add_compare_pattern(o0_ir)
        o0_const_ret = returns_constant_i32(o0_ir)
        o2_const_ret = returns_constant_i32(o2_ir)
        signed_overflow_folded = (
            has_signed_cmp_o0
            and o0_const_ret is None
            and o2_const_ret in (0, 1)
        )

        # Determine if there is a meaningful behavioral change.
        block_loss = blocks_o2 < blocks_o0
        branch_eliminated = branches_o2 < branches_o0

        has_change = (
            block_loss
            or branch_eliminated
            or (nsw_added and branch_eliminated)
            or null_check_removed
            or undef_exposed
            or signed_overflow_folded
        )

        if has_change:
            change_types = []
            if block_loss:
                change_types.append("block_loss")
            if branch_eliminated:
                change_types.append("branch_elimination")
            if nsw_added:
                change_types.append("nsw_flag_added")
            if null_check_removed:
                change_types.append("null_check_removed")
            if undef_exposed:
                change_types.append("undef_exposed")
            if signed_overflow_folded:
                change_types.append("signed_overflow_folded")

            changes.append(
                {
                    "function": func_name,
                    "change_types": change_types,
                    "metrics": {
                        "blocks_O0": blocks_o0,
                        "blocks_O2": blocks_o2,
                        "branches_O0": branches_o0,
                        "branches_O2": branches_o2,
                        "nsw_added": nsw_added,
                        "null_checks_O0": null_checks_o0,
                        "null_checks_O2": null_checks_o2,
                        "undef_exposed": undef_exposed,
                        "signed_overflow_folded": signed_overflow_folded,
                        "o0_const_ret": o0_const_ret,
                        "o2_const_ret": o2_const_ret,
                    },
                    "ir": {
                        "O0": o0_ir,
                        "O2": o2_ir,
                    },
                }
            )

    # Also report functions that only exist at O0 (e.g., inlined/removed at O2).
    for func_name in compiled_result.get("o0_only", []):
        changes.append(
            {
                "function": func_name,
                "change_types": ["inlined_at_O2"],
                "metrics": {
                    "blocks_O0": -1,
                    "blocks_O2": 0,
                    "branches_O0": -1,
                    "branches_O2": 0,
                    "nsw_added": False,
                    "null_checks_O0": 0,
                    "null_checks_O2": 0,
                    "undef_exposed": False,
                    "signed_overflow_folded": False,
                    "o0_const_ret": None,
                    "o2_const_ret": None,
                },
                "ir": {
                    "O0": "",
                    "O2": "[inlined - function not present at -O2]",
                },
                "note": f"Function '{func_name}' was inlined at -O2; cannot diff CFG.",
            }
        )

    return changes
