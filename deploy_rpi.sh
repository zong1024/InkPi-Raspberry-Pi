#!/bin/bash
# InkPi Raspberry Pi deployment helper.
# Usage:
#   ./deploy_rpi.sh
#   MODEL_SOURCE=/path/to/quality_scorer.onnx ./deploy_rpi.sh
#   RUN_SELF_TEST=1 ./deploy_rpi.sh
#   INSTALL_KIOSK=1 ./deploy_rpi.sh
#   START_APP=1 ./deploy_rpi.sh
#   PADDLEPADDLE_PACKAGE=paddlepaddle ./deploy_rpi.sh
#   INKPI_SKIP_HEALTHCHECK=1 ./deploy_rpi.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

safe_git_sync() {
    if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        return 0
    fi

    if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
        local branch="${INKPI_BRANCH:-master}"
        echo "[2/7] Syncing repository from origin/${branch}..."
        git fetch origin
        git pull --ff-only origin "${branch}"
    else
        echo "[2/7] Working tree has local changes. Skipping git sync to avoid overwriting them."
    fi
}

install_optional_pkg() {
    local pkg="$1"
    sudo apt-get install -y "$pkg" 2>/dev/null || echo "Warning: optional package '$pkg' could not be installed."
}

echo "=========================================="
echo "  InkPi Raspberry Pi Deployment"
echo "=========================================="

echo "[1/7] Cleaning generated files..."
rm -rf build dist *.spec __pycache__ */__pycache__ */*/__pycache__
rm -rf venv

safe_git_sync

echo "[3/7] Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y \
    git \
    python3-dev \
    python3-pip \
    python3-venv \
    python3-pyqt6 \
    python3-onnxruntime \
    python3-matplotlib \
    python3-numpy \
    python3-scipy \
    python3-opencv \
    python3-requests \
    python3-spidev \
    python3-pil \
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    libopencv-dev \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libopenblas0 \
    espeak-ng \
    portaudio19-dev \
    libespeak1 \
    spi-tools \
    xinput \
    xinit \
    x11-xserver-utils \
    xserver-xorg-input-evdev \
    openbox \
    xserver-xorg

install_optional_pkg python3-picamera2
install_optional_pkg python3-libcamera
install_optional_pkg libcamera-apps
install_optional_pkg unclutter

sudo raspi-config nonint do_spi 0 2>/dev/null || true
sudo raspi-config nonint do_camera 0 2>/dev/null || true
sudo usermod -a -G spi "$USER" 2>/dev/null || true
sudo usermod -a -G video "$USER" 2>/dev/null || true

echo "[4/7] Creating virtual environment..."
python3 -m venv --system-site-packages venv
source venv/bin/activate

echo "[5/7] Installing Python-only packages..."
python -m pip install --upgrade pip
python -m pip install pyttsx3

PADDLEPADDLE_PACKAGE="${PADDLEPADDLE_PACKAGE:-paddlepaddle}"
if ! python -m pip install "${PADDLEPADDLE_PACKAGE}" paddleocr; then
    echo "Warning: failed to install PaddleOCR dependencies."
    echo "The Raspberry Pi ARM64 runtime will continue with the apt tesseract OCR fallback."
    echo "If you have a compatible Paddle wheel, override the package, for example:"
    echo "  PADDLEPADDLE_PACKAGE='paddlepaddle==3.2.2' ./deploy_rpi.sh"
fi

# Keep ONNX Runtime on Raspberry Pi sourced from apt's python3-onnxruntime.
# PaddleOCR/PaddleX may pull pip wheels for onnx/onnxruntime that conflict with
# the system runtime and spam "schema already registered" during OCR startup.
python -m pip uninstall -y onnx onnxruntime onnxruntime-gpu >/dev/null 2>&1 || true

if [ -f ".inkpi/cloud.env" ]; then
    # shellcheck disable=SC1091
    source ".inkpi/cloud.env"
fi

echo "[6/7] Preparing models and health check..."
if [ -n "${MODEL_SOURCE:-}" ] && [ -f "${MODEL_SOURCE}" ]; then
    mkdir -p models
    cp "${MODEL_SOURCE}" "models/quality_scorer.onnx"
fi

if [ ! -f "models/quality_scorer.onnx" ]; then
    echo "Error: models/quality_scorer.onnx not found. Single-chain scoring cannot start."
    exit 1
fi

if [ "${INKPI_SKIP_HEALTHCHECK:-0}" = "1" ]; then
    echo "Skipping model health check because INKPI_SKIP_HEALTHCHECK=1."
else
python - <<'PY'
from services.local_ocr_service import local_ocr_service

print("Local OCR available:", local_ocr_service.available)

if not local_ocr_service.available:
    raise SystemExit("Local OCR is unavailable on this device.")
PY

python - <<'PY'
from services.quality_scorer_service import quality_scorer_service

print("Quality scorer available:", quality_scorer_service.available)

if not quality_scorer_service.available:
    raise SystemExit("Quality scorer ONNX is unavailable on this device.")
PY

python - <<'PY'
import main
print("Health check passed: import main")
PY
fi

if [ "${RUN_SELF_TEST:-0}" = "1" ]; then
    MPLBACKEND=Agg python test_all.py
fi

if [ "${INSTALL_KIOSK:-0}" = "1" ]; then
    echo "[7/7] Installing kiosk startup flow..."
    bash scripts/install_kiosk.sh
else
    echo "[7/7] Deployment finished."
fi
echo "Activate env: source venv/bin/activate"
echo "Run app:      python main.py"
echo "Install kiosk: INSTALL_KIOSK=1 ./deploy_rpi.sh"

if [ "${START_APP:-0}" = "1" ]; then
    python main.py
fi
