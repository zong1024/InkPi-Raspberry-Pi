#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_DIR}/web_console"

if [ "${INKPI_SKIP_NPM_CI:-0}" != "1" ]; then
    npm ci
fi

npm run ci
