"""Tests for change_detector.py"""
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.core.compile_engine import compile_both
from backend.core.change_detector import detect_changes


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


def test_signed_overflow_detected(tmp_c_file):
    """Signed overflow should show branch elimination or signed_overflow_folded."""
    path = tmp_c_file("int f(int x) { return x + 1 > x; }\n")
    compiled = compile_both(path, keep_ir=True)
    changes = detect_changes(compiled)
    assert len(changes) > 0
    change_types = changes[0]["change_types"]
    assert any(
        ct in change_types
        for ct in ("branch_elimination", "block_loss", "signed_overflow_folded")
    )


def test_null_deref_detected(tmp_c_file):
    """Null deref pattern should show null_check_removed."""
    code = """
int get_val(int *p) {
    int v = *p;
    if (p == 0) return -1;
    return v;
}
"""
    path = tmp_c_file(code)
    compiled = compile_both(path, keep_ir=True)
    changes = detect_changes(compiled)
    assert len(changes) > 0
    change_types = changes[0]["change_types"]
    assert "null_check_removed" in change_types


def test_safe_code_no_changes(tmp_c_file):
    """Safe code with no UB should produce no meaningful changes."""
    path = tmp_c_file("unsigned int f(unsigned int a) { return a + 1; }\n")
    compiled = compile_both(path, keep_ir=True)
    changes = detect_changes(compiled)
    # Safe unsigned arithmetic — should be no or minimal changes
    # (may have block_loss from O2 simplification, but not UB-related)
    for change in changes:
        ct = change["change_types"]
        # Should NOT have UB-specific change types
        assert "null_check_removed" not in ct
        assert "undef_exposed" not in ct
