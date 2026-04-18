#!/bin/bash
set -euo pipefail

ARTIFACT_PATH="${1:-}"
DEPLOY_MODE="${INKPI_DEPLOY_MODE:-backend}"
DEPLOY_ROOT="${INKPI_DEPLOY_ROOT:-${HOME}/inkpi-device}"
KEEP_RELEASES="${INKPI_KEEP_RELEASES:-3}"

if [ -z "${ARTIFACT_PATH}" ]; then
    echo "Usage: bash scripts/install_rpi_release.sh /path/to/inkpi-rpi-release.tar.gz" >&2
    exit 1
fi

if [ ! -f "${ARTIFACT_PATH}" ]; then
    echo "Release artifact does not exist: ${ARTIFACT_PATH}" >&2
    exit 1
fi

case "${DEPLOY_MODE}" in
    backend|server) ;;
    *)
        echo "Unsupported deploy mode: ${DEPLOY_MODE}" >&2
        exit 1
        ;;
esac

case "${KEEP_RELEASES}" in
    ''|*[!0-9]*)
        echo "INKPI_KEEP_RELEASES must be a non-negative integer." >&2
        exit 1
        ;;
esac

RELEASES_DIR="${DEPLOY_ROOT}/releases"
PACKAGES_DIR="${DEPLOY_ROOT}/packages"
SHARED_DIR="${DEPLOY_ROOT}/shared"
SHARED_DATA_DIR="${SHARED_DIR}/data"
SHARED_CACHE_DIR="${SHARED_DIR}/.inkpi"
SHARED_LOGS_DIR="${SHARED_DIR}/logs"
RUNTIME_LOG_DIR="${SHARED_DIR}/runtime_logs"
RUNTIME_PID_DIR="${SHARED_DIR}/runtime_pids"
CURRENT_LINK="${DEPLOY_ROOT}/current"
ARTIFACT_NAME="$(basename "${ARTIFACT_PATH}")"
RELEASE_NAME="${INKPI_RELEASE_NAME:-${ARTIFACT_NAME%.tar.gz}}"
STAGING_DIR="${RELEASES_DIR}/${RELEASE_NAME}.staging"
RELEASE_DIR="${RELEASES_DIR}/${RELEASE_NAME}"

if [ -e "${CURRENT_LINK}" ] && [ ! -L "${CURRENT_LINK}" ]; then
    echo "${CURRENT_LINK} exists but is not a symlink. Refusing to continue." >&2
    exit 1
fi

mkdir -p \
    "${RELEASES_DIR}" \
    "${PACKAGES_DIR}" \
    "${SHARED_DATA_DIR}/images" \
    "${SHARED_DATA_DIR}/processed" \
    "${SHARED_CACHE_DIR}" \
    "${SHARED_LOGS_DIR}" \
    "${RUNTIME_LOG_DIR}" \
    "${RUNTIME_PID_DIR}"

copy_package() {
    cp -f "${ARTIFACT_PATH}" "${PACKAGES_DIR}/${ARTIFACT_NAME}"
}

attach_shared_paths() {
    local release_path="$1"
    rm -rf "${release_path}/data" "${release_path}/.inkpi" "${release_path}/logs"
    ln -s "${SHARED_DATA_DIR}" "${release_path}/data"
    ln -s "${SHARED_CACHE_DIR}" "${release_path}/.inkpi"
    ln -s "${SHARED_LOGS_DIR}" "${release_path}/logs"
}

resolve_current_release() {
    if [ -L "${CURRENT_LINK}" ]; then
        readlink "${CURRENT_LINK}"
    fi
}

mode_script_name() {
    local prefix="$1"
    case "${DEPLOY_MODE}" in
        backend) echo "${prefix}_backend_stack.sh" ;;
        server) echo "${prefix}_server_stack.sh" ;;
    esac
}

