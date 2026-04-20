# UB Time Bomb Detector — Implementation Plan
## For AI Coding Agent (Phase-by-Phase)

> **Context:** This plan builds a static analysis tool that detects C/C++ undefined behavior
> by comparing LLVM IR at `-O0` vs `-O2`. It uses Python+FastAPI for the backend analysis
> engine and React+Vite+Tailwind+shadcn/ui for the dashboard frontend.
>
> **All fixes from the plan review are incorporated inline (marked with `[FIX #N]`).**

---

## Tech Stack Reference

| Layer | Technology |
|---|---|
| Frontend | React, Vite, Tailwind CSS, shadcn/ui |
| Code Viewer | Monaco Editor (`@monaco-editor/react`) |
| Charts | Recharts |
| Backend | Python 3.10+, FastAPI, uvicorn |
| Compiler | Clang 14+ / LLVM |
| IR Parsing | Python regex (no llvmlite dependency) |
| Testing | pytest |
| VCS | Git |

---

## Final Project Structure

```
d:\UB Timebomb Detector\
├── README.md
├── requirements.txt
├── implementation_plan.md          ← this file
├── plan.md                         ← original spec
│
├── backend/
│   ├── main.py                     ← FastAPI server entry
│   ├── core/
│   │   ├── __init__.py
│   │   ├── compile_engine.py       ← Deliverable 1
│   │   ├── change_detector.py      ← Deliverable 2
│   │   ├── ub_classifier.py        ← Deliverable 3
│   │   └── report_generator.py     ← Deliverable 4
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── ir_parser.py            ← .ll file parser
│   │   └── demangle.py             ← C++ name demangling
│   └── tests/
│       ├── __init__.py
│       ├── test_compile_engine.py
│       ├── test_change_detector.py
│       └── test_ub_classifier.py
│
├── test_cases/                     ← Deliverable 5
│   ├── signed_overflow.c
│   ├── null_deref.c
│   ├── strict_aliasing.c
│   ├── uninitialized.c
│   └── loop_overflow.c
│
├── eval/
│   ├── cve_cases/
│   │   ├── gcc_bug_30475.c
│   │   ├── cve_2009_1897.c
│   │   ├── cve_2017_9798.c
│   │   ├── cve_2014_3153.c
│   │   └── cve_2018_6789.c
│   └── run_evaluation.py
│
└── frontend/                       ← React dashboard
    ├── package.json
    ├── vite.config.js
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── index.html
    ├── components.json             ← shadcn config
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── index.css
        ├── lib/
        │   └── utils.js            ← shadcn utility (cn)
        ├── components/
        │   ├── ui/                 ← shadcn primitives
        │   │   ├── card.jsx
        │   │   ├── badge.jsx
        │   │   ├── button.jsx
        │   │   ├── tabs.jsx
        │   │   ├── alert.jsx
        │   │   └── scroll-area.jsx
        │   ├── Header.jsx
        │   ├── StatsBar.jsx
        │   ├── SourceViewer.jsx
        │   ├── IRDiffViewer.jsx
        │   ├── FindingsPanel.jsx
        │   ├── ReportPanel.jsx
        │   ├── CVEDatabase.jsx
        │   └── RiskGauge.jsx
        └── hooks/
            └── useAnalysis.js      ← API hook
```

---

# Phase 0 — Environment Setup

**Goal:** Install all dependencies and verify Clang works.

## Step 0.1 — Verify Clang is installed

```powershell
# Run in PowerShell. If clang is not found, install it.
clang --version
# Must show version 14 or higher

# If not installed:
winget install LLVM.LLVM

# After install, verify:
clang --version
```

## Step 0.2 — Create Python virtual environment

```powershell
cd "d:\UB Timebomb Detector"
python -m venv venv
.\venv\Scripts\Activate.ps1
```

## Step 0.3 — Create `requirements.txt`

```
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
python-multipart>=0.0.9
jinja2>=3.1.3
pytest>=8.0.0
```

```powershell
pip install -r requirements.txt
```

## Step 0.4 — Create directory skeleton

```powershell
$dirs = @(
    'backend/core',
    'backend/utils',
    'backend/tests',
    'test_cases',
    'eval/cve_cases'
)
$dirs | ForEach-Object { New-Item -ItemType Directory -Force -Path $_ }

# Create __init__.py files
@('backend', 'backend/core', 'backend/utils', 'backend/tests') |
    ForEach-Object { New-Item "$_/__init__.py" -ItemType File -Force | Out-Null }
```

## Step 0.5 — Verify IR generation works manually

```powershell
# Create a quick test file
@'
int f(int x) { return x + 1 > x; }
'@ | Set-Content "test_cases/_verify.c"

# Generate IR at both levels [FIX #1: -g flag] [FIX #2: -fno-inline]
clang -O0 -g -fno-inline -emit-llvm -S -o test_cases/_verify_O0.ll test_cases/_verify.c
clang -O2 -g -fno-inline -emit-llvm -S -o test_cases/_verify_O2.ll test_cases/_verify.c

# View and confirm IR files exist and contain 'define' keyword
Select-String -Path "test_cases/_verify_O0.ll" -Pattern "define"
Select-String -Path "test_cases/_verify_O2.ll" -Pattern "define"

# Check for nsw flag in O2 but not O0
Select-String -Path "test_cases/_verify_O0.ll" -Pattern "nsw"
Select-String -Path "test_cases/_verify_O2.ll" -Pattern "nsw"

# Check for !dbg metadata (proves -g flag worked)
Select-String -Path "test_cases/_verify_O0.ll" -Pattern "!dbg"

# Cleanup
Remove-Item test_cases/_verify* -Force
```

### Phase 0 Gate Checklist
- [ ] `clang --version` prints 14+
- [ ] `python --version` prints 3.10+
- [ ] `pip install -r requirements.txt` succeeds
- [ ] IR files generated at both `-O0` and `-O2` with `!dbg` metadata present
- [ ] `nsw` flag visible in O2 IR for the test case

---

# Phase 1 — Compile Engine (Deliverable 1)

**Goal:** A Python module that compiles a `.c` file at `-O0` and `-O2`, returns per-function IR as a structured dict.

## Step 1.1 — Create `backend/utils/ir_parser.py`

This module handles parsing `.ll` files into per-function IR blocks.

