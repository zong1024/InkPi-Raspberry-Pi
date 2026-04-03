$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$venvPath = Join-Path $repoRoot ".venv-desktop-sim"

function New-Venv {
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        $versions = & py -0p 2>$null
        if ($LASTEXITCODE -eq 0 -and $versions -match "3\.13") {
            & py -3.13 -m venv $venvPath
            return
        }
        & py -3 -m venv $venvPath
        return
    }

    $python = Get-Command python -ErrorAction Stop
    & $python.Source -m venv $venvPath
}

if (-not (Test-Path $venvPath)) {
    Write-Host "Creating desktop simulator venv at $venvPath"
    New-Venv
}

$venvPython = Join-Path $venvPath "Scripts\python.exe"

& $venvPython -m pip install --upgrade pip setuptools wheel
& $venvPython -m pip install `
    numpy `
    opencv-python `
    PyQt6 `
    pyttsx3 `
    requests `
    Flask `
    matplotlib `
    onnxruntime `
    scipy

if ($env:INKPI_INSTALL_PADDLEOCR -eq "1") {
    try {
        & $venvPython -m pip install paddleocr
    } catch {
        Write-Host "paddleocr install failed; desktop simulator will use built-in OCR fallback." -ForegroundColor Yellow
    }
} else {
    Write-Host "Skipping paddleocr install; set INKPI_INSTALL_PADDLEOCR=1 if you want to try local OCR later." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Desktop simulator environment is ready." -ForegroundColor Green
Write-Host "Run: powershell -ExecutionPolicy Bypass -File scripts\run_desktop_sim.ps1"
