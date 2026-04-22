"""
compile_engine.py - Differential Compilation Engine (Deliverable 1).

Compiles a C source file at -O0 and -O2 and captures LLVM IR per function.
"""

import os
import shutil
import subprocess
import tempfile
from typing import Optional

from backend.utils.ir_parser import parse_ir_by_function


class CompilationError(Exception):
    """Raised when clang fails to compile the source file."""


# Compiler-generated and process entry helpers to skip in analysis output.
SKIP_FUNCTIONS = frozenset(
    {
        "main",
        "__libc_csu_init",
        "__libc_csu_fini",
        "_start",
        "__do_global_dtors_aux",
        "frame_dummy",
        "register_tm_clones",
        "deregister_tm_clones",
        "__libc_start_main",
    }
)


CPP_EXTENSIONS = frozenset({".cpp", ".cc", ".cxx", ".C", ".c++"})


def _is_cpp_file(source_path: str) -> bool:
    """Check if a source file is C++ based on its extension."""
    _, ext = os.path.splitext(source_path)
    return ext in CPP_EXTENSIONS


def _resolve_clang(cpp: bool = False) -> str:
    """Resolve clang/clang++ executable name/path for current platform."""
    name = "clang++" if cpp else "clang"
    found = shutil.which(name)
    if found:
        return found

    exe = f"{name}.exe"
    windows_default = rf"C:\Program Files\LLVM\bin\{exe}"
    if os.name == "nt" and os.path.exists(windows_default):
        return windows_default

    return name


def _run_clang(
    source_path: str, opt_level: int, output_path: str,
    cpp: bool = False, timeout: int = 30,
) -> str:
    """
    Run clang/clang++ to emit LLVM IR at the given optimization level.
    Returns stderr output (warnings/errors).
    """
    cmd = [
        _resolve_clang(cpp=cpp),
        f"-O{opt_level}",
        "-g",
        "-fno-inline",
        "-emit-llvm",
        "-S",
        "-Wno-everything",
    ]
    if cpp:
        cmd.append("-std=c++17")
    cmd.extend(["-o", output_path, source_path])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise CompilationError(f"Clang timed out after {timeout}s at -O{opt_level}") from exc
    except FileNotFoundError as exc:
        raise CompilationError("Clang not found. Install LLVM: winget install LLVM.LLVM") from exc

    if result.returncode != 0:
        raise CompilationError(f"Clang failed at -O{opt_level}:\n{result.stderr}")

    if not os.path.exists(output_path):
        raise CompilationError(f"Clang produced no output at -O{opt_level}: {output_path}")

    return result.stderr


def compile_both(source_path: str, work_dir: Optional[str] = None, keep_ir: bool = False) -> dict:
    """
    Compile a source file at -O0 and -O2 and return structured per-function IR.

    Returns:
    {
        "source": "path/to/file.c",
        "functions": {
            "func_name": {
                "O0": "<full IR text>",
                "O2": "<full IR text>"
            }
        },
        "o0_only": ["func_missing_in_o2", ...],
        "o2_only": ["func_missing_in_o0", ...],
        "raw_ir": {
            "O0_path": "...",
            "O2_path": "...",
            "O0_full": "...",
            "O2_full": "..."
        }
    }
    """
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Source file not found: {source_path}")

    if work_dir is None:
        work_dir = tempfile.mkdtemp(prefix="ub_detector_")

    base = os.path.splitext(os.path.basename(source_path))[0]
    o0_path = os.path.join(work_dir, f"{base}_O0.ll")
    o2_path = os.path.join(work_dir, f"{base}_O2.ll")

    cpp = _is_cpp_file(source_path)
    _run_clang(source_path, 0, o0_path, cpp=cpp)
    _run_clang(source_path, 2, o2_path, cpp=cpp)

    o0_funcs = parse_ir_by_function(o0_path)
    o2_funcs = parse_ir_by_function(o2_path)

    with open(o0_path, "r", encoding="utf-8") as f:
        o0_full = f.read()
    with open(o2_path, "r", encoding="utf-8") as f:
        o2_full = f.read()

    all_names = set(o0_funcs.keys()) | set(o2_funcs.keys())
    user_functions = {name for name in all_names if name not in SKIP_FUNCTIONS}

    functions = {}
    o0_only = []
    o2_only = []

    for name in user_functions:
        if name in o0_funcs and name in o2_funcs:
            functions[name] = {"O0": o0_funcs[name], "O2": o2_funcs[name]}
        elif name in o0_funcs:
            o0_only.append(name)
        else:
            o2_only.append(name)

    if not keep_ir:
        try:
            os.unlink(o0_path)
            os.unlink(o2_path)
            os.rmdir(work_dir)
        except OSError:
            pass

    return {
        "source": source_path,
        "functions": functions,
        "o0_only": o0_only,
        "o2_only": o2_only,
        "raw_ir": {
            "O0_path": o0_path if keep_ir else None,
            "O2_path": o2_path if keep_ir else None,
            "O0_full": o0_full,
            "O2_full": o2_full,
        },
    }
