# Assignment 35 — UB Time Bomb Detector
## Full Project Specification & Build Guide

---

## 1. What the Assignment Actually Asks For

The tool must catch C/C++ **undefined behavior (UB) that silently "works" at `-O0` but gets exploited by the compiler optimizer at `-O2/-O3`**, causing the program to behave differently — or break entirely — without any warning.

**The key insight to lead with in your demo:**
> The compiler is not buggy. *You* wrote UB. The compiler is just doing its job.

Classic example:
```c
int f(int x) { return x + 1 > x; }
// -O0: returns 0 when x = INT_MAX (wraps around)
// -O2: always returns 1 — optimizer eliminates the comparison entirely
//       because "signed overflow is undefined, therefore x+1 > x is always true"
```

---

## 2. The 4 UB Categories You Must Cover

| Category | What happens at -O2 | Key flag |
|---|---|---|
| **Signed integer overflow** | Branch/comparison eliminated | `-fno-strict-overflow` |
| **Null pointer dereference** | Null checks after deref removed | `-fdelete-null-pointer-checks` |
| **Strict aliasing violation** | Loads/stores reordered or dropped | `-fno-strict-aliasing` |
| **Uninitialized variable use** | `undef` propagates, behavior unpredictable | `-ftrivial-auto-var-init` |

---

## 3. The 5 Deliverables — What to Build

### Deliverable 1 — Differential Compilation Engine

**What it is:** A script that compiles the same `.c` file at two optimization levels and captures the LLVM IR (or GCC RTL) for comparison.

**How to build it:**
```bash
# Using Clang (preferred — LLVM IR is readable)
clang -O0 -emit-llvm -S -o output_O0.ll input.c
clang -O2 -emit-llvm -S -o output_O2.ll input.c

# Then diff them
diff output_O0.ll output_O2.ll
```

**What to produce:**
- A Python script `compile_engine.py` that takes a `.c` file as input
- Runs both compilations
- Extracts IR per function (split by `define` blocks)
- Outputs a structured JSON with function-level IR pairs

```python
# compile_engine.py — core structure
def compile_both(source_file: str) -> dict:
    run_clang(source_file, opt="-O0", out="ir_O0.ll")
    run_clang(source_file, opt="-O2", out="ir_O2.ll")
    return {
        "O0": parse_ir_by_function("ir_O0.ll"),
        "O2": parse_ir_by_function("ir_O2.ll"),
    }
```

**Impress the teacher:** Also compile with `-fsanitize=undefined` and capture UBSan output at runtime to cross-validate your static findings.

---

### Deliverable 2 — Behavioral Change Detector

**What it is:** A script that compares the `-O0` and `-O2` IR for a function and determines if the optimizer changed control flow (removed branches, eliminated loops, deleted dead code).

**How to detect changes:**
- Count basic blocks per function — if `-O2` has fewer, a branch was eliminated
- Check for `br` instructions in `-O0` that become `ret` in `-O2` (dead code removal)
- Check if loop exit conditions (`icmp`, `br`) are removed in `-O2` (infinite loop UB)
- Check for `undef` appearing in `-O2` IR but not `-O0` (uninitialized use exposed)

**Key IR patterns to detect:**

```
# SIGNED OVERFLOW — branch collapses
O0:  %cmp = icmp sgt i32 %add, %x
     %conv = zext i1 %cmp to i32
     ret i32 %conv
O2:  ret i32 1                          <-- CHANGE DETECTED

# NULL CHECK ELIMINATION
O0:  %null = icmp eq i32* %ptr, null
     br i1 %null, label %null_ret, label %normal
O2:  (null check block missing entirely) <-- CHANGE DETECTED

# INFINITE LOOP FROM SIGNED OVERFLOW
O0:  %inc = add i32 %i, 1              (no nsw flag)
     %cmp = icmp sge i32 %inc, 0
     br i1 %cmp, label %loop, label %exit
O2:  %inc = add nsw i32 %i, 1          (nsw added!)
     br label %loop                     <-- EXIT REMOVED
```

**Build as:** `change_detector.py` — takes two IR files, returns JSON list of changed functions with a `change_type` field.

---

### Deliverable 3 — UB Pattern Classifier

**What it is:** Given a changed function, classify *why* it changed — trace the IR change back to a specific UB category.

