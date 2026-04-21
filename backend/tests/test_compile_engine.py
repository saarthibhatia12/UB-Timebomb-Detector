"""Tests for compile_engine.py"""
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.core.compile_engine import compile_both, CompilationError


@pytest.fixture
def tmp_c_file():
    """Create a temporary C file and clean up after."""
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


def test_compile_valid_c(tmp_c_file):
    """Valid C file compiles and returns functions."""
    path = tmp_c_file("int foo(int x) { return x * 2; }\n")
    result = compile_both(path)
    assert "functions" in result
    assert "foo" in result["functions"]
    assert "O0" in result["functions"]["foo"]
    assert "O2" in result["functions"]["foo"]


def test_compile_invalid_c(tmp_c_file):
    """Invalid C file raises CompilationError."""
    path = tmp_c_file("this is not valid C code !!!\n")
    with pytest.raises(CompilationError):
        compile_both(path)


def test_file_not_found():
    """Non-existent file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        compile_both("/nonexistent/file.c")


def test_debug_metadata(tmp_c_file):
    """-g flag produces debug metadata in IR."""
    path = tmp_c_file("int bar(int x) { return x + 1; }\n")
    result = compile_both(path, keep_ir=True)
    o0_ir = result["functions"]["bar"]["O0"]
    assert "!dbg" in o0_ir


def test_main_filtered(tmp_c_file):
    """main() function is filtered out."""
    path = tmp_c_file("int main(void) { return 0; }\nint helper(int x) { return x; }\n")
    result = compile_both(path)
    assert "main" not in result["functions"]
    assert "helper" in result["functions"]
