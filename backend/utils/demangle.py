"""
demangle.py - C++ name demangling utility.
"""

import subprocess


def demangle(name: str) -> str:
    """Demangle a C++ symbol name. Falls back to the original name."""
    if not name.startswith("_Z"):
        return name

    try:
        result = subprocess.run(
            ["c++filt", name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        demangled = result.stdout.strip()
        return demangled if demangled else name
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    try:
        result = subprocess.run(
            ["llvm-cxxfilt", name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        demangled = result.stdout.strip()
        return demangled if demangled else name
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return name
