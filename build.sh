#!/usr/bin/env bash
# build.sh — Set up the UB Time Bomb Detector environment
# Usage: ./build.sh
# Requires: Python 3.10+, Clang 14+

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "  UB Time Bomb Detector — Build Script"
echo "========================================"
echo ""

# ── 1. Check Python version ──────────────────────────────────────────────────
echo "[1/4] Checking Python version..."
if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    echo "ERROR: Python not found. Install Python 3.10+ from https://python.org"
    exit 1
fi

PYTHON_CMD="python3"
command -v python3 &>/dev/null || PYTHON_CMD="python"

PYTHON_VERSION=$("$PYTHON_CMD" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYTHON_MAJOR=$("$PYTHON_CMD" -c "import sys; print(sys.version_info.major)")
PYTHON_MINOR=$("$PYTHON_CMD" -c "import sys; print(sys.version_info.minor)")

if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]; }; then
    echo "ERROR: Python 3.10+ required, found $PYTHON_VERSION"
    exit 1
fi
echo "  ✓ Python $PYTHON_VERSION found"

# ── 2. Check Clang version ───────────────────────────────────────────────────
echo ""
echo "[2/4] Checking Clang version..."
if ! command -v clang &>/dev/null; then
    echo "ERROR: Clang not found."
    echo "  Install on Ubuntu/Debian:  sudo apt install clang"
    echo "  Install on macOS:          brew install llvm"
    echo "  Install on Windows:        winget install LLVM.LLVM"
    exit 1
fi

CLANG_VERSION_FULL=$(clang --version | head -1)
CLANG_MAJOR=$(clang --version | grep -oP 'version \K[0-9]+' | head -1 || clang --version | sed -n 's/.*version \([0-9]*\).*/\1/p' | head -1)

if [ -z "$CLANG_MAJOR" ] || [ "$CLANG_MAJOR" -lt 14 ]; then
    echo "WARNING: Clang 14+ recommended, found: $CLANG_VERSION_FULL"
    echo "  Tool may still work with older versions."
else
    echo "  ✓ $CLANG_VERSION_FULL"
fi

# ── 3. Create virtual environment ────────────────────────────────────────────
echo ""
echo "[3/4] Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    echo "  Creating venv..."
    "$PYTHON_CMD" -m venv venv
    echo "  ✓ Virtual environment created at ./venv"
else
    echo "  ✓ Virtual environment already exists at ./venv"
fi

# Activate venv
if [ -f "venv/bin/activate" ]; then
    # Unix/macOS/WSL
    source venv/bin/activate
elif [ -f "venv/Scripts/activate" ]; then
    # Git Bash on Windows
    source venv/Scripts/activate
fi

# ── 4. Install Python dependencies ───────────────────────────────────────────
echo ""
echo "[4/4] Installing Python dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo "  ✓ Dependencies installed"

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo "========================================"
echo "  Build complete!"
echo ""
echo "  To run the evaluation suite:"
echo "    ./run.sh"
echo ""
echo "  To start the API server:"
echo "    source venv/bin/activate"
echo "    uvicorn backend.main:app --reload --port 8000"
echo "========================================"
