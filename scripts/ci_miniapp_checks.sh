#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_DIR}"

if [ -f "${PROJECT_DIR}/miniapp/package.json" ]; then
    MINIAPP_CI_COMMAND="ci"
    if [ "${INKPI_MINIAPP_RELEASE_MODE:-0}" = "1" ]; then
        MINIAPP_CI_COMMAND="ci:release"
    fi

    npm --prefix miniapp run "${MINIAPP_CI_COMMAND}"
else
    while IFS= read -r -d '' file; do
        node --check "${file}"
    done < <(find miniapp -type f -name "*.js" -print0 | sort -z)

    python "${SCRIPT_DIR}/validate_miniapp_release.py"
fi