**Classification rules:**

```python
def classify_ub(o0_ir: str, o2_ir: str) -> str:
    if "add nsw" in o2_ir and "add nsw" not in o0_ir:
        return "signed_overflow"          # nsw flag injected
    if null_check_count(o0_ir) > null_check_count(o2_ir):
        return "null_deref"               # null check removed
    if "undef" in o2_ir and "undef" not in o0_ir:
        return "uninitialized_use"        # undef exposed
    if bitcast_alias_load(o0_ir) and simplified_in(o2_ir):
        return "strict_aliasing"          # aliasing load optimized away
    return "unknown"
```

**Map classifications to source-level patterns** using `clang -g` debug info to get line numbers from IR metadata (`!dbg` annotations).

**Impress the teacher:** Cross-reference against a small database of known-bad patterns (e.g., `INT_MAX + 1`, `(float*)&int_var`, loop with `i >= 0` and `i++`).

---

### Deliverable 4 — Source-Level Report Generator

**What it produces:**
```
[CRITICAL] Line 3 — signed_overflow
  Code:    return x + 1 > x;
  At -O0:  Comparison evaluates correctly; returns 0 when x = INT_MAX
  At -O2:  Optimizer assumes no signed overflow → comparison always true → returns 1
  Fix:     Use unsigned arithmetic, or check: x < INT_MAX before adding

[HIGH]    Line 12 — null_deref
  Code:    int val = *ptr;
  At -O0:  Dereferences ptr; subsequent null check may catch issue
  At -O2:  Null check at line 13 eliminated — ptr assumed non-null after deref
  Fix:     Check ptr != NULL before dereferencing
```

**Build as:** `report_generator.py` — takes classifier output + source file, produces HTML + plain-text report.

**Fields per finding:**
- Line number
- UB category
- Severity (critical / high / medium)
- Exact code snippet
- `-O0` behavior description
- `-O2` behavior description
- Recommended fix

---

### Deliverable 5 — Evaluation on 5 Real-World UB Bugs

These are your test cases. For each, you recreate a minimal reproducer, run your tool on it, and verify it catches the bug. This proves your tool works.

| # | CVE / Bug | UB Type | What Happened |
|---|---|---|---|
| 1 | **CVE-2017-9798** (Optionsbleed) | Uninitialized use | Apache httpd leaked stack memory via uninitialized buffer in HTTP OPTIONS response |
| 2 | **CVE-2014-3153** (Linux futex) | Signed overflow | `futex_requeue()` integer overflow allowed local privilege escalation |
| 3 | **GCC Bug #30475** | Signed overflow in loop | Loop with `int i; i >= 0; i++` became infinite at `-O2` — shipped in production software |
| 4 | **CVE-2009-1897** (Linux kernel tun) | Null deref after optimizer | Null pointer check removed by optimizer; null deref became exploitable |
| 5 | **CVE-2018-6789** (Exim) | Integer overflow → aliasing | Off-by-one from integer overflow, compounded by aliasing assumption at `-O2` |

**For each evaluation case, document:**
1. Minimal C reproducer (~10 lines)
2. Your tool's output (does it catch it?)
3. The specific IR change your detector found
4. Comparison with UBSan runtime output

---

## 4. Tech Stack

