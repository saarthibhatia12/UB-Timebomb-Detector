import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.core.compile_engine import compile_both, CompilationError
from backend.core.change_detector import detect_changes
from backend.core.ub_classifier import classify_diffs
from backend.core.report_generator import generate_report, report_to_text

target = sys.argv[1]
try:
    compiled = compile_both(target, keep_ir=True)
    changes = detect_changes(compiled)
    findings = classify_diffs(changes, full_ir=compiled.get("raw_ir"))
    report = generate_report(findings, target, compiled)
    print(report_to_text(report))
except CompilationError as e:
    print(f"Compilation error: {e}")
    sys.exit(1)
