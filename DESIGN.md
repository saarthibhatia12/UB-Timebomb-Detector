# DESIGN — UB Time Bomb Detector

## Problem Statement

Undefined behavior (UB) in C/C++ is a class of program errors that compilers are legally allowed to ignore, exploit, or transform away. The danger is that code may appear to work correctly at low optimization levels (`-O0`), but silently break at `-O2` or higher when the optimizer uses UB assumptions to remove branches, fold constants, or eliminate safety checks. We call these latent bugs **"time bombs"** — they exist in the source today but only detonate when the compiler version changes, optimization flags change, or the codebase evolves.

**Goal:** Build a static analysis tool that reliably detects UB time bombs by observing *what the optimizer actually does* to the LLVM Intermediate Representation (IR), rather than relying on heuristics applied purely to source text.

---

## Core Approach: Differential IR Analysis

### Key Insight

The C standard grants compilers permission to assume code has no UB. When a compiler exploits this assumption to remove a branch or eliminate a check, it leaves a measurable **structural difference** between the IR at `-O0` and at `-O2`. We detect UB by detecting these structural differences.

### Pipeline Overview

```
Source .c File
      │
      ├──▶ clang -O0 -g -fno-inline -emit-llvm -S ──▶ Unoptimized IR (.ll)
      │                                                        │
      └──▶ clang -O2 -g -fno-inline -emit-llvm -S ──▶ Optimized IR (.ll)
                                                               │
                                                  ┌────────────▼────────────┐
                                                  │   Per-Function IR Split  │
                                                  │   (balanced-brace parse) │
                                                  └────────────┬────────────┘
                                                               │
                                            ┌──────────────────▼──────────────────┐
                                            │        Behavioral Change Detector    │
                                            │  • Basic block count diff            │
                                            │  • Conditional branch count diff     │
                                            │  • nsw/nuw flag injection            │
                                            │  • Null-check removal                │
                                            │  • undef exposure                    │
                                            └──────────────────┬──────────────────┘
                                                               │
                                            ┌──────────────────▼──────────────────┐
                                            │         UB Pattern Classifier        │
                                            │  signed_overflow / null_deref /      │
                                            │  strict_aliasing / uninitialized     │
                                            └──────────────────┬──────────────────┘
                                                               │
                                            ┌──────────────────▼──────────────────┐
                                            │         Report Generator             │
                                            │  JSON + text + source locations      │
                                            │  + fix suggestions                   │
                                            └─────────────────────────────────────┘
```

### Why LLVM IR and not AST or Source Text?

| Layer | Pro | Con |
|---|---|---|
| **Source text** | Easy to parse | Cannot see optimizer behavior; many UBs are syntactically legal |
| **Clang AST** | Rich type info | Still pre-optimization; misses IR-level transformations |
| **LLVM IR (our choice)** | Shows exactly what the optimizer does/removes | Requires Clang; IR format can change across versions |
| **Binary / assembly** | Post-optimization truth | Hard to map back to source; non-portable |

LLVM IR is the correct level because it's where the UB-driven transformations happen. It's also human-readable and has stable semantics across Clang versions.

---

## Module Design

### 1. Compile Engine (`backend/core/compile_engine.py`)

**Responsibility:** Invoke `clang` twice (at `-O0` and `-O2`) via subprocess, capture IR files, and parse them into per-function dictionaries.

**Design decisions:**
- **`-g` flag:** Includes DWARF debug metadata in IR (as `!DILocation` nodes). This lets us extract source file names and line numbers from the IR without a separate source pass.
- **`-fno-inline`:** Prevents functions from being inlined at `-O2`. Without this flag, small helper functions disappear from the `-O2` IR entirely, making a diff impossible.
- **`-Wno-everything`:** Suppresses clang warnings in IR output; we only care about the IR, not diagnostics.
- **List-form subprocess:** Never uses `shell=True`. Using a list avoids shell injection and correctly handles paths with spaces.
- **`SKIP_FUNCTIONS` set:** Filters out compiler-generated functions (`__libc_csu_init`, etc.) that always change between optimization levels but carry no user UB.

### 2. IR Parser (`backend/utils/ir_parser.py`)

**Responsibility:** Parse `.ll` files into per-function IR text blocks and extract structural metrics.

**Design decisions:**
- **Balanced-brace matching:** Instead of splitting on `define` lines naively (which breaks when function bodies contain nested braces), we walk the character sequence counting `{` and `}` depth. This correctly handles LLVM IR's nested metadata sections.
- **Regex-based metrics:** Basic block count, conditional branch count, `nsw`/`nuw` flag presence, null-check count, and `undef` exposure are extracted with targeted regexes rather than a full IR parser. This avoids a dependency on `llvmlite` (which requires a compiled LLVM library) and is fast enough for interactive use.

### 3. Behavioral Change Detector (`backend/core/change_detector.py`)

**Responsibility:** For each function present in both `-O0` and `-O2` IR, compute a diff of structural metrics and report which types of changes occurred.

**Change signals detected:**