```python
"""
ir_parser.py — Parse LLVM IR (.ll) files into per-function blocks.

[FIX #6] Uses balanced-brace matching instead of naive 'define' splitting.
Handles nested braces, metadata sections, and global declarations correctly.
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
    func_header = re.compile(
        r'define\s+[^@]*@([\w$.]+)\s*\([^)]*\)[^{]*\{'
    )

    for match in func_header.finditer(content):
        name = match.group(1)
        start = match.start()
        # Find matching closing brace with balanced counting
        depth = 0
        end = start
        for i in range(match.end() - 1, len(content)):
            if content[i] == '{':
                depth += 1
            elif content[i] == '}':
                depth -= 1
            if depth == 0:
                end = i + 1
                break
        functions[name] = content[start:end]

    return functions


def count_basic_blocks(func_ir: str) -> int:
    """Count basic blocks in a function's IR. Each label: line = 1 block,
    plus 1 for the entry block."""
    labels = re.findall(r'^\w[\w.]*:', func_ir, re.MULTILINE)
    return len(labels) + 1  # +1 for entry block


def count_conditional_branches(func_ir: str) -> int:
    """Count conditional branch instructions (br i1 ...)."""
    return len(re.findall(r'br\s+i1\s+', func_ir))


def count_unconditional_branches(func_ir: str) -> int:
    """Count unconditional branch instructions (br label ...)."""
    return len(re.findall(r'br\s+label\s+', func_ir))


def has_nsw_flag(func_ir: str) -> bool:
    """Check if any arithmetic instruction has the 'nsw' flag."""
    return bool(re.search(r'\b(add|sub|mul|shl)\s+nsw\b', func_ir))


def has_undef(func_ir: str) -> bool:
    """Check if 'undef' appears in value-producing positions.
    [FIX #12] Narrow detection — not just any occurrence of 'undef'."""
    return bool(re.search(r'(select|phi|ret)\s+.*\bundef\b', func_ir))


def has_null_check(func_ir: str) -> int:
    """Count null pointer comparisons (icmp eq/ne ... null)."""
    return len(re.findall(r'icmp\s+(?:eq|ne)\s+.*\bnull\b', func_ir))


def extract_dbg_lines(func_ir: str) -> list:
    """Extract source line numbers from !dbg metadata references."""
    dbg_refs = re.findall(r'!dbg\s+!(\d+)', func_ir)
    return dbg_refs


def get_source_location(func_ir: str, full_ll_content: str = "") -> Optional[dict]:
    """
    Extract source file and line number from debug metadata.
    Returns {"file": "...", "line": N} or None.
    """
    dbg_refs = re.findall(r'!dbg\s+!(\d+)', func_ir)
    if not dbg_refs and not full_ll_content:
        return None

    search_content = full_ll_content or func_ir
    for ref in dbg_refs:
        loc_match = re.search(
            rf'!{ref}\s*=\s*!DILocation\(line:\s*(\d+).*?(?:file:\s*"([^"]*)")?',
            search_content
        )
        if loc_match:
            return {
                "line": int(loc_match.group(1)),
                "file": loc_match.group(2) or "unknown"
            }
    return None
```

## Step 1.2 — Create `backend/core/compile_engine.py`

```python
"""
compile_engine.py — Differential Compilation Engine (Deliverable 1)

Compiles a C source file at -O0 and -O2, captures LLVM IR per function.

[FIX #1] All clang invocations include -g for debug metadata.
[FIX #2] All clang invocations include -fno-inline to prevent function disappearance.
[FIX #4] Uses subprocess list-form, never shell=True.
[FIX #8] Handles compilation failures gracefully.
"""
import subprocess
import tempfile
import os
from typing import Dict, Optional
from backend.utils.ir_parser import parse_ir_by_function


class CompilationError(Exception):
    """Raised when clang fails to compile the source file."""
    pass


# [FIX #7] Functions to skip in analysis (compiler-generated, entry points)
SKIP_FUNCTIONS = frozenset({
    "main", "__libc_csu_init", "__libc_csu_fini",
    "_start", "__do_global_dtors_aux", "frame_dummy",
    "register_tm_clones", "deregister_tm_clones",
    "__libc_start_main",
})


def _run_clang(
    source_path: str,
    opt_level: int,
    output_path: str,
    timeout: int = 30
) -> str:
    """
    Run clang to emit LLVM IR at the given optimization level.
    Returns the stderr output (warnings/errors).

    [FIX #1] -g flag included for debug metadata.
    [FIX #2] -fno-inline to preserve function boundaries.
    [FIX #4] List-form subprocess call, no shell=True.
    """
    cmd = [
        "clang",
        f"-O{opt_level}",
        "-g",                   # [FIX #1] Debug info for line numbers
        "-fno-inline",          # [FIX #2] Prevent inlining
        "-emit-llvm",
        "-S",
        "-Wno-everything",      # Suppress warnings in IR output
        "-o", output_path,
        source_path,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,       # [FIX #3] Timeout protection
        )
    except subprocess.TimeoutExpired:
        raise CompilationError(
            f"Clang timed out after {timeout}s at -O{opt_level}"
        )
    except FileNotFoundError:
        raise CompilationError(
            "Clang not found. Install LLVM: winget install LLVM.LLVM"
        )

    # [FIX #8] Handle compilation failures
    if result.returncode != 0:
        raise CompilationError(
            f"Clang failed at -O{opt_level}:\n{result.stderr}"
        )

    if not os.path.exists(output_path):
        raise CompilationError(
            f"Clang produced no output at -O{opt_level}: {output_path}"
        )

    return result.stderr


def compile_both(
    source_path: str,
    work_dir: Optional[str] = None,
    keep_ir: bool = False
) -> dict:
    """
    Compile a source file at -O0 and -O2, return structured per-function IR.

    Returns:
    {
        "source": "path/to/file.c",
        "functions": {
            "func_name": {
                "O0": "<full IR text>",
                "O2": "<full IR text>"
            },
            ...
        },
        "o0_only": ["func_inlined_at_o2", ...],
        "o2_only": ["func_name", ...],
        "raw_ir": {
            "O0_path": "...",
            "O2_path": "...",
            "O0_full": "...",
            "O2_full": "..."
        }
    }
    """
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Source file not found: {source_path}")

    # Create temp dir for IR output if not specified
    if work_dir is None:
        work_dir = tempfile.mkdtemp(prefix="ub_detector_")

    base = os.path.splitext(os.path.basename(source_path))[0]
    o0_path = os.path.join(work_dir, f"{base}_O0.ll")
    o2_path = os.path.join(work_dir, f"{base}_O2.ll")

    # Compile at both levels
    _run_clang(source_path, 0, o0_path)
    _run_clang(source_path, 2, o2_path)

    # Parse IR into per-function blocks
    o0_funcs = parse_ir_by_function(o0_path)
    o2_funcs = parse_ir_by_function(o2_path)

    # Read full IR content for metadata resolution
    with open(o0_path, "r", encoding="utf-8") as f:
        o0_full = f.read()
    with open(o2_path, "r", encoding="utf-8") as f:
        o2_full = f.read()

    # [FIX #7] Filter out compiler-generated functions
    all_names = set(o0_funcs.keys()) | set(o2_funcs.keys())
    user_functions = {n for n in all_names if n not in SKIP_FUNCTIONS}

    # Build paired dict
    functions = {}
    o0_only = []
    o2_only = []

    for name in user_functions:
        if name in o0_funcs and name in o2_funcs:
            functions[name] = {
                "O0": o0_funcs[name],
                "O2": o2_funcs[name],
            }
        elif name in o0_funcs:
            o0_only.append(name)
        else:
            o2_only.append(name)

    # Cleanup IR files unless requested to keep
    if not keep_ir:
        try:
            os.unlink(o0_path)
            os.unlink(o2_path)
            os.rmdir(work_dir)
        except OSError:
            pass

    return {
        "source": source_path,
        "functions": functions,
        "o0_only": o0_only,
        "o2_only": o2_only,
        "raw_ir": {
            "O0_path": o0_path if keep_ir else None,
            "O2_path": o2_path if keep_ir else None,
            "O0_full": o0_full,
            "O2_full": o2_full,
        }
    }
```

