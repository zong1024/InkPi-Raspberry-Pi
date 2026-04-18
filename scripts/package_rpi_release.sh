#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DIST_DIR="${INKPI_PACKAGE_DIR:-${PROJECT_DIR}/dist/releases}"
PACKAGE_PREFIX="${INKPI_PACKAGE_NAME:-inkpi-rpi-release}"
TIMESTAMP="$(date -u +"%Y%m%d-%H%M%S")"
GIT_SHA="nogit"

cd "${PROJECT_DIR}"

if [ ! -f "${PROJECT_DIR}/models/quality_scorer.onnx" ]; then
    echo "models/quality_scorer.onnx is required for Raspberry Pi release packaging." >&2
    exit 1
fi

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    GIT_SHA="$(git rev-parse --short HEAD)"
fi

RELEASE_ID="${INKPI_RELEASE_ID:-${TIMESTAMP}-${GIT_SHA}}"
ARTIFACT_PATH="${DIST_DIR}/${PACKAGE_PREFIX}-${RELEASE_ID}.tar.gz"
MANIFEST_PATH="${DIST_DIR}/${PACKAGE_PREFIX}-${RELEASE_ID}.manifest.txt"
CHECKSUM_PATH="${ARTIFACT_PATH}.sha256"

mkdir -p "${DIST_DIR}"

PACKAGE_PATHS=(
    assets
    cloud_api
    config
    models
    scripts
    services
    views
    web_ui
    main.py
    README.md
    requirements.txt
    requirements-backend.txt
)

if [ "${INKPI_PACKAGE_INCLUDE_TESTS:-0}" = "1" ]; then
    PACKAGE_PATHS+=(
        test_all.py
        test_cloud_api.py
        test_cloud_ocr_api.py
        test_cloud_sync_integration.py
        test_web_ui.py
    )
fi

for package_path in "${PACKAGE_PATHS[@]}"; do
    if [ ! -e "${package_path}" ]; then
        echo "Required package path is missing: ${package_path}" >&2
        exit 1
    fi
done

if [ -d "${PROJECT_DIR}/web_console" ] && [ -x "${SCRIPT_DIR}/ci_ops_console.sh" ]; then
    bash "${SCRIPT_DIR}/ci_ops_console.sh"
fi

tar \
    --exclude="__pycache__" \
    --exclude="*.pyc" \
    --exclude="*.pyo" \
    --exclude="*.log" \
    --exclude=".DS_Store" \
    -czf "${ARTIFACT_PATH}" \
    "${PACKAGE_PATHS[@]}"

if command -v sha256sum >/dev/null 2>&1; then
    (
        cd "${DIST_DIR}"
        sha256sum "$(basename "${ARTIFACT_PATH}")"
    ) > "${CHECKSUM_PATH}"
else
    python3 - "${ARTIFACT_PATH}" "${CHECKSUM_PATH}" <<'PY'
import hashlib
import pathlib
import sys

artifact = pathlib.Path(sys.argv[1])
checksum_path = pathlib.Path(sys.argv[2])
digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
checksum_path.write_text(f"{digest}  {artifact.name}\n", encoding="utf-8")
PY
fi

cat > "${MANIFEST_PATH}" <<EOF
artifact=$(basename "${ARTIFACT_PATH}")
release_id=${RELEASE_ID}
created_at_utc=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
git_sha=${GIT_SHA}
deploy_modes=backend,server
includes_tests=${INKPI_PACKAGE_INCLUDE_TESTS:-0}
EOF

echo "Release package created:"
echo "  artifact: ${ARTIFACT_PATH}"
echo "  checksum: ${CHECKSUM_PATH}"
echo "  manifest: ${MANIFEST_PATH}"
