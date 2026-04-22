import sys, json
sys.path.insert(0, '.')
from backend.core.compile_engine import compile_both
from backend.core.change_detector import detect_changes
from backend.core.ub_classifier import classify_diffs

compiled = compile_both('debug_test.c', keep_ir=True)
print('=== Functions found ===')
for name in compiled['functions']:
    print('  ' + name)
print('O0-only: ' + str(compiled["o0_only"]))
print('O2-only: ' + str(compiled["o2_only"]))

changes = detect_changes(compiled)
print('\n=== Changes detected: ' + str(len(changes)) + ' ===')
for c in changes:
    m = c["metrics"]
    print('  ' + c["function"] + ': ' + str(c["change_types"]))
    print('    blocks O0=' + str(m["blocks_O0"]) + ' O2=' + str(m["blocks_O2"]))
    print('    branches O0=' + str(m["branches_O0"]) + ' O2=' + str(m["branches_O2"]))
    print('    null_checks O0=' + str(m["null_checks_O0"]) + ' O2=' + str(m["null_checks_O2"]))
    print('    nsw_added=' + str(m["nsw_added"]))
    print('    signed_overflow_folded=' + str(m.get("signed_overflow_folded", False)))

findings = classify_diffs(changes, full_ir=compiled.get('raw_ir'))
print('\n=== Findings: ' + str(len(findings)) + ' ===')
for f in findings:
    print('  ' + f["function"] + ': ' + f["category"] + ' (' + f["severity"] + ')')
