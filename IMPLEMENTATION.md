# IMPLEMENTATION — UB Time Bomb Detector (LLVM Details)

This document describes the exact LLVM components, IR constructs, passes, and flags the tool uses. Every section maps directly to code in `backend/`.

---

## 1. LLVM Tool Invoked: `clang` / `clang++`

The tool drives Clang as a subprocess to emit human-readable LLVM IR (`.ll` files). No LLVM library (llvmlite, LLVM C API, etc.) is linked — everything goes through the Clang command-line frontend.

### Exact command line (C source)

```
clang -O{0|2} -g -fno-inline -emit-llvm -S -Wno-everything -o <output>.ll <source>.c
```

### Exact command line (C++ source — `.cpp`, `.cc`, `.cxx`)

```
clang++ -O{0|2} -g -fno-inline -emit-llvm -S -Wno-everything -std=c++17 -o <output>.ll <source>.cpp
```

### What each LLVM flag does

| Flag | LLVM subsystem | Effect on IR |
|---|---|---|
| `-O0` | No optimization passes run | IR is a 1-to-1 translation of the AST: every local var has its own `alloca`, no instructions are folded or moved |
| `-O2` | Full middle-end pipeline (~100 passes) | SROA, GVN, InstCombine, BranchFolder, LICM, loop-idiom recognition, and others run in sequence |
| `-g` | DWARF debug info generator | Embeds `!DILocation`, `!DISubprogram`, `!DIFile` metadata nodes in IR; enables source-line extraction |
| `-fno-inline` | `InlineAdvisor` / `AlwaysInliner` | Adds `noinline` attribute to every `define`; prevents `InlinerPass` from absorbing functions into callers at O2 |
| `-emit-llvm -S` | LLVM IR writer (`IRPrinter`) | Outputs human-readable `.ll` text instead of bitcode or native assembly |
| `-Wno-everything` | Clang diagnostic engine | Silences all frontend warnings so they don't interleave with IR text |
| `-std=c++17` | Clang C++ frontend | Enables C++17 language features for `.cpp` files |

### How the binary is located

```python
# backend/core/compile_engine.py
import shutil
shutil.which("clang")                                    # PATH lookup (Unix/Windows)
r"C:\Program Files\LLVM\bin\clang.exe"                  # Windows default install fallback
```

---

## 2. LLVM IR Format — `.ll` File Structure

After Clang emits IR, the tool reads and parses the `.ll` text file directly. Key IR constructs encountered:

### Top-level declarations in a `.ll` file

```llvm
; Module-level metadata
source_filename = "test.c"
target datalayout = "e-m:w-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-windows-msvc19.43.34808"

; Global variable
@g = global i32 0, align 4

; Function definition
define dso_local i32 @f(i32 noundef %0) #0 {
  ...
}

; Attribute groups referenced by #0
attributes #0 = { noinline nounwind optnone uwtable ... }

; Named metadata (module-level debug info)
!llvm.dbg.cu = !{!0}
!0 = distinct !DICompileUnit(language: DW_LANG_C11, file: !1, ...)
!1 = !DIFile(filename: "test.c", directory: "d:\\UB Timebomb Detector")
```

### Function-level IR constructs the tool reads

```llvm
define dso_local i32 @always_true(i32 noundef %0) #0 {
; ─── Entry basic block (unnamed, always first) ───────────────────────────────
  %2 = alloca i32, align 4          ; stack slot for local var
  store i32 %0, ptr %2, align 4     ; write arg to stack slot
  %3 = load i32, ptr %2, align 4    ; read it back (SROA removes this at O2)
  %4 = add nsw i32 %3, 1            ; nsw = No Signed Wrap assertion
  %5 = icmp sgt i32 %4, %3          ; signed greater-than comparison
  %6 = zext i1 %5 to i32
  ret i32 %6, !dbg !12              ; !dbg = source location reference

; ─── Labeled basic block ─────────────────────────────────────────────────────
cond_true:
  br label %exit                    ; unconditional branch

exit:
  ret i32 1
}
```

---

## 3. LLVM IR Instructions Parsed by the Tool

These are the exact instructions the tool's regex engine searches for in the `.ll` text:

### 3.1 `alloca` — Stack Slot Allocation

```llvm
%x = alloca i32, align 4
```