run_release_script() {
    local release_path="$1"
    local script_name="$2"
    if [ ! -x "${release_path}/scripts/${script_name}" ]; then
        echo "Missing executable script: ${release_path}/scripts/${script_name}" >&2
        return 1
    fi

    export INKPI_LOG_DIR="${RUNTIME_LOG_DIR}"
    export INKPI_PID_DIR="${RUNTIME_PID_DIR}"
    bash "${release_path}/scripts/${script_name}"
}

health_check_release() {
    local release_path="$1"
    export INKPI_LOG_DIR="${RUNTIME_LOG_DIR}"
    export INKPI_PID_DIR="${RUNTIME_PID_DIR}"
    bash "${release_path}/scripts/health_check_stack.sh" "${DEPLOY_MODE}"
}

rollback_to_previous() {
    local previous_release="$1"
    local failed_release="$2"

    echo "Deployment verification failed. Rolling back..."
    if [ -d "${failed_release}" ]; then
        run_release_script "${failed_release}" "$(mode_script_name stop)" || true
    fi

    if [ -n "${previous_release}" ] && [ -d "${previous_release}" ]; then
        ln -sfn "${previous_release}" "${CURRENT_LINK}"
        run_release_script "${previous_release}" "$(mode_script_name start)" || true
        health_check_release "${previous_release}" || true
    else
        rm -f "${CURRENT_LINK}"
    fi
}

cleanup_old_releases() {
    local keep_limit="$1"
    local active_release=""
    active_release="$(resolve_current_release || true)"
    mapfile -t releases < <(find "${RELEASES_DIR}" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' | sort -nr | awk '{print $2}')
    local kept=0
    for release_path in "${releases[@]}"; do
        if [ -n "${active_release}" ] && [ "${release_path}" = "${active_release}" ]; then
            continue
        fi
        kept=$((kept + 1))
        if [ "${kept}" -le "${keep_limit}" ]; then
            continue
        fi
        rm -rf "${release_path}"
    done
}

copy_package

rm -rf "${STAGING_DIR}"
if [ -e "${RELEASE_DIR}" ]; then
    echo "Release directory already exists: ${RELEASE_DIR}" >&2
    exit 1
fi

mkdir -p "${STAGING_DIR}"
tar -xzf "${ARTIFACT_PATH}" -C "${STAGING_DIR}"
attach_shared_paths "${STAGING_DIR}"
chmod +x "${STAGING_DIR}/scripts/"*.sh

if [ ! -x "${STAGING_DIR}/scripts/setup_backend_runtime.sh" ] || [ ! -x "${STAGING_DIR}/scripts/setup_server_runtime.sh" ]; then
    echo "Release artifact is missing required runtime scripts." >&2
    exit 1
fi

echo "[1/5] Preparing release runtime..."
run_release_script "${STAGING_DIR}" "$(mode_script_name setup)"

mv "${STAGING_DIR}" "${RELEASE_DIR}"

PREVIOUS_RELEASE="$(resolve_current_release || true)"

echo "[2/5] Stopping current stack..."
if [ -n "${PREVIOUS_RELEASE}" ] && [ -d "${PREVIOUS_RELEASE}" ]; then
    run_release_script "${PREVIOUS_RELEASE}" "$(mode_script_name stop)" || true
fi

echo "[3/5] Switching current release..."
ln -sfn "${RELEASE_DIR}" "${CURRENT_LINK}"

echo "[4/5] Starting ${DEPLOY_MODE} stack..."
if ! run_release_script "${CURRENT_LINK}" "$(mode_script_name start)"; then
    rollback_to_previous "${PREVIOUS_RELEASE}" "${RELEASE_DIR}"
    exit 1
fi

echo "[5/5] Running health check..."
if ! health_check_release "${CURRENT_LINK}"; then
    rollback_to_previous "${PREVIOUS_RELEASE}" "${RELEASE_DIR}"
    exit 1
fi

cleanup_old_releases "${KEEP_RELEASES}"

echo "Release deployed successfully."
echo "  deploy_root: ${DEPLOY_ROOT}"
echo "  release: ${RELEASE_DIR}"
echo "  mode: ${DEPLOY_MODE}"
