#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUT_DIR="${INKPI_RELEASE_DIR:-${PROJECT_DIR}/dist/releases}"
VERSION_TAG="${INKPI_RELEASE_VERSION:-$(git -C "${PROJECT_DIR}" rev-parse --short HEAD 2>/dev/null || echo local)}"
PACKAGE_NAME="inkpi-miniapp-${VERSION_TAG}"
STAGE_DIR="${OUT_DIR}/${PACKAGE_NAME}"
ARCHIVE_PATH="${OUT_DIR}/${PACKAGE_NAME}.zip"
MINIAPP_ARTIFACT_DIR="${PROJECT_DIR}/miniapp/dist/ci-package"

mkdir -p "${OUT_DIR}"
rm -rf "${STAGE_DIR}" "${ARCHIVE_PATH}"

INKPI_MINIAPP_RELEASE_MODE="${INKPI_MINIAPP_RELEASE_MODE:-0}" \
    bash "${SCRIPT_DIR}/ci_miniapp_checks.sh"

if [ ! -d "${MINIAPP_ARTIFACT_DIR}" ]; then
    echo "Missing prepared miniapp artifact directory: ${MINIAPP_ARTIFACT_DIR}" >&2
    exit 1
fi

mkdir -p "${STAGE_DIR}"
cp -a "${MINIAPP_ARTIFACT_DIR}" "${STAGE_DIR}/miniapp"

cat > "${STAGE_DIR}/release-manifest.json" <<EOF
{
  "package": "${PACKAGE_NAME}",
  "kind": "miniapp",
  "git_ref": "$(git -C "${PROJECT_DIR}" rev-parse HEAD 2>/dev/null || echo unknown)",
  "built_at_utc": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "release_mode": ${INKPI_MINIAPP_RELEASE_MODE:-0}
}
EOF

PACKAGE_STAGE="${STAGE_DIR}" PACKAGE_ARCHIVE="${ARCHIVE_PATH}" python - <<'PY'
import os
from pathlib import Path
import zipfile

stage_dir = Path(os.environ["PACKAGE_STAGE"])
archive_path = Path(os.environ["PACKAGE_ARCHIVE"])

with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    for path in sorted(stage_dir.rglob("*")):
        if path.is_file():
            zf.write(path, path.relative_to(stage_dir))
PY

echo "${ARCHIVE_PATH}"