- Present at `-O0` for every local variable.
- **SROA** (`ScalarReplacementOfAggregatesPass`) eliminates `alloca`/`store`/`load` triples at `-O2`, promoting them to SSA registers.
- Tool checks: `"alloca" in o0_ir` → used in uninitialized-use classification to confirm there was a stack-allocated variable.

### 3.2 `load` / `store` — Memory Operations

```llvm
store float 3.140000e+00, ptr %f.addr, align 4
%val = load i32, ptr %f.addr, align 4
```

- At `-O0`, every variable access generates a `load` from its `alloca`.
- At `-O2`, loads are eliminated when the optimizer proves the value is already in an SSA register or when type-punning makes the result meaningless.
- Tool counts: `load {scalar_type}` instructions at O0 vs O2 to detect type-punning load elimination.

### 3.3 `add nsw` / `sub nsw` / `mul nsw` — Arithmetic with No-Wrap Flags

```llvm
%4 = add nsw i32 %3, 1
```

- `nsw` = **No Signed Wrap**. The LLVM language reference states: if signed overflow occurs on this instruction, the result is a `poison` value.
- `nuw` = **No Unsigned Wrap**. Same semantics for unsigned.
- Clang emits `nsw` on arithmetic when the C type is `signed int` and the operation has well-defined behavior in both C and LLVM IR.
- **InstCombine** and **GVN** can propagate the `nsw` flag to arithmetic instructions they generate during optimization.
- Tool checks: `r'\b(add|sub|mul|shl)\s+nsw\b'` — detects when `nsw` appears at O2 but was absent at O0.

### 3.4 `icmp` — Integer Comparison

```llvm
%cond = icmp sgt i32 %a, %b         ; signed greater-than
%null = icmp eq ptr %p, null        ; null pointer check
%loop = icmp slt i32 %i, %n        ; signed less-than (loop bound)
```

- `icmp eq/ne ... null` — null pointer comparison. Tool counts these to detect null-check removal.
- `icmp sgt/slt/sge/sle` — signed comparisons. Tool searches for these in loop overflow guard detection.
- At O2, **BranchFolder** and **GVN** eliminate `icmp` instructions when the optimizer can prove the comparison result is constant.

**Regex used:**
```python
# Null check count
re.findall(r'icmp\s+(?:eq|ne)\s+.*\bnull\b', func_ir)

# Signed comparison in loop guard
re.search(r'icmp\s+s(lt|le|gt|ge)\s+i32', func_ir)
```

### 3.5 `br` — Branch Instructions

```llvm
br i1 %cond, label %true, label %false    ; conditional branch
br label %loop_header                      ; unconditional branch (back-edge)
```

- Conditional branches (`br i1`) are counted per function.
- **BranchFolder** and **SimplifyCFG** collapse conditional branches into unconditional ones (or remove them entirely) when the condition is provably constant.
- Fewer `br i1` instructions at O2 vs O0 = optimizer eliminated a check.

**Regex used:**
```python
re.findall(r'br\s+i1\s+', func_ir)      # count conditional branches
re.findall(r'br\s+label\s+', func_ir)   # count unconditional branches
```

### 3.6 `ret` — Return Instruction

```llvm
ret i32 1        ; constant return — optimizer folded the whole function body
ret i32 %6       ; SSA value return
ret void
```

- When the entire function body is constant-folded, O2 IR contains exactly one `ret i32 <constant>`.
- Tool detects this pattern: `re.findall(r'^\s*ret i32 (-?\d+)\b', func_ir, re.MULTILINE)`.

### 3.7 `undef` / `poison` — Undefined Values

```llvm
ret i32 undef           ; undefined value propagated into return
%v = phi i32 [ undef, %entry ], [ %x, %loop ]
```

- `undef` in LLVM means the value can be any bit pattern — equivalent to C's uninitialized read.
- In LLVM 15+, `undef` is being replaced by `poison`, which has stricter propagation rules. The tool checks for both.
- At O2, **SROA** can expose `undef` by promoting an uninitialized `alloca` to an SSA register with no initial value.

**Regex used:**
```python
# Narrow detection: undef in value-producing positions only
re.search(r'(select|phi|ret)\s+.*\bundef\b', func_ir)
```

### 3.8 Basic Block Labels

