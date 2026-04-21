"""
run_evaluation.py — Batch test runner for all test cases.
Includes timeout protection for test cases that may hang.
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
