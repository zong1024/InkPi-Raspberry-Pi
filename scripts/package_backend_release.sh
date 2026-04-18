#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUT_DIR="${INKPI_RELEASE_DIR:-${PROJECT_DIR}/dist/releases}"
VERSION_TAG="${INKPI_RELEASE_VERSION:-$(git -C "${PROJECT_DIR}" rev-parse --short HEAD 2>/dev/null || echo local)}"
PACKAGE_NAME="inkpi-backend-${VERSION_TAG}"
STAGE_DIR="${OUT_DIR}/${PACKAGE_NAME}"
ARCHIVE_PATH="${OUT_DIR}/${PACKAGE_NAME}.tar.gz"

copy_into_stage() {
    local relative_path="$1"
    local source_path="${PROJECT_DIR}/${relative_path}"
    if [ ! -e "${source_path}" ]; then
        echo "Missing required path: ${relative_path}" >&2
        exit 1
    fi
    mkdir -p "${STAGE_DIR}/$(dirname "${relative_path}")"
    cp -a "${source_path}" "${STAGE_DIR}/${relative_path}"
}

mkdir -p "${OUT_DIR}"
rm -rf "${STAGE_DIR}" "${ARCHIVE_PATH}"

bash "${SCRIPT_DIR}/ci_ops_console.sh"

copy_into_stage "README.md"
copy_into_stage "requirements-backend.txt"
copy_into_stage "cloud_api"
copy_into_stage "config"
copy_into_stage "models"
copy_into_stage "services"
copy_into_stage "web_ui"
copy_into_stage "scripts"

cat > "${STAGE_DIR}/release-manifest.json" <<EOF
{
  "package": "${PACKAGE_NAME}",
  "kind": "backend",
  "git_ref": "$(git -C "${PROJECT_DIR}" rev-parse HEAD 2>/dev/null || echo unknown)",
  "built_at_utc": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF

tar -czf "${ARCHIVE_PATH}" -C "${STAGE_DIR}" .
echo "${ARCHIVE_PATH}"