## Step 1.3 — Test Compile Engine

```powershell
cd "d:\UB Timebomb Detector"
.\venv\Scripts\Activate.ps1

# Quick smoke test
python -c "
from backend.core.compile_engine import compile_both

with open('test_cases/_test.c', 'w') as f:
    f.write('int f(int x) { return x + 1 > x; }\n')

result = compile_both('test_cases/_test.c')
print('Functions found:', list(result['functions'].keys()))
print('O0-only (inlined):', result['o0_only'])
for name, ir in result['functions'].items():
    print(f'--- {name} O0 (first 200 chars) ---')
    print(ir['O0'][:200])
    print(f'--- {name} O2 (first 200 chars) ---')
    print(ir['O2'][:200])

import os; os.unlink('test_cases/_test.c')
"
```

### Phase 1 Gate Checklist
- [ ] `compile_both()` returns a dict with function names as keys
- [ ] Both `O0` and `O2` IR text present for each function
- [ ] `!dbg` metadata present in the IR (proves `-g` works)
- [ ] `nsw` visible in O2 IR for `f(int x) { return x+1 > x; }`
- [ ] Functions like `main` are filtered out
- [ ] Compilation errors raise `CompilationError` with a clear message
- [ ] No crashes on valid C files

---

# Phase 2 — Behavioral Change Detector (Deliverable 2)

**Goal:** Compare O0 vs O2 per-function IR and detect structural changes (block loss, branch elimination, flag injection).

## Step 2.1 — Create `backend/core/change_detector.py`

```python
"""
change_detector.py — Behavioral Change Detector (Deliverable 2)

Compares -O0 and -O2 IR per function and detects structural changes.
"""
from typing import List, Dict, Any
from backend.utils.ir_parser import (
    count_basic_blocks,
    count_conditional_branches,
    count_unconditional_branches,
    has_nsw_flag,
    has_undef,
    has_null_check,
)


def detect_changes(compiled_result: dict) -> List[Dict[str, Any]]:
    """
    Analyze compiled IR and detect behavioral changes between -O0 and -O2.

    Input: Output of compile_both()
    Returns: List of changed functions with diff metadata.
    """
    changes = []

    for func_name, ir_pair in compiled_result["functions"].items():
        o0_ir = ir_pair["O0"]
        o2_ir = ir_pair["O2"]

        # Structural metrics
        blocks_o0 = count_basic_blocks(o0_ir)
        blocks_o2 = count_basic_blocks(o2_ir)
        branches_o0 = count_conditional_branches(o0_ir)
        branches_o2 = count_conditional_branches(o2_ir)

        # Flag changes
        nsw_o0 = has_nsw_flag(o0_ir)
        nsw_o2 = has_nsw_flag(o2_ir)
        nsw_added = nsw_o2 and not nsw_o0

        # Null check changes
        null_checks_o0 = has_null_check(o0_ir)
        null_checks_o2 = has_null_check(o2_ir)
        null_check_removed = null_checks_o0 > null_checks_o2

        # Undef changes [FIX #12: narrow detection]
        undef_o0 = has_undef(o0_ir)
        undef_o2 = has_undef(o2_ir)
        undef_exposed = undef_o2 and not undef_o0

        # Determine if there is a meaningful behavioral change
        block_loss = blocks_o2 < blocks_o0
        branch_eliminated = branches_o2 < branches_o0

        has_change = (
            block_loss or
            branch_eliminated or
            (nsw_added and branch_eliminated) or  # [FIX #11]
            null_check_removed or
            undef_exposed
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

            changes.append({
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
                },
                "ir": {
                    "O0": o0_ir,
                    "O2": o2_ir,
                }
            })

    # Also report inlined functions [FIX #2 related]
    for func_name in compiled_result.get("o0_only", []):
        changes.append({
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
            },
            "ir": {
                "O0": "",
                "O2": "[inlined — function not present at -O2]"
            },
            "note": f"Function '{func_name}' was inlined at -O2; cannot diff CFG."
        })

    return changes
```

### Phase 2 Gate Checklist
- [ ] `signed_overflow.c` reports `branch_elimination` + `nsw_flag_added`
- [ ] `null_deref.c` reports `block_loss` + `null_check_removed`
- [ ] Safe code `int f(int a){return a+1;}` reports NO changes (or only nsw without branch elim)
- [ ] Inlined functions produce an `inlined_at_O2` entry with info message

---

# Phase 3 — UB Pattern Classifier (Deliverable 3)

**Goal:** Classify each detected change into one of the 4 UB categories with severity and source location.

## Step 3.1 — Create `backend/utils/demangle.py`

