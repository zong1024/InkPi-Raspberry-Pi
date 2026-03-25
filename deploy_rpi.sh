#!/bin/bash
# InkPi Raspberry Pi deployment helper.
# Usage:
#   ./deploy_rpi.sh
#   MODEL_SOURCE=/path/to/siamese_calligraphy.onnx ./deploy_rpi.sh
#   RUN_SELF_TEST=1 ./deploy_rpi.sh
#   INSTALL_KIOSK=1 ./deploy_rpi.sh
#   START_APP=1 ./deploy_rpi.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

safe_git_sync() {
    if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        return 0
    fi

    if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
        echo "[2/7] Syncing repository from origin/master..."
        git fetch origin
        git pull --ff-only origin master
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
    spi-tools \
    xinit \
    x11-xserver-utils \
    openbox \
    xserver-xorg

install_optional_pkg python3-picamera2
install_optional_pkg python3-libcamera
install_optional_pkg libcamera-apps
install_optional_pkg unclutter

sudo raspi-config nonint do_spi 0 2>/dev/null || true
sudo usermod -a -G spi "$USER" 2>/dev/null || true

echo "[4/7] Creating virtual environment..."
python3 -m venv --system-site-packages venv
source venv/bin/activate

echo "[5/7] Installing Python-only packages..."
python -m pip install --upgrade pip
python -m pip install pyttsx3

echo "[6/7] Preparing model and running health check..."
if [ -n "${MODEL_SOURCE:-}" ] && [ -f "${MODEL_SOURCE}" ]; then
    mkdir -p models
    cp "${MODEL_SOURCE}" "models/siamese_calligraphy.onnx"
fi

if [ -f "models/siamese_calligraphy.onnx" ]; then
    echo "Found Siamese model: models/siamese_calligraphy.onnx"
else
    echo "Warning: models/siamese_calligraphy.onnx not found. The app will fall back to rule-based scoring."
fi

python -c "import main; print('Health check passed: import main')"

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
