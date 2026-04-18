#!/bin/bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <bundle.tar.gz>" >&2
    exit 1
fi

BUNDLE_PATH="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
: "${INKPI_DEPLOY_HOST:?Missing INKPI_DEPLOY_HOST}"
: "${INKPI_DEPLOY_USER:?Missing INKPI_DEPLOY_USER}"

INKPI_DEPLOY_PORT="${INKPI_DEPLOY_PORT:-22}"
INKPI_DEPLOY_TARGET_DIR="${INKPI_DEPLOY_TARGET_DIR:-/opt/inkpi}"
INKPI_RELEASE_ID="${INKPI_RELEASE_ID:-$(date -u +%Y%m%d%H%M%S)}"
INKPI_REMOTE_WEB_PORT="${INKPI_REMOTE_WEB_PORT:-5000}"
INKPI_REMOTE_CLOUD_PORT="${INKPI_REMOTE_CLOUD_PORT:-23333}"

REMOTE_RELEASES_DIR="${INKPI_DEPLOY_TARGET_DIR}/releases"
REMOTE_RELEASE_DIR="${REMOTE_RELEASES_DIR}/${INKPI_RELEASE_ID}"
REMOTE_CURRENT_LINK="${INKPI_DEPLOY_TARGET_DIR}/current"
REMOTE_SHARED_DIR="${INKPI_DEPLOY_TARGET_DIR}/shared"
REMOTE_SHARED_ENV_DIR="${REMOTE_SHARED_DIR}/.inkpi"
REMOTE_SHARED_DATA_DIR="${REMOTE_SHARED_DIR}/data"
REMOTE_SHARED_VENV_DIR="${REMOTE_SHARED_DIR}/venv"
REMOTE_SHARED_LOG_DIR="${REMOTE_SHARED_DIR}/runtime_logs"
REMOTE_SHARED_PID_DIR="${REMOTE_SHARED_DIR}/runtime_pids"
REMOTE_BUNDLE_PATH="/tmp/$(basename "${BUNDLE_PATH}")"
SSH_OPTS=(-p "${INKPI_DEPLOY_PORT}" -o StrictHostKeyChecking=accept-new)

scp "${SSH_OPTS[@]}" "${BUNDLE_PATH}" "${INKPI_DEPLOY_USER}@${INKPI_DEPLOY_HOST}:${REMOTE_BUNDLE_PATH}"

ssh "${SSH_OPTS[@]}" "${INKPI_DEPLOY_USER}@${INKPI_DEPLOY_HOST}" \
    "REMOTE_RELEASES_DIR='${REMOTE_RELEASES_DIR}' \
REMOTE_RELEASE_DIR='${REMOTE_RELEASE_DIR}' \
REMOTE_CURRENT_LINK='${REMOTE_CURRENT_LINK}' \
REMOTE_SHARED_ENV_DIR='${REMOTE_SHARED_ENV_DIR}' \
REMOTE_SHARED_DATA_DIR='${REMOTE_SHARED_DATA_DIR}' \
REMOTE_SHARED_VENV_DIR='${REMOTE_SHARED_VENV_DIR}' \
REMOTE_SHARED_LOG_DIR='${REMOTE_SHARED_LOG_DIR}' \
REMOTE_SHARED_PID_DIR='${REMOTE_SHARED_PID_DIR}' \
REMOTE_BUNDLE_PATH='${REMOTE_BUNDLE_PATH}' \
INKPI_REMOTE_WEB_PORT='${INKPI_REMOTE_WEB_PORT}' \
INKPI_REMOTE_CLOUD_PORT='${INKPI_REMOTE_CLOUD_PORT}' \
bash -s" <<'REMOTE'
set -euo pipefail

copy_into_shared_if_empty() {
    local source_dir="$1"
    local target_dir="$2"

    if [ ! -d "${source_dir}" ]; then
        return 0
    fi

    mkdir -p "${target_dir}"
    if find "${target_dir}" -mindepth 1 -maxdepth 1 -print -quit | grep -q .; then
        return 0
    fi

    cp -a "${source_dir}/." "${target_dir}/"
}

