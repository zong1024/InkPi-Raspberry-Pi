#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/_server_runtime.sh"

ensure_xfce_runtime

cd "${PROJECT_DIR}"
exec python main.py
