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


def has_type_punning_pattern(o0_ir: str, o2_ir: str) -> bool:
    """
    Detect strict aliasing violation via type punning with opaque pointers.

    With LLVM 22 opaque pointers, there are no bitcasts between pointer types.
    Instead, we detect: a store of type A and a load of type B in the same
    function (type punning), combined with O2 eliminating the load or folding
    it to a constant.

    This uses a relaxed pointer-matching strategy: instead of requiring the
    same SSA name (which fails because of alloca indirection at O0), we check
    that different scalar types are stored and loaded anywhere in the function,
    and that O2 optimized away the typed load.
    """
    scalar_types = r"(?:float|double|i8|i16|i32|i64)"

    # Find all store types and load types in O0
    store_types = set(re.findall(
        rf"store\s+({scalar_types})\s+", o0_ir
    ))
    load_types = set(re.findall(
        rf"=\s*load\s+({scalar_types}),", o0_ir
    ))

    # Filter out ptr stores/loads (alloca bookkeeping)
    # We only care about value-type stores and loads
    value_store_types = store_types - {"ptr"}
    value_load_types = load_types - {"ptr"}

    # Check for type mismatch (e.g., store float + load i32)
    if not value_store_types or not value_load_types:
        return False
    if not (value_store_types - value_load_types):
        # All stored types are also loaded as the same type — no punning
        return False

    # There's a type mismatch. Now check if O2 optimized it away:
    # Either the typed load is gone, or O2 returns a constant where O0 didn't.
    o0_typed_loads = len(re.findall(
        rf"=\s*load\s+{scalar_types},", o0_ir
    ))
    o2_typed_loads = len(re.findall(
        rf"=\s*load\s+{scalar_types},", o2_ir
    ))

    if o2_typed_loads < o0_typed_loads:
        return True

    # Check if O2 returns a constant where O0 computed a value
    if returns_constant_i32(o2_ir) is not None and returns_constant_i32(o0_ir) is None:
        return True

    return False



def has_loop_with_signed_overflow_guard(func_ir: str) -> bool:
    """
    Detect a loop containing a signed overflow guard that the optimizer
    would remove. Pattern: signed add + signed compare < 0 inside a loop.
    """
    # Check for a loop structure (back-edge: branch to earlier label)
    has_loop = bool(re.search(r"br\s+(i1\s+%[\w.]+,\s*)?label\s+%", func_ir))
    if not has_loop:
        return False

    # Check for signed add (nsw) inside the function
    has_nsw_add = bool(re.search(r"add\s+nsw\s+i32", func_ir))

    # Check for signed comparison (overflow guard like i+1 < 0)
    has_signed_cmp = bool(re.search(r"icmp\s+s(lt|le|gt|ge)\s+i32", func_ir))

    return has_nsw_add and has_signed_cmp