```llvm
entry:
  ...
cond.true:
  ...
loop.end:
  ...
```

- Every label (except the implicit entry block) starts with `^\w[\w.]*:` at the start of a line.
- Tool counts labels + 1 (entry block) to get total basic block count.
- Basic block count reduction at O2 = optimizer merged, folded, or deleted blocks.

**Regex used:**
```python
re.findall(r'^\w[\w.]*:', func_ir, re.MULTILINE)  # count labeled BBs
# +1 for implicit entry block
```

---

## 4. LLVM Optimization Passes Responsible for UB-Exploiting Transformations

These are the specific LLVM passes that produce the IR changes the tool detects:

### 4.1 InstCombine (`InstCombinePass`)

**What it does:** Algebraic simplification of individual instructions.

**UB-relevant transformation:**  
`add nsw i32 %x, 1` compared with `%x` via `icmp sgt` → proven always-true under `nsw` → branch folded to unconditional.

```llvm
; Before InstCombine (O0)
%add = add nsw i32 %x, 1
%cmp = icmp sgt i32 %add, %x
br i1 %cmp, label %true, label %false

; After InstCombine (O2)
ret i32 1      ; entire function collapsed
```

**Tool signal:** `signed_overflow_folded = True` (O0 has `add nsw` + `icmp sgt` on same SSA value; O2 returns a constant).

### 4.2 SROA (`ScalarReplacementOfAggregatesPass`)

**What it does:** Promotes `alloca`/`load`/`store` triples to SSA values.

**UB-relevant transformation:**  
An uninitialized `alloca` (no `store` before `load`) → promoted to SSA register → value is `undef`/`poison`.

```llvm
; O0: alloca present, loaded without prior store
%x.addr = alloca i32, align 4
%1 = load i32, ptr %x.addr, align 4    ; reads garbage
ret i32 %1

; O2: SROA promotes alloca, exposes undef
ret i32 undef    ; or: SROA + InstCombine produces poison
```

**Tool signal:** `undef_exposed = True` (O2 IR contains `ret ... undef`).

### 4.3 GVN (`GVNPass` — Global Value Numbering)

**What it does:** Eliminates redundant computations and loads by proving value equality.

**UB-relevant transformation:**  
Pointer `p` was dereferenced before a null check `if (!p)`. GVN proves `p != null` (because a prior `load ptr %p` would have crashed if null), so the null check is dead code.

```llvm
; O0: null check present
%val = load i32, ptr %p              ; dereference first
%cond = icmp eq ptr %p, null         ; null check after (UB: p already used)
br i1 %cond, label %null_path, label %continue

; O2: GVN removes null check (p proven non-null by prior load)
%val = load i32, ptr %p
br label %continue                   ; null_path block gone
```

**Tool signal:** `null_check_removed = True` + `block_loss = True`.

### 4.4 SimplifyCFG (`SimplifyCFGPass`)

**What it does:** Merges basic blocks, removes unreachable blocks, folds constant-condition branches.

**UB-relevant transformation:**  
After InstCombine/GVN prove a branch condition is constant, SimplifyCFG removes the dead target block and turns the conditional branch into an unconditional one.

**Tool signal:** `branch_eliminated = True` (fewer `br i1` at O2 than O0).

### 4.5 LICM (`LICMPass` — Loop Invariant Code Motion)

**What it does:** Hoists loop-invariant computations out of the loop body.