| Signal | Meaning |
|---|---|
| `block_loss` | Optimizer removed basic blocks (dead code, constant-folded branches) |
| `branch_elimination` | Conditional branches (`br i1`) reduced — optimizer collapsed a check |
| `nsw_flag_added` | Optimizer added `nsw` (no signed wrap) annotation — assumes no overflow |
| `null_check_removed` | `icmp eq/ne ... null` present at `-O0`, gone at `-O2` |
| `undef_exposed` | `undef` value propagated into a return/select/phi at `-O2` |

### 4. UB Classifier (`backend/core/ub_classifier.py`)

**Responsibility:** Map detected change signals to one of the four UB categories.

**Classification rules:**

| UB Category | Required Signals |
|---|---|
| `signed_overflow` | `nsw_added` AND (`branch_elimination` OR `block_loss`) |
| `null_deref` | `null_check_removed` AND `block_loss` |
| `strict_aliasing` | Suspicious `bitcast` in O0 IR AND load eliminated at O2 |
| `uninitialized_use` | `undef_exposed` at O2 |

**Key design constraint:** `nsw_added` alone is insufficient for `signed_overflow`. The optimizer routinely annotates safe additions with `nsw`. Only when it also eliminates a branch (proving the overflow path is unreachable under its assumptions) is there a true time bomb.

### 5. Report Generator (`backend/core/report_generator.py`)

**Responsibility:** Assemble classified findings into a structured JSON report with human-readable descriptions, severity ratings, source locations, and fix suggestions.

**Design decisions:**
- Source locations are extracted from DWARF `!DILocation` metadata embedded in the IR.
- Severity assignment: `critical` for null deref and signed overflow, `high` for aliasing and uninitialized use.
- Fix suggestions are category-specific and actionable (e.g., "use `__builtin_add_overflow()`").

### 6. FastAPI Backend (`backend/main.py`)

**Responsibility:** Expose the analysis pipeline as an HTTP API.

**Endpoints:**
- `POST /analyze` — analyze source code from request body
- `POST /analyze-file` — analyze an on-disk `.c` file
- `GET /health` — liveness check
- `POST /ai-explain` — (optional) generate LLM explanation via Groq

---

## Alternatives Considered

### Alternative 1: Clang Static Analyzer / `scan-build`

Clang's built-in static analyzer runs on the AST and uses symbolic execution. It catches many UB cases but:
- Cannot see what the optimizer actually removes (it's pre-optimization)
- Produces many false positives on complex codebases
- Does not model the "time bomb" pattern (working now, broken with `-O2`)

We complement rather than replace static analyzers: our tool specifically catches optimizer-visible UB that static analyzers miss.

### Alternative 2: ASan / UBSan (Runtime Sanitizers)

AddressSanitizer and UndefinedBehaviorSanitizer are the gold standard for runtime UB detection:
- **Pros:** Zero false positives (only fires on actual execution paths)
- **Cons:** Requires a test suite with good coverage; misses UB that isn't exercised at runtime; doesn't predict optimizer exploitation

Our tool is complementary: we detect *structural UB risk* without requiring a test suite or runtime execution.

### Alternative 3: `llvmlite` / Full IR Parsing

Using `llvmlite` would give us a full IR parse tree with type information. We chose regex-based parsing because:
- `llvmlite` requires a compiled LLVM library (complex install, version-sensitive)
- The structural metrics we need (block counts, flag presence) are easily extracted with regexes
- Regex approach has zero additional system dependencies

### Alternative 4: Direct CFG Comparison with `opt --dot-cfg`

LLVM's `opt` tool can dump control flow graphs as Graphviz `.dot` files. Graph diffing would be precise but:
- Requires additional parsing and graph isomorphism logic
- Node labels change between `-O0` and `-O2` even for unchanged behavior
- Much higher implementation complexity for marginal accuracy gain in our target UB categories

### Alternative 5: Source-level Pattern Matching (cppcheck style)

Tools like `cppcheck` apply patterns directly to source text. This approach:
- Works without a compiler
- Catches many obvious bugs
- **Misses the key class:** optimizer-visible UB where the source *looks* correct but the optimizer's assumptions are violated

Our approach is strictly more powerful for detecting optimizer-exploited UB.

---

## Design Constraints and Limitations

1. **Clang required:** The tool requires Clang 14+ installed and on PATH. GCC emits different IR format.
2. **C only (primarily):** C++ works for simple cases, but complex templates/lambdas may not parse cleanly.
3. **Strict aliasing heuristic:** The strict aliasing detector uses a best-effort `bitcast` heuristic. Full detection would require MemorySSA analysis (not implemented).
4. **Inlined functions:** Functions inlined at `-O2` cannot be structurally diffed. The tool reports these as `inlined_at_O2` annotations.
5. **No interprocedural analysis:** Each function is analyzed independently; cross-function UB (e.g., aliasing through function arguments) may be missed.

---

## Security Considerations

- All `clang` invocations use list-form subprocess (no shell injection).
- Analyzed source code is written to a temporary directory and cleaned up after each run.
- The optional AI explanation feature (`/ai-explain`) sends excerpts of code and IR to Groq's API. This must only be used with non-sensitive code.
