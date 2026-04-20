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