```python
"""
demangle.py — C++ name demangling utility.
[FIX #10] Provides readable function names in reports.
"""
import subprocess


def demangle(name: str) -> str:
    """Demangle a C++ symbol name. Falls back to the mangled name."""
    if not name.startswith("_Z"):
        return name
    try:
        result = subprocess.run(
            ["c++filt", name],
            capture_output=True, text=True, timeout=5
        )
        demangled = result.stdout.strip()
        return demangled if demangled else name
    except (FileNotFoundError, subprocess.TimeoutExpired):
        try:
            result = subprocess.run(
                ["llvm-cxxfilt", name],
                capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip() or name
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return name
```

## Step 3.2 — Create `backend/core/ub_classifier.py`

```python
"""
ub_classifier.py — UB Pattern Classifier (Deliverable 3)

Classifies detected IR changes into specific UB categories.

[FIX #11] Signed overflow requires BOTH nsw flag AND branch elimination.
[FIX #12] Undef detection narrowed to value-producing positions only.
[FIX #13] Strict aliasing uses best-effort heuristic with documented limits.
"""
import re
from typing import List, Dict, Any, Optional
from backend.utils.ir_parser import get_source_location
from backend.utils.demangle import demangle


# UB category definitions
class UBCategory:
    SIGNED_OVERFLOW = "signed_overflow"
    NULL_DEREF = "null_deref"
    STRICT_ALIASING = "strict_aliasing"
    UNINITIALIZED = "uninitialized_use"
    UNKNOWN = "unknown"


# Severity levels
class Severity:
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# Fix suggestions per UB type
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


def _classify_signed_overflow(change: dict) -> bool:
    """
    [FIX #11] Require BOTH the nsw flag AND branch/block elimination.
    nsw alone is NOT sufficient — the optimizer adds nsw to safe code too.
    """
    metrics = change["metrics"]
    nsw_added = metrics["nsw_added"]
    branch_eliminated = metrics["branches_O2"] < metrics["branches_O0"]
    block_loss = metrics["blocks_O2"] < metrics["blocks_O0"]
    return nsw_added and (branch_eliminated or block_loss)


def _classify_null_deref(change: dict) -> bool:
    """Detect null check removal: null checks present at O0 but gone at O2."""
    metrics = change["metrics"]
    return (
        metrics["null_checks_O0"] > metrics["null_checks_O2"] and
        metrics["blocks_O2"] < metrics["blocks_O0"]
    )


def _classify_strict_aliasing(change: dict) -> bool:
    """
    [FIX #13] Best-effort heuristic for strict aliasing violations.
    Detects bitcast between incompatible pointer types + load removed.
    Limitation: Cannot detect instruction reordering (needs MemorySSA).
    """
    o0_ir = change["ir"]["O0"]
    o2_ir = change["ir"]["O2"]

    has_suspicious_bitcast = bool(re.search(
        r'bitcast\s+\w+\*\s+%\w+\s+to\s+\w+\*', o0_ir
    ))
    if not has_suspicious_bitcast:
        return False

    o0_loads = len(re.findall(r'load\s+\w+,\s+\w+\*', o0_ir))
    o2_loads = len(re.findall(r'load\s+\w+,\s+\w+\*', o2_ir))
    return o2_loads < o0_loads


def _classify_uninitialized(change: dict) -> bool:
    """
    [FIX #12] Detect uninitialized variable use.
    Checks for alloca at O0 + undef exposure at O2 in value positions.
    """
    o0_ir = change["ir"]["O0"]
    metrics = change["metrics"]

    has_alloca = "alloca" in o0_ir
    undef_exposed = metrics["undef_exposed"]

    return has_alloca and undef_exposed


def classify_diffs(
    changes: List[Dict[str, Any]],
    full_ir: Optional[dict] = None
) -> List[Dict[str, Any]]:
    """
    Classify each changed function into a UB category.

    Input: Output of detect_changes()
    Returns: List of UB findings with category, severity, and details.
    """
    findings = []

    for change in changes:
        func_name = change["function"]

        # Skip inlined functions — we can't classify them
        if "inlined_at_O2" in change.get("change_types", []):
            findings.append({
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
            })
            continue

        # Classification priority: overflow > null > uninit > aliasing > unknown
        if _classify_signed_overflow(change):
            category = UBCategory.SIGNED_OVERFLOW
            severity = Severity.CRITICAL
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

        # Extract source location from debug metadata
        location = None
        if full_ir:
            o0_full = full_ir.get("O0_full", "")
            location = get_source_location(change["ir"]["O0"], o0_full)

        findings.append({
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
        })

    return findings
```

### Phase 3 Gate Checklist
- [ ] `signed_overflow.c` classified as `signed_overflow` (CRITICAL)
- [ ] `null_deref.c` classified as `null_deref` (CRITICAL)
- [ ] `uninitialized.c` classified as `uninitialized_use` (HIGH)
- [ ] `strict_aliasing.c` classified as `strict_aliasing` (HIGH) or `unknown`
- [ ] Safe code `int f(int a){return a*2;}` produces NO findings
- [ ] Each finding has a `fix` suggestion string
- [ ] Each finding has a `confidence` field

---

# Phase 4 — Report Generator + FastAPI Server (Deliverable 4)

**Goal:** Generate JSON/text reports and expose the full pipeline via a REST API.

## Step 4.1 — Create `backend/core/report_generator.py`

