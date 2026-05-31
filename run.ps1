param()

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$VenvDir = Join-Path $ProjectRoot "venv"
$PythonPath = Join-Path $VenvDir "Scripts\python.exe"

if (-not (Test-Path $PythonPath)) {
    Write-Host "ERROR: Virtual environment not found. Run .\build.ps1 first."
    exit 1
}

$Mode = "eval"
$TargetFile = ""

if ($args.Count -gt 0) {
    switch ($args[0]) {
        "--server" { $Mode = "server" }
        "-s"       { $Mode = "server" }
        "--help"   { Write-Host "Usage:`n  .\run.ps1              Run full evaluation`n  .\run.ps1 <file.c>     Analyze a single C file`n  .\run.ps1 --server     Start API server"; exit 0 }
        "-h"       { Write-Host "Usage:`n  .\run.ps1              Run full evaluation`n  .\run.ps1 <file.c>     Analyze a single C file`n  .\run.ps1 --server     Start API server"; exit 0 }
        default    { $Mode = "single"; $TargetFile = $args[0] }
    }
}

if ($Mode -eq "server") {
    Write-Host "========================================"
    Write-Host "  Starting UB Detector API server..."
    Write-Host "  Endpoint: http://localhost:8000"
    Write-Host "  Press Ctrl+C to stop"
    Write-Host "========================================"
    & $PythonPath -m uvicorn backend.main:app --reload --port 8000
}
elseif ($Mode -eq "single") {
    if (-not $TargetFile) {
        Write-Host "ERROR: No file specified."
        exit 1
    }
    if (-not (Test-Path $TargetFile)) {
        Write-Host "ERROR: File not found: $TargetFile"
        exit 1
    }
    $TargetFile = (Resolve-Path $TargetFile).Path

    Write-Host "========================================"
    Write-Host "  Analyzing: $TargetFile"
    Write-Host "========================================"
    & $PythonPath run_single.py $TargetFile
}
else {
    Write-Host "========================================"
    Write-Host "  UB Time Bomb Detector - Evaluation"
    Write-Host "========================================"
    & $PythonPath eval/run_evaluation.py
}