**UB-relevant transformation:**  
A signed overflow guard inside a loop body (`if (i+1 < 0) break`) is hoisted and then proven dead (because the optimizer assumed signed overflow doesn't happen under `nsw`), collapsing the loop structure.

```llvm
; O0: loop with signed overflow guard
loop:
  %sum = add nsw i32 %i, 1
  %guard = icmp slt i32 %sum, 0     ; overflow guard
  br i1 %guard, label %exit, label %loop

; O2: guard eliminated (add nsw proves sum >= 0 under no-overflow assumption)
loop:
  %sum = add nsw i32 %i, 1
  br label %loop
```

**Tool signal:** `loop_overflow_guard = True` (O0 has loop + `add nsw i32` + `icmp s{lt|le|gt|ge}`; O2 has fewer blocks).

### 4.6 Load Elimination / Type-Based Alias Analysis (TBAA)

**What it does:** LLVM attaches `!tbaa` metadata to loads/stores. TBAA allows the optimizer to assume that pointers of different types do not alias. Loads through "impossible aliases" are then eliminated.

**UB-relevant transformation:**  
`store float %f → %ptr`, then `load i32 from %ptr` (type punning). TBAA metadata says `float*` and `int*` can't alias the same location. The `load i32` is either eliminated or returns a stale value.

```llvm
; O0: both typed operations present
store float %val, ptr %f.addr, align 4        ; store float
%punned = load i32, ptr %f.addr, align 4      ; load as int (type punning)
ret i32 %punned

; O2: load eliminated under TBAA alias assumption
ret i32 0     ; or: some arbitrary constant
```

**Tool signal:** `type_punning = True` (store type ≠ load type in O0; typed load count reduced at O2 or O2 returns a constant where O0 did not).

---

## 5. LLVM Debug Metadata — Source Location Extraction

The `-g` flag causes Clang to embed DWARF metadata as named metadata nodes directly in the `.ll` file:

### Metadata node types used

| Metadata Kind | Purpose |
|---|---|
| `!DICompileUnit` | Module-level: compiler version, source file, language |
| `!DIFile` | Maps a metadata ID to a filename + directory |
| `!DISubprogram` | Per-function: name, source file, start line |
| `!DILocation` | Per-instruction: source line, column, scope |

### How `!dbg` links instruction to source line

```llvm
; Instruction with debug reference
  %4 = add nsw i32 %3, 1, !dbg !12

; Named metadata definitions at end of .ll file
!12 = !DILocation(line: 3, column: 20, scope: !7)
!7  = distinct !DISubprogram(name: "always_true", file: !8, line: 2, ...)
!8  = !DIFile(filename: "signed_overflow.c", directory: "d:\\UB Timebomb Detector\\test_cases")
```

### Extraction regex

```python
# Step 1: find all !dbg references in function IR
dbg_refs = re.findall(r'!dbg\s+!(\d+)', func_ir)

# Step 2: resolve each reference to a DILocation node in the full .ll file
loc_match = re.search(
    rf'!{ref}\s*=\s*!DILocation\(line:\s*(\d+).*?(?:file:\s*"([^"]*)")?',
    full_ll_content
)
# Returns {"line": 3, "file": "signed_overflow.c"}
```

---

## 6. LLVM Opaque Pointer Mode (LLVM 15+)

Clang 15 and later default to **opaque pointer** mode. In typed-pointer IR (LLVM ≤ 14), every pointer had an explicit element type:

```llvm
; Typed pointers (LLVM ≤ 14) — explicit bitcast visible in IR
%1 = bitcast float* %f.addr to i32*
%2 = load i32, i32* %1
```

In opaque pointer IR (LLVM ≥ 15), all pointers are simply `ptr`:

```llvm
; Opaque pointers (LLVM ≥ 15) — no bitcast in IR
store float %val, ptr %f.addr, align 4
%punned = load i32, ptr %f.addr, align 4   ; type punning via scalar types
```

### Impact on tool detection

The old `bitcast` heuristic for strict aliasing detection does not fire in LLVM 15+ IR. The tool uses a separate `has_type_punning_pattern()` detector:

```python
# Collect all scalar types stored and loaded in the function
store_types = set(re.findall(rf'store\s+({scalar_types})\s+', o0_ir))
load_types  = set(re.findall(rf'=\s*load\s+({scalar_types}),', o0_ir))

# If a type is stored but loaded as a different type → type punning
if value_store_types - value_load_types:    # mismatch
    if o2_typed_loads < o0_typed_loads:     # and O2 eliminated the load
        return True                         # → strict_aliasing
```

Both paths (legacy `bitcast` + opaque pointer) are active in `_classify_strict_aliasing()`.

---

## 7. LLVM IR Per-Function Parsing — Balanced-Brace Algorithm

Splitting a `.ll` file on `}` naively fails because LLVM IR contains nested braces in:

- Inline metadata: `!{i32 1, !"wchar_size", i32 4}`  
- Attribute groups: `attributes #0 = { noinline nounwind optnone uwtable }`
- Nested debug info: `!DISubprogram(... retainedNodes: !{!10, !11})`

### Algorithm (`ir_parser.py :: parse_ir_by_function`)

```python
func_header = re.compile(r'define\s+[^@]*@([\w$.]+)\s*\([^)]*\)[^{]*\{')

for match in func_header.finditer(content):
    name = match.group(1)
    depth = 0
    for i in range(match.end() - 1, len(content)):
        if content[i] == '{':  depth += 1
        elif content[i] == '}': depth -= 1
        if depth == 0:
            functions[name] = content[match.start() : i + 1]
            break
```

The regex captures the function name from `@name` in the `define` line. Brace-depth tracking then finds the exact closing `}` of the function body regardless of nesting.

### Function name mangling

C++ symbols are mangled (`_Z9always_truei`). The tool calls `c++filt` (or `llvm-cxxfilt`) as a subprocess to produce human-readable names in reports:

```python
subprocess.run(["c++filt", name], ...)       # GCC toolchain
subprocess.run(["llvm-cxxfilt", name], ...)  # LLVM toolchain fallback
```

Unmangled C names pass through unchanged.

---

## 8. LLVM IR Signals Summary Table

| IR Signal | Regex / Check | LLVM Pass that creates it | UB Category |
|---|---|---|---|
| `add nsw i32` at O2 not at O0 | `r'\b(add|sub|mul|shl)\s+nsw\b'` | InstCombine, SROA | `signed_overflow` |
| `icmp sgt` on `add nsw` result folded to `ret i32 1` | `returns_constant_i32()` + `has_signed_add_compare_pattern()` | InstCombine + SimplifyCFG | `signed_overflow` |
| Loop with `add nsw` + `icmp slt` collapsed at O2 | `has_loop_with_signed_overflow_guard()` | LICM + SimplifyCFG | `signed_overflow` |
| `icmp eq ptr %p, null` count drops O0→O2 + block loss | `r'icmp\s+(?:eq|ne)\s+.*\bnull\b'` | GVN | `null_deref` |
| `undef` in `ret`/`phi`/`select` at O2, not at O0 | `r'(select|phi|ret)\s+.*\bundef\b'` | SROA | `uninitialized_use` |
| `alloca` present at O0 + `undef` exposed at O2 | `"alloca" in o0_ir` + `undef_exposed` | SROA | `uninitialized_use` |
| Store type ≠ load type at O0 + fewer typed loads at O2 | `has_type_punning_pattern()` | TBAA + Load Elimination | `strict_aliasing` |
| `bitcast ... to` in O0 IR + fewer `load` at O2 | `r'bitcast\s+.+\s+to\s+.+'` (LLVM ≤14) | TBAA + Load Elimination | `strict_aliasing` |
| `br i1` count drops O0→O2 | `r'br\s+i1\s+'` | SimplifyCFG, BranchFolder | supporting signal |
| Basic block label count drops O0→O2 | `r'^\w[\w.]*:'` multiline | SimplifyCFG, GVN | supporting signal |

---

## 9. LLVM Target Triple and Data Layout

The tool does not pass a specific target triple — Clang infers the host target. The resulting `.ll` files include:

```llvm
target datalayout = "e-m:w-p270:32:32-p271:32:32-p272:64:64-i64:64-..."
target triple = "x86_64-pc-windows-msvc19.43.34808"
```

These lines are parsed by LLVM's backend but ignored by this tool. The analysis operates purely on architecture-neutral IR semantics (`nsw`, `undef`, `icmp`, `br i1`) that are independent of the target triple.

---

## 10. LLVM Version Compatibility

| LLVM Version | Pointer Mode | `nsw` Detection | Type-Punning Detection | `undef` |
|---|---|---|---|---|
| 14 | Typed (`i32*`) | ✅ `bitcast` visible | ✅ `bitcast i32* to float*` | `undef` |
| 15–16 | Opaque (`ptr`) | ✅ | ✅ scalar-type mismatch heuristic | `undef` / `poison` |
| 17–22 | Opaque (`ptr`) | ✅ | ✅ | `poison` (tool still catches via `undef`/const-ret patterns) |

Tested with Clang 22. The `has_signed_add_compare_pattern()` function was added specifically to handle Clang 22's behavior where `add nsw` is not always introduced at O2 for folded expressions — instead, the entire function collapses directly to `ret i32 1`.