```python
"""
report_generator.py — Source-Level Report Generator (Deliverable 4)

Generates JSON, plain-text, and HTML reports from classified findings.
"""
from typing import List, Dict, Any, Optional


SEVERITY_EMOJI = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🟢",
    "info": "ℹ️",
}

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def _read_source_lines(source_path: str) -> List[str]:
    """Read source file into lines list."""
    try:
        with open(source_path, "r", encoding="utf-8") as f:
            return f.readlines()
    except FileNotFoundError:
        return []


def _calc_risk_score(findings: List[Dict]) -> int:
    """Calculate an overall risk score from 0-100."""
    if not findings:
        return 0
    severity_weights = {"critical": 30, "high": 20, "medium": 10, "low": 5, "info": 0}
    total = sum(severity_weights.get(f["severity"], 0) for f in findings)
    return min(100, total)


def generate_report(
    findings: List[Dict[str, Any]],
    source_path: str,
    compiled_result: Optional[dict] = None,
) -> Dict[str, Any]:
    """
    Generate a full report object that can be serialized to JSON
    and consumed by both CLI and frontend.
    """
    source_lines = _read_source_lines(source_path)

    sorted_findings = sorted(
        findings,
        key=lambda f: SEVERITY_ORDER.get(f["severity"], 99)
    )

    enriched = []
    for finding in sorted_findings:
        loc = finding.get("location")
        snippet = ""
        if loc and loc.get("line") and source_lines:
            line_num = loc["line"]
            start = max(0, line_num - 2)
            end = min(len(source_lines), line_num + 2)
            snippet_lines = []
            for i in range(start, end):
                marker = ">>>" if i == line_num - 1 else "   "
                snippet_lines.append(f"{marker} {i+1:>4} | {source_lines[i].rstrip()}")
            snippet = "\n".join(snippet_lines)

        enriched.append({
            **finding,
            "source_snippet": snippet,
            "severity_icon": SEVERITY_EMOJI.get(finding["severity"], ""),
        })

    risk_score = _calc_risk_score(findings)

    category_counts = {}
    for f in findings:
        cat = f["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

    report = {
        "source_file": source_path,
        "source_lines": [l.rstrip() for l in source_lines],
        "total_findings": len(findings),
        "risk_score": risk_score,
        "risk_level": (
            "CRITICAL" if risk_score >= 70 else
            "HIGH" if risk_score >= 40 else
            "MEDIUM" if risk_score >= 20 else
            "LOW"
        ),
        "category_counts": category_counts,
        "findings": enriched,
        "functions_analyzed": len(compiled_result["functions"]) if compiled_result else 0,
        "functions_inlined": len(compiled_result.get("o0_only", [])) if compiled_result else 0,
    }

    return report


def report_to_text(report: dict) -> str:
    """Convert report to plain text format."""
    lines = []
    lines.append("=" * 60)
    lines.append("  UB TIME BOMB DETECTOR — ANALYSIS REPORT")
    lines.append("=" * 60)
    lines.append(f"  File: {report['source_file']}")
    lines.append(f"  Risk Score: {report['risk_score']}/100 ({report['risk_level']})")
    lines.append(f"  Functions Analyzed: {report['functions_analyzed']}")
    lines.append(f"  Time Bombs Found: {report['total_findings']}")
    lines.append("=" * 60)

    for i, f in enumerate(report["findings"], 1):
        lines.append("")
        icon = f.get("severity_icon", "")
        lines.append(f"[{icon} {f['severity'].upper()}] #{i} — {f['readable_name']}")
        lines.append(f"  Category : {f['category']}")
        lines.append(f"  Confidence: {f['confidence']}")

        if f.get("location"):
            loc = f["location"]
            lines.append(f"  Location : {loc.get('file', '?')}:{loc.get('line', '?')}")

        lines.append(f"  Detail   : {f['detail']}")
        lines.append(f"  Fix      : {f['fix']}")

        if f.get("source_snippet"):
            lines.append("  Code:")
            for sl in f["source_snippet"].split("\n"):
                lines.append(f"    {sl}")

        if f.get("metrics"):
            m = f["metrics"]
            lines.append(f"  Blocks   : O0={m['blocks_O0']}  O2={m['blocks_O2']}")
            lines.append(f"  Branches : O0={m['branches_O0']}  O2={m['branches_O2']}")

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)
```

## Step 4.2 — Create `backend/main.py` (FastAPI Server)

```python
"""
main.py — FastAPI server for UB Time Bomb Detector.

[FIX #5] Input validation, size limits, and timeout protection.
"""
import os
import shutil
import tempfile
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional

from backend.core.compile_engine import compile_both, CompilationError
from backend.core.change_detector import detect_changes
from backend.core.ub_classifier import classify_diffs
from backend.core.report_generator import generate_report, report_to_text


app = FastAPI(
    title="UB Time Bomb Detector",
    description="Static analysis tool for detecting undefined behavior time bombs in C/C++ code",
    version="1.0.0",
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# [FIX #5] Input validation
MAX_SOURCE_SIZE = 50_000  # 50 KB max


class AnalyzeRequest(BaseModel):
    """Request body for /analyze endpoint."""
    source_code: str = Field(..., max_length=MAX_SOURCE_SIZE)
    filename: Optional[str] = Field(default="input.c")


class AnalyzeFileRequest(BaseModel):
    """Request body for /analyze-file endpoint (file path on disk)."""
    file_path: str


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/analyze")
async def analyze_source(request: AnalyzeRequest):
    """
    Analyze C source code for UB time bombs.
    Accepts raw source code as a string, returns JSON report.
    """
    source_code = request.source_code

    if len(source_code) > MAX_SOURCE_SIZE:
        raise HTTPException(400, "Source code exceeds size limit")

    work_dir = tempfile.mkdtemp(prefix="ub_analyze_")
    source_path = os.path.join(work_dir, request.filename or "input.c")

    try:
        with open(source_path, "w", encoding="utf-8") as f:
            f.write(source_code)

        compiled = compile_both(source_path, work_dir=work_dir, keep_ir=True)
        changes = detect_changes(compiled)
        findings = classify_diffs(changes, full_ir=compiled.get("raw_ir"))
        report = generate_report(findings, source_path, compiled)

        return report

    except CompilationError as e:
        raise HTTPException(400, f"Compilation error: {str(e)}")
    except Exception as e:
        raise HTTPException(500, f"Analysis error: {str(e)}")
    finally:
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
        except Exception:
            pass


@app.post("/analyze-file")
async def analyze_file(request: AnalyzeFileRequest):
    """Analyze a C file from disk by path."""
    file_path = request.file_path

    if not os.path.exists(file_path):
        raise HTTPException(404, f"File not found: {file_path}")
    if not file_path.endswith(".c"):
        raise HTTPException(400, "Only .c files are supported")

    try:
        compiled = compile_both(file_path, keep_ir=True)
        changes = detect_changes(compiled)
        findings = classify_diffs(changes, full_ir=compiled.get("raw_ir"))
        report = generate_report(findings, file_path, compiled)
        return report

    except CompilationError as e:
        raise HTTPException(400, f"Compilation error: {str(e)}")
    except Exception as e:
        raise HTTPException(500, f"Analysis error: {str(e)}")


# Run with: uvicorn backend.main:app --reload --port 8000
```

## Step 4.3 — Test the full backend pipeline

```powershell
cd "d:\UB Timebomb Detector"
.\venv\Scripts\Activate.ps1

# Start the server
uvicorn backend.main:app --reload --port 8000
```

In a separate terminal:
```powershell
# Test with Invoke-RestMethod
$body = @{
    source_code = 'int f(int x) { return x + 1 > x; }'
    filename = "test.c"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/analyze" -Method POST -Body $body -ContentType "application/json" | ConvertTo-Json -Depth 10
```

