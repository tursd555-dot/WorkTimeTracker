# WorkTimeTracker - Venv Diagnostic Script
# Simple version without special characters

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  VENV DIAGNOSTIC" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Check current directory
Write-Host "[1] Current Directory:" -ForegroundColor Yellow
Get-Location
Write-Host ""

# Check .venv exists
Write-Host "[2] Checking .venv folder..." -ForegroundColor Yellow
if (Test-Path ".venv") {
    Write-Host "    [OK] .venv exists" -ForegroundColor Green
} else {
    Write-Host "    [ERROR] .venv NOT found!" -ForegroundColor Red
}
Write-Host ""

# Check python.exe
Write-Host "[3] Checking python.exe..." -ForegroundColor Yellow
if (Test-Path ".venv\Scripts\python.exe") {
    Write-Host "    [OK] Python found: .venv\Scripts\python.exe" -ForegroundColor Green
    $version = & .venv\Scripts\python.exe --version 2>&1
    Write-Host "    Version: $version" -ForegroundColor Gray
} else {
    Write-Host "    [ERROR] Python NOT found in .venv!" -ForegroundColor Red
}
Write-Host ""

# Check activation
Write-Host "[4] Checking activation..." -ForegroundColor Yellow
if ($env:VIRTUAL_ENV) {
    Write-Host "    [OK] Virtual environment is active" -ForegroundColor Green
} else {
    Write-Host "    [WARNING] Virtual environment NOT active" -ForegroundColor Yellow
}
Write-Host ""

# Check system Python
Write-Host "[5] Checking system Python..." -ForegroundColor Yellow
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCmd) {
    Write-Host "    [OK] Python found in PATH" -ForegroundColor Green
    Write-Host "    Path: $($pythonCmd.Path)" -ForegroundColor Gray
} else {
    Write-Host "    [ERROR] Python NOT found in PATH!" -ForegroundColor Red
}
Write-Host ""

# Recommendations
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  SOLUTIONS" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Option 1: Use BAT files (EASIEST)" -ForegroundColor Green
Write-Host "  - Double-click: run_admin.bat" -ForegroundColor Gray
Write-Host "  - Double-click: run_user.bat" -ForegroundColor Gray
Write-Host ""
Write-Host "Option 2: Activate manually" -ForegroundColor Yellow
Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor Gray
Write-Host "  python admin_app/main_admin.py" -ForegroundColor Gray
Write-Host ""
Write-Host "Option 3: Recreate .venv" -ForegroundColor Yellow
Write-Host "  python -m venv .venv" -ForegroundColor Gray
Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor Gray
Write-Host "  pip install -r requirements.txt" -ForegroundColor Gray
Write-Host ""