stop_current_stack() {
    local stop_script="$1"

    if [ ! -f "${stop_script}" ]; then
        return 0
    fi

    INKPI_VENV_DIR="${REMOTE_SHARED_VENV_DIR}" \
    INKPI_LOG_DIR="${REMOTE_SHARED_LOG_DIR}" \
    INKPI_PID_DIR="${REMOTE_SHARED_PID_DIR}" \
        bash "${stop_script}" || true

    bash "${stop_script}" || true
}

mkdir -p \
    "${REMOTE_RELEASES_DIR}" \
    "${REMOTE_RELEASE_DIR}" \
    "${REMOTE_SHARED_ENV_DIR}" \
    "${REMOTE_SHARED_DATA_DIR}" \
    "${REMOTE_SHARED_LOG_DIR}" \
    "${REMOTE_SHARED_PID_DIR}"

if [ -e "${REMOTE_CURRENT_LINK}" ]; then
    copy_into_shared_if_empty "${REMOTE_CURRENT_LINK}/data" "${REMOTE_SHARED_DATA_DIR}"
    copy_into_shared_if_empty "${REMOTE_CURRENT_LINK}/.inkpi" "${REMOTE_SHARED_ENV_DIR}"
    stop_current_stack "${REMOTE_CURRENT_LINK}/scripts/stop_backend_stack.sh"
fi

find "${REMOTE_RELEASE_DIR}" -mindepth 1 -maxdepth 1 -exec rm -rf {} + 2>/dev/null || true
tar -xzf "${REMOTE_BUNDLE_PATH}" -C "${REMOTE_RELEASE_DIR}"

rm -rf "${REMOTE_RELEASE_DIR}/data" "${REMOTE_RELEASE_DIR}/.inkpi"
ln -sfn "${REMOTE_SHARED_DATA_DIR}" "${REMOTE_RELEASE_DIR}/data"
ln -sfn "${REMOTE_SHARED_ENV_DIR}" "${REMOTE_RELEASE_DIR}/.inkpi"

if [ -e "${REMOTE_CURRENT_LINK}" ] && [ ! -L "${REMOTE_CURRENT_LINK}" ]; then
    rm -rf "${REMOTE_CURRENT_LINK}"
fi
ln -sfn "${REMOTE_RELEASE_DIR}" "${REMOTE_CURRENT_LINK}"

cd "${REMOTE_CURRENT_LINK}"
INKPI_VENV_DIR="${REMOTE_SHARED_VENV_DIR}" \
INKPI_LOG_DIR="${REMOTE_SHARED_LOG_DIR}" \
INKPI_PID_DIR="${REMOTE_SHARED_PID_DIR}" \
    bash scripts/setup_backend_runtime.sh

INKPI_VENV_DIR="${REMOTE_SHARED_VENV_DIR}" \
INKPI_LOG_DIR="${REMOTE_SHARED_LOG_DIR}" \
INKPI_PID_DIR="${REMOTE_SHARED_PID_DIR}" \
INKPI_WEB_PORT="${INKPI_REMOTE_WEB_PORT}" \
INKPI_CLOUD_PORT="${INKPI_REMOTE_CLOUD_PORT}" \
    bash scripts/start_backend_stack.sh

INKPI_VENV_DIR="${REMOTE_SHARED_VENV_DIR}" \
INKPI_LOG_DIR="${REMOTE_SHARED_LOG_DIR}" \
INKPI_PID_DIR="${REMOTE_SHARED_PID_DIR}" \
INKPI_WEB_PORT="${INKPI_REMOTE_WEB_PORT}" \
INKPI_CLOUD_PORT="${INKPI_REMOTE_CLOUD_PORT}" \
    bash scripts/health_check_stack.sh backend

rm -f "${REMOTE_BUNDLE_PATH}"
REMOTE

echo "PASS backend deployed to ${INKPI_DEPLOY_HOST}:${INKPI_DEPLOY_TARGET_DIR}"
echo "Shared runtime dir: ${INKPI_DEPLOY_TARGET_DIR}/shared"
