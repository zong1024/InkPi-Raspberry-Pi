#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${INKPI_CHECKS_VENV_DIR:-${PROJECT_DIR}/.venv-rpi-checks}"

cd "${PROJECT_DIR}"

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 is required to run Raspberry Pi CI checks." >&2
    exit 1
fi

if [ ! -d "${VENV_DIR}" ]; then
    python3 -m venv "${VENV_DIR}"
fi

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -m pip install flake8

export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}"
export INKPI_TEST_MODE="${INKPI_TEST_MODE:-true}"
export PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK="${PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK:-True}"

echo "[1/2] Running flake8..."
flake8 main.py cloud_api config services views web_ui test_*.py --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 main.py cloud_api config services views web_ui test_*.py --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

TEST_TARGETS=(
    test_web_ui.py
    test_all.py
    test_cloud_api.py
    test_cloud_ocr_api.py
)

if [ "${INKPI_INCLUDE_CLOUD_SYNC_TESTS:-0}" = "1" ]; then
    TEST_TARGETS+=(test_cloud_sync_integration.py)
fi

echo "[2/2] Running unittest smoke suite..."
python -m unittest "${TEST_TARGETS[@]}"

echo "Raspberry Pi CI checks passed."
