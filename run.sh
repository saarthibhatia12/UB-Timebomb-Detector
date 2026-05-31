
#!/usr/bin/env bash
# run.sh — Run the UB Time Bomb Detector evaluation suite
# Usage:
#   ./run.sh              → run full evaluation (core + CVE test cases)
#   ./run.sh <file.c>     → analyze a single C file
#   ./run.sh --server     → start the FastAPI API server
#
# Run ./build.sh first to set up the environment.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Activate virtual environment ─────────────────────────────────────────────
ACTIVATED=0
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    ACTIVATED=1
elif [ -f "venv/Scripts/activate" ]; then
    source venv/Scripts/activate
    ACTIVATED=1
fi

if [ "$ACTIVATED" -eq 0 ]; then
    echo "WARNING: Could not find venv. Run ./build.sh first, or activate manually."
fi

PYTHON_CMD="python3"
command -v python3 &>/dev/null || PYTHON_CMD="python"

# ── Parse arguments ──────────────────────────────────────────────────────────
MODE="eval"
TARGET_FILE=""

if [ $# -gt 0 ]; then
    case "$1" in
        --server|-s)
            MODE="server"
            ;;
        --help|-h)
            echo "Usage:"
            echo "  ./run.sh              Run full evaluation suite"
            echo "  ./run.sh <file.c>     Analyze a single C file"
            echo "  ./run.sh --server     Start the API server on port 8000"
            exit 0
            ;;
        *)
            MODE="single"
            TARGET_FILE="$1"
            ;;
    esac
fi

# ── Run modes ────────────────────────────────────────────────────────────────

if [ "$MODE" = "server" ]; then
    echo "========================================"
    echo "  Starting UB Detector API server..."
    echo "  Endpoint: http://localhost:8000"
    echo "  Health:   http://localhost:8000/health"
    echo "  Press Ctrl+C to stop"
    echo "========================================"
    uvicorn backend.main:app --reload --port 8000

elif [ "$MODE" = "single" ]; then
    if [ -z "$TARGET_FILE" ]; then
        echo "ERROR: No file specified."
        echo "Usage: ./run.sh <file.c>"
        exit 1
    fi
    if [ ! -f "$TARGET_FILE" ]; then
        echo "ERROR: File not found: $TARGET_FILE"
        exit 1
    fi
    echo "========================================"
    echo "  Analyzing: $TARGET_FILE"
    echo "========================================"
    "$PYTHON_CMD" -c "
import sys, json, os
sys.path.insert(0, '.')
from backend.core.compile_engine import compile_both, CompilationError
from backend.core.change_detector import detect_changes
from backend.core.ub_classifier import classify_diffs
from backend.core.report_generator import generate_report, report_to_text

try:
    compiled = compile_both('$TARGET_FILE', keep_ir=True)
    changes = detect_changes(compiled)
    findings = classify_diffs(changes, full_ir=compiled.get('raw_ir'))
    report = generate_report(findings, '$TARGET_FILE', compiled)
    print(report_to_text(report))
except CompilationError as e:
    print(f'Compilation error: {e}')
    sys.exit(1)
"

else
    # Default: run evaluation suite
    echo "========================================"
    echo "  UB Time Bomb Detector — Evaluation"
    echo "========================================"
    "$PYTHON_CMD" eval/run_evaluation.py
fi
