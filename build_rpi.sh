#!/bin/bash
# InkPi Raspberry Pi build helper.
# Usage:
#   ./build_rpi.sh
#   MODEL_SOURCE=/path/to/quality_scorer.onnx ./build_rpi.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

install_optional_pkg() {
    local pkg="$1"
    sudo apt-get install -y "$pkg" 2>/dev/null || echo "Warning: optional package '$pkg' could not be installed."
}

echo "=========================================="
echo "  InkPi Raspberry Pi Build"
echo "=========================================="

if [ ! -f /proc/device-tree/model ]; then
    echo "Warning: build_rpi.sh is intended to run on Raspberry Pi hardware."
fi

echo "[1/5] Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y \
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
    libopencv-dev \
    espeak-ng \
    portaudio19-dev \
    libespeak1 \
    libespeak-dev \
    spi-tools

install_optional_pkg python3-picamera2
install_optional_pkg python3-libcamera
install_optional_pkg libcamera-apps

sudo raspi-config nonint do_spi 0 2>/dev/null || true
sudo usermod -a -G spi "$USER" 2>/dev/null || true

echo "[2/5] Creating virtual environment..."
rm -rf venv
python3 -m venv --system-site-packages venv
source venv/bin/activate

echo "[3/5] Installing Python-only packages..."
python -m pip install --upgrade pip
python -m pip install pyinstaller pyttsx3 paddleocr

echo "[4/5] Preparing model and sanity check..."
mkdir -p models
if [ -n "${MODEL_SOURCE:-}" ] && [ -f "${MODEL_SOURCE}" ]; then
    cp "${MODEL_SOURCE}" "models/quality_scorer.onnx"
fi

if [ ! -f "models/quality_scorer.onnx" ]; then
    echo "Error: models/quality_scorer.onnx not found. Single-chain scoring cannot be packaged."
    exit 1
fi

python - <<'PY'
import main
from services.local_ocr_service import local_ocr_service
from services.quality_scorer_service import quality_scorer_service

print("Health check passed: import main")
print("Local OCR available:", local_ocr_service.available)
print("Quality scorer available:", quality_scorer_service.available)

if not local_ocr_service.available:
    raise SystemExit("PaddleOCR is unavailable on this device.")
if not quality_scorer_service.available:
    raise SystemExit("Quality scorer ONNX is unavailable on this device.")
PY

echo "[5/5] Building application..."
pyinstaller \
    --onefile \
    --windowed \
    --name InkPi \
    --add-data "config:config" \
    --add-data "models:models" \
    --add-data "services:services" \
    --add-data "views:views" \
    --add-data "data:data" \
    --hidden-import PyQt6 \
    --hidden-import PyQt6.QtCore \
    --hidden-import PyQt6.QtWidgets \
    --hidden-import PyQt6.QtGui \
    --hidden-import cv2 \
    --hidden-import numpy \
    --hidden-import matplotlib \
    --hidden-import matplotlib.backends.backend_qtagg \
    --hidden-import pyttsx3 \
    --hidden-import sqlite3 \
    --hidden-import requests \
    --hidden-import onnxruntime \
    --hidden-import paddleocr \
    --hidden-import PIL \
    --hidden-import scipy \
    --collect-all PyQt6 \
    --exclude-module tkinter \
    main.py

echo ""
echo "=========================================="
echo "  Build Complete"
echo "=========================================="
echo "Binary: dist/InkPi"
echo "Size:   $(du -h dist/InkPi | cut -f1)"
