#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_DIR}"

if [ -d "${PROJECT_DIR}/venv" ]; then
    source "${PROJECT_DIR}/venv/bin/activate"
fi

if [ -f "${PROJECT_DIR}/.inkpi/cloud.env" ]; then
    # shellcheck disable=SC1091
    source "${PROJECT_DIR}/.inkpi/cloud.env"
fi

export PYTHONUNBUFFERED=1
export QT_AUTO_SCREEN_SCALE_FACTOR=0
export QT_SCALE_FACTOR=1

exec python main.py
