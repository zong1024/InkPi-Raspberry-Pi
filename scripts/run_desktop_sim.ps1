$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$venvPath = Join-Path $repoRoot ".venv-desktop-sim"
$venvPython = Join-Path $venvPath "Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "Desktop simulator venv not found; running setup first." -ForegroundColor Yellow
    & powershell -ExecutionPolicy Bypass -File (Join-Path $repoRoot "scripts\setup_desktop_sim.ps1")
}

$env:INKPI_DESKTOP_SIM = "1"
$env:INKPI_LOCAL_OCR_DEVICE = "cpu"
$env:PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK = "True"

if (-not $env:INKPI_SIM_DEFAULT_CHAR) {
    $env:INKPI_SIM_DEFAULT_CHAR = "永"
}

Write-Host "Launching InkPi desktop simulator..." -ForegroundColor Green
Write-Host "Window: 480x320, desktop simulation mode enabled"

Push-Location $repoRoot
try {
    & $venvPython main.py
} finally {
    Pop-Location
}