### Phase 4 Gate Checklist
- [ ] `uvicorn backend.main:app` starts without errors
- [ ] `GET /health` returns `{"status": "ok"}`
- [ ] `POST /analyze` with signed overflow code returns findings with `signed_overflow` category
- [ ] Report includes `risk_score`, `findings`, `source_lines`, `category_counts`
- [ ] Compilation errors return HTTP 400 with descriptive message
- [ ] Oversized input returns HTTP 400

---

# Phase 5 — Test Cases (Deliverable 5)

**Goal:** Create the 5 canonical test C files and verify detection.

## Step 5.1 — Create all 5 test case files

**`test_cases/signed_overflow.c`**
```c
// Test Case 1: Signed Integer Overflow
// Expected: comparison eliminated at -O2
// UB: x + 1 > x is UB when x = INT_MAX
#include <limits.h>

int always_greater(int x) {
    return x + 1 > x;   // UB: signed overflow
}
```

**`test_cases/null_deref.c`**
```c
// Test Case 2: Null Pointer Dereference
// Expected: null check removed at -O2
// UB: dereferencing ptr before null check

int get_value(int *ptr) {
    int val = *ptr;       // UB if ptr is NULL
    if (ptr == 0)         // dead code at -O2
        return -1;
    return val;
}
```

**`test_cases/strict_aliasing.c`**
```c
// Test Case 3: Strict Aliasing Violation
// Expected: load may be reordered or dropped at -O2
// UB: accessing int memory through float pointer

int alias_bug(int *ip) {
    float *fp = (float *)ip;   // UB: strict aliasing
    *fp = 1.0f;
    return *ip;                 // may see stale value at -O2
}
```

**`test_cases/uninitialized.c`**
```c
// Test Case 4: Uninitialized Variable Use
// Expected: undef propagates at -O2
// UB: reading x before assignment

int f(void) {
    int x;
    return x + 1;   // UB: x is indeterminate
}
```

**`test_cases/loop_overflow.c`**
```c
// Test Case 5: Signed Overflow in Loop Bound
// Expected: loop exit condition removed at -O2
// UB: signed int i will overflow past INT_MAX
// WARNING: Do NOT execute this at -O2 — it becomes an infinite loop.

int count_up(int limit) {
    int count = 0;
    for (int i = 0; i < limit; i++) {
        if (i + 1 < 0) return -1;   // overflow guard removed at O2
        count++;
    }
    return count;
}
```

## Step 5.2 — Create batch test runner `eval/run_evaluation.py`

```python
"""
run_evaluation.py — Batch test runner for all test cases.
[FIX #3] Includes timeout protection for test cases that may hang.
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.compile_engine import compile_both, CompilationError
from backend.core.change_detector import detect_changes
from backend.core.ub_classifier import classify_diffs
from backend.core.report_generator import generate_report, report_to_text


TEST_CASES = [
    ("test_cases/signed_overflow.c", "signed_overflow"),
    ("test_cases/null_deref.c", "null_deref"),
    ("test_cases/strict_aliasing.c", "strict_aliasing"),
    ("test_cases/uninitialized.c", "uninitialized_use"),
    ("test_cases/loop_overflow.c", "signed_overflow"),
]


def run_single(source_path: str, expected_category: str) -> dict:
    """Run the full pipeline on a single test case."""
    try:
        compiled = compile_both(source_path, keep_ir=True)
        changes = detect_changes(compiled)
        findings = classify_diffs(changes, full_ir=compiled.get("raw_ir"))
        report = generate_report(findings, source_path, compiled)

        found_categories = [f["category"] for f in findings]
        detected = expected_category in found_categories

        return {
            "file": source_path,
            "expected": expected_category,
            "detected": detected,
            "found_categories": found_categories,
            "total_findings": len(findings),
            "report_text": report_to_text(report),
        }
    except CompilationError as e:
        return {
            "file": source_path,
            "expected": expected_category,
            "detected": False,
            "error": str(e),
        }


def main():
    print("=" * 60)
    print("  UB TIME BOMB DETECTOR — EVALUATION RUN")
    print("=" * 60)

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    results = []
    for source_path, expected in TEST_CASES:
        full_path = os.path.join(project_root, source_path)
        print(f"\n--- {source_path} (expected: {expected}) ---")
        result = run_single(full_path, expected)
        results.append(result)

        status = "CAUGHT" if result["detected"] else "MISSED"
        print(f"  Result: {status}")
        if "found_categories" in result:
            print(f"  Found: {result['found_categories']}")
        if "error" in result:
            print(f"  Error: {result['error']}")

    caught = sum(1 for r in results if r["detected"])
    total = len(results)
    print(f"\n{'=' * 60}")
    print(f"  SUMMARY: {caught}/{total} test cases detected")
    print(f"{'=' * 60}")

    output_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "evaluation_results.json"
    )
    with open(output_path, "w") as f:
        clean = []
        for r in results:
            c = {k: v for k, v in r.items() if k != "report_text"}
            clean.append(c)
        json.dump(clean, f, indent=2)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
```

### Phase 5 Gate Checklist
- [ ] All 5 `.c` files created in `test_cases/`
- [ ] `python eval/run_evaluation.py` runs without crashing
- [ ] `signed_overflow.c` CAUGHT
- [ ] `null_deref.c` CAUGHT
- [ ] `uninitialized.c` CAUGHT (or UNKNOWN — not signed_overflow)
- [ ] `strict_aliasing.c` CAUGHT or honestly documented as partial
- [ ] `loop_overflow.c` CAUGHT (as signed_overflow)
- [ ] No test case causes an infinite hang

---

# Phase 6 — Frontend Setup (React + Vite + Tailwind + shadcn)

**Goal:** Initialize the React frontend with all UI dependencies.

## Step 6.1 — Create Vite React project

```powershell
cd "d:\UB Timebomb Detector"
npx -y create-vite@latest frontend -- --template react
cd frontend
npm install
```

## Step 6.2 — Install Tailwind CSS

```powershell
cd "d:\UB Timebomb Detector\frontend"
npm install -D tailwindcss @tailwindcss/vite
```

Update `vite.config.js`:
```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  }
})
```

Replace `src/index.css` with:
```css
@import "tailwindcss";
```

## Step 6.3 — Install shadcn/ui dependencies

```powershell
cd "d:\UB Timebomb Detector\frontend"
npm install tailwind-merge clsx class-variance-authority lucide-react
```

