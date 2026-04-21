# ⚠️ UB Time Bomb Detector

A static analysis tool that detects **undefined behavior (UB) time bombs** in C/C++ code by comparing LLVM IR generated at `-O0` vs `-O2`. When the optimizer exploits UB assumptions to eliminate branches, remove null checks, or fold computations, this tool catches it — before it blows up in production.

---

## How It Works

```
Source Code (.c)
     │
     ├──▶ clang -O0 -g -fno-inline -emit-llvm -S  →  Unoptimized IR
     │
     └──▶ clang -O2 -g -fno-inline -emit-llvm -S  →  Optimized IR
                    │
                    ▼
          ┌─────────────────────┐
          │  Behavioral Change  │  Compare per-function IR:
          │     Detector        │  blocks, branches, flags
          └────────┬────────────┘
                   │
                   ▼
          ┌─────────────────────┐
          │   UB Pattern        │  Classify into:
          │   Classifier        │  overflow, null deref, aliasing, uninit
          └────────┬────────────┘
                   │
                   ▼
          ┌─────────────────────┐
          │  Report Generator   │  JSON + text reports with
          │                     │  source locations & fix suggestions
          └─────────────────────┘
```

**Key insight:** If the optimizer changes the behavior of your function (removes branches, eliminates checks), it's exploiting an assumption that your code has no UB. If that assumption is wrong, you have a **time bomb** — code that works today but breaks with the next compiler upgrade.

---

## UB Categories Detected

| Category | Severity | Detection Method |
|---|---|---|
| **Signed Integer Overflow** | 🔴 Critical | `nsw` flag + branch elimination, or signed add/compare folded to constant |
| **Null Pointer Dereference** | 🔴 Critical | Null check present at O0, removed at O2 |
| **Strict Aliasing Violation** | 🟠 High | Type-punned store/load with load eliminated at O2 |
| **Uninitialized Variable Use** | 🟠 High | `alloca` without store + `undef` exposure at O2 |

---

## Quick Start

### Prerequisites

- **Python 3.10+**
- **Clang/LLVM 14+** (tested with Clang 22)

```powershell
# Verify clang is installed
clang --version

# If not installed (Windows):
winget install LLVM.LLVM
```

### Install

```powershell
cd "UB-Timebomb-Detector"
pip install -r requirements.txt
```

### Run the Evaluation Suite

```powershell
python eval/run_evaluation.py
```

Expected output:
```
============================================================
  UB TIME BOMB DETECTOR — EVALUATION RUN
============================================================

--- test_cases/signed_overflow.c (expected: signed_overflow) ---
  Result: CAUGHT

--- test_cases/null_deref.c (expected: null_deref) ---
  Result: CAUGHT

--- test_cases/strict_aliasing.c (expected: strict_aliasing) ---
  Result: CAUGHT

--- test_cases/uninitialized.c (expected: uninitialized_use) ---
  Result: CAUGHT

--- test_cases/loop_overflow.c (expected: signed_overflow) ---
  Result: CAUGHT

============================================================
  SUMMARY: 5/5 test cases detected
============================================================
```

### Start the API Server

```powershell
uvicorn backend.main:app --reload --port 8000
```

### Analyze Code via API

```powershell
# Health check
Invoke-RestMethod http://localhost:8000/health

# Analyze source code (PowerShell native)
$body = @{
    source_code = 'int f(int x) { return x + 1 > x; }'
    filename = "test.c"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/analyze" `
  -Method POST -Body $body -ContentType "application/json"
```

Or with `curl.exe` (note the escaped quotes for PowerShell):
```powershell
curl.exe -X POST http://localhost:8000/analyze `
  -H "Content-Type: application/json" `
  -d "{\"source_code\": \"int f(int x) { return x + 1 > x; }\", \"filename\": \"test.c\"}"
```

### Analyze a File from Disk

```powershell
$body = @{ file_path = "test_cases/signed_overflow.c" } | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8000/analyze-file" `
  -Method POST -Body $body -ContentType "application/json"
```

---

## Test Cases

| File | UB Type | What Happens |
|---|---|---|
| `signed_overflow.c` | `x + 1 > x` | O2 folds to `return 1` (always true — ignoring INT_MAX) |
| `null_deref.c` | deref before null check | O2 removes the null check as dead code |
| `strict_aliasing.c` | `float*` → `int*` punning | O2 returns stale/reinterpreted value |
| `uninitialized.c` | `int x; return x+1;` | O2 propagates `undef`/poison |
| `loop_overflow.c` | overflow guard in loop | O2 removes the `i+1 < 0` safety check |

---

## API Reference

### `GET /health`
Returns `{"status": "ok"}`.

### `POST /analyze`
Analyze C source code from request body.

**Request:**
```json
{
  "source_code": "int f(int x) { return x + 1 > x; }",
  "filename": "test.c"
}
```

**Response:**
```json
{
  "source_file": "...",
  "total_findings": 1,
  "risk_score": 30,
  "risk_level": "MEDIUM",
  "category_counts": {"signed_overflow": 1},
  "findings": [
    {
      "function": "f",
      "readable_name": "f",
      "category": "signed_overflow",
      "severity": "critical",
      "confidence": "HIGH",
      "detail": "Signed add/compare at -O0 was folded to a constant...",
      "fix": "Use unsigned arithmetic, or __builtin_add_overflow()...",
      "location": {"file": "test.c", "line": 1},
      "source_snippet": "...",
      "metrics": { "blocks_O0": 2, "blocks_O2": 1, ... }
    }
  ]
}
```

### `POST /analyze-file`
Analyze an existing `.c` file by path.

**Request:**
```json
{"file_path": "test_cases/signed_overflow.c"}
```

---

## Project Structure

```
UB-Timebomb-Detector/
├── README.md
├── requirements.txt
├── implementation_plan.md
│
├── backend/
│   ├── main.py                  ← FastAPI server
│   ├── core/
│   │   ├── compile_engine.py    ← Differential compilation (O0 vs O2)
│   │   ├── change_detector.py   ← IR structural diff analysis
│   │   ├── ub_classifier.py     ← UB pattern classification
│   │   └── report_generator.py  ← JSON/text report generation
│   └── utils/
│       ├── ir_parser.py         ← LLVM IR parsing & pattern matching
│       └── demangle.py          ← C++ name demangling
│
├── test_cases/                  ← 5 canonical UB test files
│   ├── signed_overflow.c
│   ├── null_deref.c
│   ├── strict_aliasing.c
│   ├── uninitialized.c
│   └── loop_overflow.c
│
└── eval/
    ├── run_evaluation.py        ← Batch test runner
    └── evaluation_results.json  ← Latest results
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.10+, FastAPI, uvicorn |
| Compiler | Clang/LLVM (14+ tested through 22) |
| IR Parsing | Python regex (no llvmlite dependency) |
| Testing | pytest, custom evaluation harness |

---

## License

MIT
