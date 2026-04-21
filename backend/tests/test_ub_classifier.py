"""Tests for ub_classifier.py"""
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.core.compile_engine import compile_both
from backend.core.change_detector import detect_changes
from backend.core.ub_classifier import classify_diffs


@pytest.fixture
def tmp_c_file():
    files = []

    def _create(code):
        fd, path = tempfile.mkstemp(suffix=".c")
        with os.fdopen(fd, "w") as f:
            f.write(code)
        files.append(path)
        return path

    yield _create

    for p in files:
        try:
            os.unlink(p)
        except OSError:
            pass


def _classify(code, tmp_c_file):
    """Helper: compile, detect, classify."""
    path = tmp_c_file(code)
    compiled = compile_both(path, keep_ir=True)
    changes = detect_changes(compiled)
    findings = classify_diffs(changes, full_ir=compiled.get("raw_ir"))
    return findings


def test_signed_overflow_classified(tmp_c_file):
    """Signed overflow should be classified as signed_overflow."""
    findings = _classify("int f(int x) { return x + 1 > x; }\n", tmp_c_file)
    assert len(findings) > 0
    assert findings[0]["category"] == "signed_overflow"
    assert findings[0]["severity"] == "critical"


def test_null_deref_classified(tmp_c_file):
    """Null deref pattern should be classified as null_deref."""
    code = """
int get_val(int *p) {
    int v = *p;
    if (p == 0) return -1;
    return v;
}
"""
    findings = _classify(code, tmp_c_file)
    assert len(findings) > 0
    assert findings[0]["category"] == "null_deref"
    assert findings[0]["severity"] == "critical"


def test_safe_code_no_findings(tmp_c_file):
    """Safe code should produce no UB findings (signed_overflow/null_deref/etc)."""
    findings = _classify("unsigned int f(unsigned int a) { return a * 2; }\n", tmp_c_file)
    ub_findings = [f for f in findings if f["category"] not in ("unknown", "inlined")]
    assert len(ub_findings) == 0


def test_findings_have_fix(tmp_c_file):
    """Every finding should include a fix suggestion."""
    findings = _classify("int f(int x) { return x + 1 > x; }\n", tmp_c_file)
    for f in findings:
        assert "fix" in f
        assert len(f["fix"]) > 0


def test_findings_have_confidence(tmp_c_file):
    """Every finding should include a confidence field."""
    findings = _classify("int f(int x) { return x + 1 > x; }\n", tmp_c_file)
    for f in findings:
        assert "confidence" in f
        assert f["confidence"] in ("HIGH", "MEDIUM", "PARTIAL", "LOW", "N/A")
