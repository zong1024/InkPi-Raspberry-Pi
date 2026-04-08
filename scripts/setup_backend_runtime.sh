#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/_server_runtime.sh"

cd "${PROJECT_DIR}"

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 is required on the server." >&2
    exit 1
fi

if [ ! -d "${VENV_DIR}" ]; then
    python3 -m venv "${VENV_DIR}"
fi

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements-backend.txt

mkdir -p "${PROJECT_DIR}/data/runtime_logs" "${PROJECT_DIR}/data/runtime_pids"
chmod +x "${SCRIPT_DIR}/"*.sh

echo "InkPi backend runtime is ready."
echo "Virtualenv: ${VENV_DIR}"
