param()

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$PythonPath = "C:\Users\graph\AppData\Local\Programs\Python\Python311\python.exe"
$VenvDir = Join-Path $ProjectRoot "venv"

Write-Host "========================================"
Write-Host "  UB Time Bomb Detector - Build Script"
Write-Host "========================================"
Write-Host ""

# 1. Check Python
Write-Host "[1/4] Checking Python version..."
if (-not (Test-Path $PythonPath)) {
    Write-Host "ERROR: Python not found at $PythonPath"
    exit 1
}
$PyVersion = & $PythonPath -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Write-Host "  Python version: $PyVersion"

# 2. Check Clang
Write-Host ""
Write-Host "[2/4] Checking Clang..."
$ClangPath = "C:\Program Files\LLVM\bin\clang.exe"
if (-not (Test-Path $ClangPath)) {
    $ClangFound = Get-Command clang -ErrorAction SilentlyContinue
    if (-not $ClangFound) {
        Write-Host "ERROR: Clang not found. Install from https://github.com/llvm/llvm-project/releases"
        exit 1
    }
}
$ClangVer = & $ClangPath --version | Select-Object -First 1
Write-Host "  $ClangVer"

# 3. Virtual env
Write-Host ""
Write-Host "[3/4] Setting up virtual environment..."
if (-not (Test-Path $VenvDir)) {
    & $PythonPath -m venv $VenvDir
    Write-Host "  Created venv at $VenvDir"
} else {
    Write-Host "  Venv already exists"
}

# 4. Install deps
Write-Host ""
Write-Host "[4/4] Installing Python dependencies..."
$PipPath = Join-Path $VenvDir "Scripts\pip.exe"
& $PipPath install --quiet --upgrade pip
& $PipPath install --quiet -r requirements.txt
Write-Host "  Dependencies installed"

Write-Host ""
Write-Host "========================================"
Write-Host "  Build complete!"
Write-Host ""
Write-Host "  To run the evaluation suite:"
Write-Host "    .\run.ps1"
Write-Host ""
Write-Host "  To analyze a single file:"
Write-Host "    .\run.ps1 test_cases\signed_overflow.c"
Write-Host ""
Write-Host "  To start the API server:"
Write-Host "    .\run.ps1 --server"
Write-Host "========================================"