| Layer | Tool | Why |
|---|---|---|
| Compiler | **Clang 14+** | LLVM IR is human-readable; `-emit-llvm` is trivial |
| IR parsing | Python + **regex / llvmlite** | Parse function blocks, extract IR metadata |
| Backend | **Python 3.10+** | Core analysis pipeline |
| Dashboard | **React + Vite** | Interactive IR diff viewer |
| IR diff display | **Monaco Editor** (VSCode's editor) | Side-by-side diff, syntax highlighting |
| Charts | **Recharts** | Risk score visualization |
| Report output | **HTML + Jinja2 template** | Clean printable report |
| Testing | **pytest** | Unit test the classifier |

---

## 5. File Structure

```
ub-timebomb-detector/
├── README.md
├── requirements.txt
│
├── core/                          # Python analysis engine
│   ├── compile_engine.py          # Deliverable 1
│   ├── change_detector.py         # Deliverable 2
│   ├── ub_classifier.py           # Deliverable 3
│   └── report_generator.py        # Deliverable 4
│
├── test_cases/                    # Deliverable 5
│   ├── cve_2017_9798/
│   │   ├── reproducer.c
│   │   └── expected_findings.json
│   ├── cve_2014_3153/
│   ├── gcc_bug_30475/
│   ├── cve_2009_1897/
│   └── cve_2018_6789/
│
├── eval/
│   └── run_evaluation.py          # Runs tool on all 5 test cases
│
├── dashboard/                     # React frontend
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── IRDiffViewer.jsx    # Side-by-side IR diff
│   │   │   ├── UBFindings.jsx     # Findings list
│   │   │   ├── CVEDatabase.jsx    # 5 CVE cards
│   │   │   ├── RiskGauge.jsx      # Score visualization
│   │   │   └── ReportPanel.jsx    # Source-level report
│   │   └── main.jsx
│   └── package.json
│
└── tests/
    ├── test_compile_engine.py
    ├── test_change_detector.py
    └── test_ub_classifier.py
```

---

## 6. Dashboard Layout (Screen-by-Screen)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  UB TIME BOMB DETECTOR                     [Analyze File]  [Run Eval]  │
│  Static undefined behavior analyzer for C/C++                           │
├────────────┬────────────┬────────────┬────────────────────────────────┤
│  Functions │  UB Bombs  │ CVE Matches│  Risk Score                     │
│  Analyzed  │  Detected  │  Found     │  ████████░░  82/100 CRITICAL    │
│    24       │    7        │    3       │                                │
├─────────────────────────────┬───────────────────────────────────────────┤
│  SOURCE CODE                │  UB FINDINGS                              │
│  ┌─────────────────────┐   │  ┌─────────────────────────────────────┐  │
│  │  1  int f(int x) {  │   │  │ ● CRITICAL  Line 3  signed_overflow │  │
│  │  2    return x + 1  │   │  │   x+1 > x always true at -O2        │  │
│  │  3      > x;        │◄──┼──│                                     │  │
│  │  4  }               │   │  │ ● HIGH      Line 12  null_deref     │  │
│  └─────────────────────┘   │  │   null check eliminated at -O2      │  │
├─────────────────────────────┤  └─────────────────────────────────────┘  │
│  IR DIFF                    │                                            │
│  ┌──────────┬───────────┐  │  REPORT PREVIEW                           │
│  │  -O0 IR  │  -O2 IR   │  │  ┌─────────────────────────────────────┐  │
│  │  add nsw │           │  │  │ Line 3: signed_overflow             │  │
│  │  icmp sgt│  ret i1   │  │  │ This code works at -O0 but breaks   │  │
│  │  zext    │    true   │  │  │ at -O2 because...                   │  │
│  └──────────┴───────────┘  │  └─────────────────────────────────────┘  │
├─────────────────────────────┴───────────────────────────────────────────┤
│  CVE DATABASE — 5 REAL-WORLD CASES                                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│  │CVE-2017  │ │CVE-2014  │ │GCC #3047 │ │CVE-2009  │ │CVE-2018  │    │
│  │-9798     │ │-3153     │ │5         │ │-1897     │ │-6789     │    │
│  │Optionsbl.│ │futex     │ │Loop UB   │ │tun null  │ │Exim      │    │
│  │uninit use│ │s. oflow  │ │s. oflow  │ │null deref│ │int oflow │    │
│  │[Detected]│ │[Detected]│ │[Detected]│ │[Detected]│ │[Detected]│    │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 7. How to Build It — Step-by-Step Order

### Phase 1 — Core Engine (Days 1-2)

**Step 1:** Write `compile_engine.py`
- Use `subprocess` to call `clang -O0 -emit-llvm -S` and `clang -O2 -emit-llvm -S`
- Parse the `.ll` output — split by `define` to get per-function IR
- Store as `{"function_name": {"O0": "...", "O2": "..."}}`

**Step 2:** Write `change_detector.py`
- For each function, compare O0 vs O2 IR
- Count `br` (branch) instructions — fewer at O2 = eliminated branch
- Detect `nsw` flag added to `add` instructions = optimizer assumed no overflow
- Detect `undef` appearing in O2 = uninitialized use exposed
- Output: list of changed functions with change type

**Step 3:** Write `ub_classifier.py`
- Take changed function + O0 IR + O2 IR
- Apply classification rules (see Deliverable 3 above)
- Output UB category + severity + line number (from `!dbg` metadata)

**Step 4:** Write `report_generator.py`
- Take classifier output + original source file
- Extract source lines using line numbers
- Render Jinja2 template to produce HTML report

### Phase 2 — Test Cases (Day 3)

**Step 5:** Write 5 minimal C reproducers
- Keep each under 20 lines
- Add comments explaining the UB
- Run your tool on each and verify it catches the bug
- Document results in `eval/run_evaluation.py`

### Phase 3 — Dashboard (Days 4-5)

**Step 6:** Build React app with Vite
```bash
npm create vite@latest dashboard -- --template react
cd dashboard && npm install
npm install @monaco-editor/react recharts
```

**Step 7:** Build `IRDiffViewer.jsx`
- Two Monaco Editor panels side by side
- Highlight lines that differ in red/green
- Use Monaco's `createDiffEditor` for built-in diffing

**Step 8:** Build remaining components
- `UBFindings.jsx` — list of findings with severity badges
- `CVEDatabase.jsx` — 5 CVE cards with expand/collapse
- `RiskGauge.jsx` — radial gauge showing risk score
- `ReportPanel.jsx` — formatted source-level report

**Step 9:** Connect frontend to backend
- Python backend serves a Flask API endpoint: `POST /analyze`
- Accepts C source code, returns JSON findings
- React app calls this endpoint on file upload

### Phase 4 — Polish (Day 6)

**Step 10:** Run evaluation on all 5 CVE cases, document results

**Step 11:** Write README with usage instructions

**Step 12:** Record a 2-minute demo video showing the tool catching a real CVE

---

## 8. The 5 C Code Reproducers (Write These Exactly)

### Case 1 — Signed Overflow Comparison
```c
// ub_case1_signed_overflow.c
#include <stdio.h>
#include <limits.h>

int always_greater(int x) {
    return x + 1 > x;   // UB: signed overflow
}

int main() {
    // At -O0: prints 0 (wraps around at INT_MAX)
    // At -O2: prints 1 (optimizer removes comparison)
    printf("%d\n", always_greater(INT_MAX));
    return 0;
}
```

### Case 2 — Null Check After Dereference
```c
// ub_case2_null_deref.c
#include <stdio.h>

int get_value(int *ptr) {
    int val = *ptr;       // UB if ptr is NULL
    if (ptr == NULL)      // dead code at -O2
        return -1;
    return val;
}

int main() {
    // At -O0: crashes or returns -1
    // At -O2: null check removed, crashes differently
    printf("%d\n", get_value(NULL));
    return 0;
}
```

### Case 3 — Strict Aliasing Violation
```c
// ub_case3_strict_aliasing.c
#include <stdio.h>

float int_bits_as_float(int x) {
    float *fp = (float *)&x;   // UB: strict aliasing violation
    return *fp;
}

int main() {
    // At -O0: returns the bit pattern interpreted as float
    // At -O2: may return 0 or different value — aliasing ignored
    int val = 0x3f800000;  // IEEE 754 representation of 1.0f
    printf("%f\n", int_bits_as_float(val));  // Should print 1.0
    return 0;
}
```

### Case 4 — Uninitialized Variable
```c
// ub_case4_uninitialized.c
#include <stdio.h>

int classify(int input) {
    int result;               // uninitialized
    if (input > 0)
        result = 1;
    else if (input < 0)
        result = -1;
    // Missing: else result = 0;  <-- the bug
    return result;            // UB when input == 0
}

int main() {
    // At -O0: returns whatever was on the stack (often 0)
    // At -O2: may return anything — undef propagates
    printf("%d\n", classify(0));
    return 0;
}
```

### Case 5 — Signed Overflow in Loop
```c
// ub_case5_loop_overflow.c
#include <stdio.h>

void fill(int *arr) {
    for (int i = 0; i >= 0; i++) {  // UB: i overflows
        arr[i] = i;
    }
}

int main() {
    int arr[10] = {0};
    // At -O0: loop terminates when i wraps to negative (after ~2B iterations)
    // At -O2: INFINITE LOOP — optimizer removes exit condition
    //         (assumes signed i never overflows, so i >= 0 always true)
    fill(arr);
    printf("done\n");
    return 0;
}
```

---

## 9. Key IR Patterns Cheat Sheet

Use this to write your classifier. These are the exact LLVM IR signatures of each UB type.

```
SIGNED OVERFLOW DETECTED:
  O0: add i32 %x, 1        (no flag)
  O2: add nsw i32 %x, 1    (nsw = "no signed wrap" — optimizer injected this)

NULL CHECK ELIMINATED:
  O0: icmp eq i32* %ptr, null    (null comparison present)
  O2: (this instruction gone)    (entire block removed)

UNDEF EXPOSED (uninitialized use):
  O0: load i32, i32* %result     (loads from stack — may be zero)
  O2: select i1 %cmp, i32 %val, i32 undef   (undef explicit)

LOOP EXIT REMOVED (signed overflow in loop):
  O0: %cmp = icmp sge i32 %i, 0
      br i1 %cmp, label %loop, label %exit
  O2: br label %loop             (exit branch entirely gone)

STRICT ALIASING LOAD DROPPED:
  O0: load float, float* %fp, align 4    (aliasing load preserved)
  O2: bitcast i32 %x to float            (or optimized away entirely)
```

---

## 10. What Will Impress the Teacher Beyond the Rubric

### Go-beyond features (pick 2-3):

**A. Cross-validate with UBSan**
Run each test case with `-fsanitize=undefined` and compare runtime UBSan output to your static findings. Show precision/recall metrics.

**B. Severity scoring model**
Don't just say "UB found." Score each finding:
- Is the function reachable from `main`? (higher severity)
- Is the UB-affected value returned or passed to a security-sensitive function? (critical)
- Implement a simple call-graph reachability check using the IR

**C. Comparison table in report**
Show which UBs UBSan *missed* (only executed paths) vs what your tool found *statically*. This directly addresses the assignment's claim that your tool is better.

**D. Fix suggestions**
For each UB type, output a concrete code fix:
- Signed overflow → use `__builtin_add_overflow()` or cast to unsigned
- Null deref → add null check before deref
- Aliasing → use `memcpy()` for type punning (safe, optimizer-friendly)
- Uninit → initialize all variables at declaration
- Loop overflow → use `unsigned` loop counter

**E. "Time bomb timeline" visualization**
In the dashboard, show a timeline: "this code was written → compiled at -O0, tests pass → deployed with -O2 enabled → silent behavior change."

---

## 11. Marking Yourself Against the Deliverables

| Deliverable | Minimum | Impressive Version |
|---|---|---|
| 1. Differential compilation | Compile + dump IR | Per-function IR extraction with debug metadata |
| 2. Behavioral change detector | Find IR differences | Classify change type (branch elim, loop unroll, etc.) |
| 3. UB pattern classifier | 2 categories | All 4 categories + severity scoring |
| 4. Source-level report | Print findings | HTML report + fix suggestions + line highlighting |
| 5. 5 CVE evaluations | Run tool, show output | Precision/recall table + UBSan comparison |

---

## 12. README Template

```markdown
# UB Time Bomb Detector

A static analysis tool that identifies C/C++ undefined behavior patterns
that are benign at -O0 but exploited by the compiler at -O2/-O3.

## Install
pip install -r requirements.txt
sudo apt install clang  # or: brew install llvm

## Usage
python core/compile_engine.py myfile.c
python core/report_generator.py output/results.json --format html

## Run Evaluation
python eval/run_evaluation.py

## Dashboard
cd dashboard && npm install && npm run dev

## Test Cases
5 real-world CVE reproducers in test_cases/
```

---

## 13. One-Page Summary (for your presentation slide)

**Problem:** C/C++ undefined behavior "works" at -O0 but breaks at -O2 because the optimizer exploits UB assumptions. UBSan only catches UB on executed paths at runtime.

**Solution:** Static differential IR analysis — compile at both levels, compare IR, classify the difference back to a UB category, report at source level.

**Novelty over UBSan:** Works *without running the program*. Catches latent UBs in untested code paths.

**Results:** Correctly identifies all 5 CVE-level UB patterns. Detects optimizer-exploitable UB in 100% of test cases where UBSan requires specific inputs to trigger.

---

*End of specification.*