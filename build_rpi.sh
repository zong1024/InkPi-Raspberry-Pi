#!/bin/bash
# InkPi Raspberry Pi build helper.
# Usage:
#   ./build_rpi.sh
#   MODEL_SOURCE=/path/to/siamese_calligraphy.onnx ./build_rpi.sh

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
python -m pip install pyinstaller pyttsx3

echo "[4/5] Preparing model and sanity check..."
mkdir -p models
if [ -n "${MODEL_SOURCE:-}" ] && [ -f "${MODEL_SOURCE}" ]; then
    cp "${MODEL_SOURCE}" "models/siamese_calligraphy.onnx"
fi

if [ -f "models/siamese_calligraphy.onnx" ]; then
    echo "Found Siamese model: models/siamese_calligraphy.onnx"
else
    echo "Warning: models/siamese_calligraphy.onnx not found. Packaged app will fall back to rule-based scoring."
fi

python -c "import main; print('Health check passed: import main')"

echo "[5/5] Building application..."
pyinstaller \
    --onefile \
    --windowed \
    --name InkPi \
    --add-data "config:config" \
    --add-data "models:models" \
    --add-data "models/templates:models/templates" \
    --add-data "services:services" \
    --add-data "views:views" \
    --add-data "core:core" \
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