Create `src/lib/utils.js`:
```js
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}
```

## Step 6.4 — Install Monaco Editor + Recharts

```powershell
cd "d:\UB Timebomb Detector\frontend"
npm install @monaco-editor/react recharts
```

## Step 6.5 — Verify frontend boots

```powershell
cd "d:\UB Timebomb Detector\frontend"
npm run dev
# Should open at http://localhost:5173
```

### Phase 6 Gate Checklist
- [ ] `npm run dev` starts without errors at `localhost:5173`
- [ ] Tailwind classes work (test with a `<div className="bg-red-500">`)
- [ ] Monaco Editor import resolves without error
- [ ] Recharts import resolves without error

---

# Phase 7 — Frontend Components

**Goal:** Build all dashboard UI components.

## Component Architecture

```
App.jsx
├── Header.jsx (title bar + file upload + analyze button)
├── StatsBar.jsx (4 stat cards: functions, bombs, CVE matches, risk score)
├── <main layout: 2-column grid>
│   ├── LEFT COLUMN
│   │   ├── SourceViewer.jsx (source code with line highlighting)
│   │   └── IRDiffViewer.jsx (Monaco side-by-side diff)
│   └── RIGHT COLUMN
│       ├── FindingsPanel.jsx (list of UB findings with severity badges)
│       └── ReportPanel.jsx (formatted text report)
├── CVEDatabase.jsx (5 CVE cards at bottom)
└── RiskGauge.jsx (used inside StatsBar)
```

## Step 7.1 — Create `src/hooks/useAnalysis.js`

```js
import { useState, useCallback } from 'react';

export function useAnalysis() {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const analyze = useCallback(async (sourceCode, filename = 'input.c') => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_code: sourceCode,
          filename: filename,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Analysis failed');
      }
      const data = await res.json();
      setReport(data);
      return data;
    } catch (e) {
      setError(e.message);
      throw e;
    } finally {
      setLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setReport(null);
    setError(null);
  }, []);

  return { report, loading, error, analyze, reset };
}
```

## Step 7.2 — Build each component

The agent should create these files in `src/components/`:

### `Header.jsx`
- Dark gradient top bar with ⚠️ UB TIME BOMB DETECTOR title
- Subtitle: Static undefined behavior analyzer for C/C++
- File upload button (accepts `.c` files)
- Analyze button (calls `useAnalysis.analyze()`)
- Use Tailwind: `bg-gradient-to-r from-gray-900 to-gray-800`, white text

### `StatsBar.jsx`
- 4 cards in a horizontal row:
  1. Functions Analyzed — count from `report.functions_analyzed`
  2. UB Bombs Detected — count from `report.total_findings`
  3. Risk Score — `report.risk_score` / 100
  4. Risk Level — `report.risk_level` with color coding
- Use glassmorphism cards: `bg-white/5 backdrop-blur-md border border-white/10 rounded-xl`

### `SourceViewer.jsx`
- Displays source code with line numbers
- Highlights lines that have findings (red background with glow)
- Uses a monospace font, dark background (`bg-gray-950`)
- When a finding is clicked in FindingsPanel, scrolls to that line

### `IRDiffViewer.jsx`
- Uses `@monaco-editor/react` `DiffEditor` component
- Left panel: O0 IR, Right panel: O2 IR
- Dark theme (`vs-dark`)
- Shows the IR of the currently selected finding's function
- Props: `{ o0IR: string, o2IR: string }`

### `FindingsPanel.jsx`
- Scrollable list of all findings
- Each finding shows:
  - Severity badge (CRITICAL / HIGH / MEDIUM / LOW)
  - Function name (readable/demangled)
  - UB category
  - Line number
  - Confidence badge
- Clicking a finding selects it (updates IRDiffViewer + SourceViewer highlight)

### `ReportPanel.jsx`
- Formatted text report panel
- Shows detail, fix suggestion, metrics for the selected finding
- Export Report button that downloads full text report

### `CVEDatabase.jsx`
- 5 cards at the bottom for the CVE test cases
- Each card shows: CVE ID, name, UB type, detection status
- Cards use gradient borders and subtle hover animations
- Clicking a card loads the CVE reproducer into the source editor

### `RiskGauge.jsx`
- Semi-circular gauge using Recharts PieChart
- Shows risk score 0-100
- Color: green (0-30), yellow (31-60), red (61-100)
- Animated fill on load

## Step 7.3 — Wire everything in `App.jsx`

```jsx
import { useState } from 'react';
import { useAnalysis } from './hooks/useAnalysis';
import Header from './components/Header';
import StatsBar from './components/StatsBar';
import SourceViewer from './components/SourceViewer';
import IRDiffViewer from './components/IRDiffViewer';
import FindingsPanel from './components/FindingsPanel';
import ReportPanel from './components/ReportPanel';
import CVEDatabase from './components/CVEDatabase';

function App() {
  const { report, loading, error, analyze, reset } = useAnalysis();
  const [sourceCode, setSourceCode] = useState('');
  const [selectedFinding, setSelectedFinding] = useState(null);

  const handleAnalyze = async () => {
    if (!sourceCode.trim()) return;
    try {
      const result = await analyze(sourceCode);
      if (result.findings.length > 0) {
        setSelectedFinding(result.findings[0]);
      }
    } catch (e) {
      // Error handled by hook
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <Header
        onAnalyze={handleAnalyze}
        onSourceChange={setSourceCode}
        loading={loading}
        error={error}
      />

      {report && (
        <>
          <StatsBar report={report} />

          <main className="grid grid-cols-1 lg:grid-cols-2 gap-4 p-4">
            <div className="space-y-4">
              <SourceViewer
                sourceLines={report.source_lines}
                findings={report.findings}
                selectedFinding={selectedFinding}
              />
              <IRDiffViewer
                o0IR={selectedFinding?.ir?.O0 || ''}
                o2IR={selectedFinding?.ir?.O2 || ''}
              />
            </div>

            <div className="space-y-4">
              <FindingsPanel
                findings={report.findings}
                selectedFinding={selectedFinding}
                onSelectFinding={setSelectedFinding}
              />
              <ReportPanel finding={selectedFinding} />
            </div>
          </main>

          <CVEDatabase onLoadCase={(code) => setSourceCode(code)} />
        </>
      )}
    </div>
  );
}

export default App;
```

