"""
ir_parser.py - Parse LLVM IR (.ll) files into per-function blocks.

Uses balanced-brace matching instead of naive splitting.
"""

import re
from typing import Dict, Optional


def parse_ir_by_function(ll_path: str) -> Dict[str, str]:
    """
    Parse a .ll file and return a dict mapping function names to their
    complete IR text (from 'define' to the closing '}').
    """
    with open(ll_path, "r", encoding="utf-8") as f:
        content = f.read()

    functions: Dict[str, str] = {}

    # Pattern: define <linkage>? <ret_type> @<name>(<args>) <attrs>? {
    func_header = re.compile(r"define\s+[^@]*@([\w$.]+)\s*\([^)]*\)[^{]*\{")

    for match in func_header.finditer(content):
        name = match.group(1)
        start = match.start()

        # Find matching closing brace with balanced counting.
        depth = 0
        end = start
        for i in range(match.end() - 1, len(content)):
            if content[i] == "{":
                depth += 1
            elif content[i] == "}":
                depth -= 1
            if depth == 0:
                end = i + 1
                break

        functions[name] = content[start:end]

    return functions


def count_basic_blocks(func_ir: str) -> int:
    """Count basic blocks in a function IR."""
    labels = re.findall(r"^\w[\w.]*:", func_ir, re.MULTILINE)
    return len(labels) + 1  # +1 for entry block


def count_conditional_branches(func_ir: str) -> int:
    """Count conditional branch instructions (br i1 ...)."""
    return len(re.findall(r"br\s+i1\s+", func_ir))


def count_unconditional_branches(func_ir: str) -> int:
    """Count unconditional branch instructions (br label ...)."""
    return len(re.findall(r"br\s+label\s+", func_ir))


def has_nsw_flag(func_ir: str) -> bool:
    """Check if arithmetic instructions include the nsw flag."""
    return bool(re.search(r"\b(add|sub|mul|shl)\s+nsw\b", func_ir))


def has_signed_add_compare_pattern(func_ir: str) -> bool:
    """
    Detect patterns like `(x + 1 > x)` or `(x + 1 < x)` in LLVM IR.

    This is used for clang 22 behavior where O2 may fold the expression to a
    constant return instead of introducing new `nsw` at O2.
    """
    load_ptr_by_var = {
        m.group(1): m.group(2)
        for m in re.finditer(
            r"^\s*(%[\w.]+)\s*=\s*load i32,\s*ptr\s*(%[\w.]+)\b",
            func_ir,
            re.MULTILINE,
        )
    }

    add_ops = [
        (m.group(1), m.group(2), int(m.group(3)))
        for m in re.finditer(
            r"^\s*(%[\w.]+)\s*=\s*add nsw i32\s*(%[\w.]+),\s*(-?\d+)\b",
            func_ir,
            re.MULTILINE,
        )
    ]

    signed_cmps = [
        (m.group(1), m.group(2))
        for m in re.finditer(
            r"^\s*%[\w.]+\s*=\s*icmp\s+s(?:gt|lt|ge|le)\s+i32\s*(%[\w.]+),\s*(%[\w.]+)\b",
            func_ir,
            re.MULTILINE,
        )
    ]

    for add_result, base_var, delta in add_ops:
        if delta not in (1, -1):
            continue

        for lhs, rhs in signed_cmps:
            if add_result == lhs:
                other_var = rhs
            elif add_result == rhs:
                other_var = lhs
            else:
                continue

            if base_var == other_var:
                return True

            if (
                base_var in load_ptr_by_var
                and other_var in load_ptr_by_var
                and load_ptr_by_var[base_var] == load_ptr_by_var[other_var]
            ):
                return True

    return False


def returns_constant_i32(func_ir: str) -> Optional[int]:
    """Return constant i32 value if function has a single constant return."""
    ret_values = re.findall(r"^\s*ret i32 (-?\d+)\b", func_ir, re.MULTILINE)
    if len(ret_values) != 1:
        return None

    try:
        return int(ret_values[0])
    except ValueError:
        return None


def has_undef(func_ir: str) -> bool:
    """Check if undef appears in value-producing positions."""
    return bool(re.search(r"(select|phi|ret)\s+.*\bundef\b", func_ir))


def has_null_check(func_ir: str) -> int:
    """Count null pointer comparisons (icmp eq/ne ... null)."""
    return len(re.findall(r"icmp\s+(?:eq|ne)\s+.*\bnull\b", func_ir))


def extract_dbg_lines(func_ir: str) -> list:
    """Extract debug metadata reference IDs from !dbg tags."""
    return re.findall(r"!dbg\s+!(\d+)", func_ir)


def get_source_location(func_ir: str, full_ll_content: str = "") -> Optional[dict]:
    """
    Extract source file and line number from debug metadata.
    Returns {"file": "...", "line": N} or None.
    """
    dbg_refs = re.findall(r"!dbg\s+!(\d+)", func_ir)
    if not dbg_refs and not full_ll_content:
        return None

    search_content = full_ll_content or func_ir
    for ref in dbg_refs:
        loc_match = re.search(
            rf"!{ref}\s*=\s*!DILocation\(line:\s*(\d+).*?(?:file:\s*\"([^\"]*)\")?",
            search_content,
        )
        if loc_match:
            return {
                "line": int(loc_match.group(1)),
                "file": loc_match.group(2) or "unknown",
            }

    return None
