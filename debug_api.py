"""Debug: simulate exactly what the /analyze endpoint does."""
import sys, os, json, tempfile, shutil
sys.path.insert(0, '.')

from backend.core.compile_engine import compile_both, CompilationError
from backend.core.change_detector import detect_changes
from backend.core.ub_classifier import classify_diffs
from backend.core.report_generator import generate_report

source_code = r'''#include <stdio.h>
#include <stdlib.h>

#define NO_INLINE __attribute__((noinline))

NO_INLINE void check_null_logic(int *p) {
    int val = *p;
    if (p == NULL) {
        printf("This code is a 'Time Bomb' and will be deleted at -O2.\n");
        return;
    }
    printf("Value: %d\n", val);
}

NO_INLINE int check_overflow_logic(int a) {
    int next = a + 1;
    if (next > a) {
        return 1;
    } else {
        return 0; 
    }
}

NO_INLINE void check_boundary_logic(int index) {
    int buffer[5] = {1, 2, 3, 4, 5};
    int val = buffer[index];
    if (index >= 5) {
        printf("Index out of bounds! (Optimizer may prune this).\n");
    }
    printf("Val: %d\n", val);
}

int main(int argc, char** argv) {
    int x = 10;
    check_null_logic(&x);
    check_overflow_logic(2000);
    check_boundary_logic(2);
    return 0;
}
'''

# This simulates what _safe_filename does
def safe_filename(name):
    fallback = "input.c"
    raw = (name or fallback).strip()
    base = os.path.basename(raw)
    if not base:
        return fallback
    _, ext = os.path.splitext(base)
    valid = {".c", ".cpp", ".cc", ".cxx", ".C", ".c++"}
    if ext not in valid:
        base = base + ".c"
    return base

work_dir = tempfile.mkdtemp(prefix="ub_debug_")
filename = safe_filename("input.c")
source_path = os.path.join(work_dir, filename)
print("Source path:", source_path)

with open(source_path, "w", encoding="utf-8") as f:
    f.write(source_code)

try:
    compiled = compile_both(source_path, work_dir=work_dir, keep_ir=True)
    changes = detect_changes(compiled)
    findings = classify_diffs(changes, full_ir=compiled.get("raw_ir"))
    report = generate_report(findings, source_path, compiled)
    
    print("Total findings:", report["total_findings"])
    print("Risk score:", report["risk_score"])
    for f in report["findings"]:
        print("  -", f["function"], ":", f["category"], "("+f["severity"]+")")
except CompilationError as e:
    print("COMPILATION ERROR:", str(e))
finally:
    shutil.rmtree(work_dir, ignore_errors=True)