### Phase 7 Gate Checklist
- [ ] All component files created and importable
- [ ] `npm run dev` renders the full layout without console errors
- [ ] Header shows title with file upload working
- [ ] StatsBar displays 4 cards with data or placeholders
- [ ] Monaco DiffEditor renders with dark theme
- [ ] FindingsPanel is scrollable with clickable items
- [ ] CVE cards render at bottom with hover effects

---

# Phase 8 — Integration & End-to-End Testing

**Goal:** Connect frontend to backend and verify the complete flow.

## Step 8.1 — Start both servers

**Terminal 1 — Backend:**
```powershell
cd "d:\UB Timebomb Detector"
.\venv\Scripts\Activate.ps1
uvicorn backend.main:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```powershell
cd "d:\UB Timebomb Detector\frontend"
npm run dev
```

## Step 8.2 — Test end-to-end flow

1. Open `http://localhost:5173` in browser
2. Paste signed overflow test case into the source editor
3. Click Analyze
4. Verify:
   - StatsBar updates with finding counts and risk score
   - FindingsPanel shows CRITICAL signed_overflow
   - SourceViewer highlights the offending line
   - IRDiffViewer shows O0 vs O2 IR side-by-side
   - ReportPanel shows detail, fix suggestion

## Step 8.3 — Test all 5 cases

Repeat with each test case from Phase 5. Document which ones are caught.

### Phase 8 Gate Checklist
- [ ] Frontend successfully calls backend `/api/analyze` endpoint
- [ ] No CORS errors in browser console
- [ ] Signed overflow case: full report renders correctly
- [ ] Null deref case: detected and displayed
- [ ] Source code highlighting corresponds to correct line numbers
- [ ] IR diff shows meaningful differences
- [ ] Export report button produces downloadable text file

---

# Phase 9 — CVE Evaluation Cases (Deliverable 5)

**Goal:** Create 5 CVE-inspired reproducers in `eval/cve_cases/` and document results.

## Step 9.1 — Create CVE reproducer files

Create each file in `eval/cve_cases/`. These are simplified analogies of the real CVEs. [FIX #14] Document them honestly as pattern reproductions, not literal CVE replays.

**The agent should create:**
1. `eval/cve_cases/gcc_bug_30475.c` — Signed overflow loop (from PDF)
2. `eval/cve_cases/cve_2009_1897.c` — Null deref with check removal (from PDF)
3. `eval/cve_cases/cve_2017_9798.c` — Uninitialized struct field read
4. `eval/cve_cases/cve_2014_3153.c` — Integer overflow in bounds check
5. `eval/cve_cases/cve_2018_6789.c` — Integer overflow + pointer aliasing

## Step 9.2 — Run CVE evaluation

```powershell
cd "d:\UB Timebomb Detector"
.\venv\Scripts\Activate.ps1
python eval/run_evaluation.py
```

## Step 9.3 — Document results

Create `eval/evaluation_report.md` with:
- For each CVE: caught / partial / missed + reasoning
- [FIX #18] Honest assessment — do NOT claim 100% detection
- Note strict aliasing limitations explicitly

### Phase 9 Gate Checklist
- [ ] All 5 CVE `.c` files compile without errors
- [ ] `run_evaluation.py` processes all 5 without crashing
- [ ] At least 3 of 5 detected (signed overflow + null deref expected catches)
- [ ] Results documented honestly with reasoning for misses

---

# Phase 10 — Polish, Tests & Documentation

**Goal:** Write tests, polish the UI, create final documentation.

## Step 10.1 — Write pytest tests

Create test files in `backend/tests/`:

**`test_compile_engine.py`** — Test that:
- Valid C file compiles and returns functions
- Invalid C file raises CompilationError
- `-g` metadata present in IR output
- `main` function filtered out

**`test_change_detector.py`** — Test that:
- Signed overflow shows branch elimination + nsw
- Null deref shows null check removal
- Safe code shows no changes

**`test_ub_classifier.py`** — Test that:
- Signed overflow classified correctly (not just nsw alone)
- Null deref classified correctly
- Safe code produces zero findings (false positive test)

```powershell
cd "d:\UB Timebomb Detector"
.\venv\Scripts\Activate.ps1
python -m pytest backend/tests/ -v
```

## Step 10.2 — Polish frontend

- Add loading spinner animation during analysis
- Add error toast/alert when compilation fails
- Add smooth transitions between states
- Ensure dark mode looks premium throughout
- Add keyboard shortcut: Ctrl+Enter to analyze
- Add sample code button (pre-loads signed overflow example)

## Step 10.3 — Write README.md

Include:
- Project description
- Screenshots of the dashboard
- Installation steps (Windows-focused) [FIX #9]
- Usage instructions (CLI + Dashboard)
- Architecture diagram
- Test results summary [FIX #18: honest metrics]

## Step 10.4 — Create .gitignore

```
venv/
node_modules/
__pycache__/
*.pyc
*.ll
.env
dist/
build/
*.egg-info/
eval/evaluation_results.json
```

## Step 10.5 — Final verification

```powershell
# Run backend tests
python -m pytest backend/tests/ -v

# Run evaluation
python eval/run_evaluation.py

# Start both servers and manually test in browser
uvicorn backend.main:app --port 8000
# In another terminal:
cd frontend && npm run dev
```

### Phase 10 Gate Checklist
- [ ] All pytest tests pass
- [ ] All 5 test cases produce expected results
- [ ] Dashboard renders correctly on `localhost:5173`
- [ ] README.md complete with install + usage instructions
- [ ] No hardcoded paths (uses relative paths throughout)
- [ ] `.gitignore` created

---

# Quick Command Reference

```powershell
# Activate Python env
cd "d:\UB Timebomb Detector"
.\venv\Scripts\Activate.ps1

# Start backend
uvicorn backend.main:app --reload --port 8000

# Start frontend
cd "d:\UB Timebomb Detector\frontend"
npm run dev

# Run tests
python -m pytest backend/tests/ -v

# Run evaluation
python eval/run_evaluation.py

# Quick single-file analysis (CLI)
python -c "
from backend.core.compile_engine import compile_both
from backend.core.change_detector import detect_changes
from backend.core.ub_classifier import classify_diffs
from backend.core.report_generator import generate_report, report_to_text

compiled = compile_both('test_cases/signed_overflow.c', keep_ir=True)
changes = detect_changes(compiled)
findings = classify_diffs(changes, full_ir=compiled.get('raw_ir'))
report = generate_report(findings, 'test_cases/signed_overflow.c', compiled)
print(report_to_text(report))
"
```

---

*End of implementation plan.*
