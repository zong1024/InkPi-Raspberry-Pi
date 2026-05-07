#!/usr/bin/env bash
# Curl-friendly Raspberry Pi installer for InkPi.
#
# Example:
#   curl -fsSL https://raw.githubusercontent.com/zong1024/InkPi-Raspberry-Pi/master/scripts/install_rpi_oneclick.sh | bash
#
# Useful overrides:
#   INKPI_REPO_URL=https://github.com/zong1024/InkPi-Raspberry-Pi.git
#   INKPI_BRANCH=master
#   INKPI_DIR="$HOME/InkPi-Raspberry-Pi"
#   CALLIGRAPHY_STYLE=kaishu|xingshu
#   INSTALL_KIOSK=1
#   START_APP=1
#   MODEL_SOURCE=/path/to/quality_scorer.onnx
#   PADDLEPADDLE_PACKAGE=paddlepaddle
#   INKPI_FORCE_REFRESH=1
#   INKPI_SKIP_HEALTHCHECK=1
#   INKPI_DISPLAY_ROTATION=inverted|normal|left|right

set -euo pipefail

REPO_URL="${INKPI_REPO_URL:-https://github.com/zong1024/InkPi-Raspberry-Pi.git}"
BRANCH="${INKPI_BRANCH:-master}"
INSTALL_DIR="${INKPI_DIR:-${HOME}/InkPi-Raspberry-Pi}"
CALLIGRAPHY_STYLE="${CALLIGRAPHY_STYLE:-kaishu}"
INSTALL_KIOSK="${INSTALL_KIOSK:-1}"
START_APP="${START_APP:-0}"
RUN_SELF_TEST="${RUN_SELF_TEST:-0}"
INKPI_UI_MODE="${INKPI_UI_MODE:-qt}"
INKPI_CLOUD_DEVICE_NAME="${INKPI_CLOUD_DEVICE_NAME:-InkPi-Raspberry-Pi}"
INKPI_FORCE_REFRESH="${INKPI_FORCE_REFRESH:-0}"
INKPI_DISPLAY_ROTATION="${INKPI_DISPLAY_ROTATION:-inverted}"

log() {
    printf '\n[%s] %s\n' "$(date '+%H:%M:%S')" "$*"
}

die() {
    echo "Error: $*" >&2
    exit 1
}

quote_env() {
    printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"
}

upsert_env() {
    local key="$1"
    local value="$2"
    local file="$3"
    local tmp
    tmp="$(mktemp)"
    touch "$file"
    grep -v -E "^(export[[:space:]]+)?${key}=" "$file" > "$tmp" || true
    printf 'export %s=%s\n' "$key" "$(quote_env "$value")" >> "$tmp"
    mv "$tmp" "$file"
}

clone_repository() {
    git clone --branch "${BRANCH}" "${REPO_URL}" "${INSTALL_DIR}"
}

restore_runtime_data() {
    local backup_dir="$1"

    if [ -d "${backup_dir}/.inkpi" ] && [ ! -d "${INSTALL_DIR}/.inkpi" ]; then
        cp -a "${backup_dir}/.inkpi" "${INSTALL_DIR}/.inkpi"
        echo "Restored .inkpi runtime settings from ${backup_dir}."
    fi

    if [ -d "${backup_dir}/data" ] && [ ! -d "${INSTALL_DIR}/data" ]; then
        cp -a "${backup_dir}/data" "${INSTALL_DIR}/data"
        echo "Restored local data directory from ${backup_dir}."
    fi
}

backup_and_reclone() {
    local reason="$1"
    local backup_dir="${INSTALL_DIR}.backup.$(date +%Y%m%d%H%M%S)"

    echo "Warning: ${reason}"
    echo "Backing up existing install to ${backup_dir}"
    mv "${INSTALL_DIR}" "${backup_dir}"
    clone_repository
    restore_runtime_data "${backup_dir}"
}

has_required_deploy_files() {
    [ -f "${INSTALL_DIR}/deploy_rpi.sh" ] \
        && [ -d "${INSTALL_DIR}/scripts" ] \
        && [ -f "${INSTALL_DIR}/scripts/install_kiosk.sh" ]
}

case "$CALLIGRAPHY_STYLE" in
    kaishu|xingshu) ;;
    kai|regular) CALLIGRAPHY_STYLE="kaishu" ;;
    xing|running) CALLIGRAPHY_STYLE="xingshu" ;;
    *) die "CALLIGRAPHY_STYLE must be kaishu or xingshu." ;;
esac

if [ -f /proc/device-tree/model ] && ! tr -d '\0' < /proc/device-tree/model | grep -q "Raspberry Pi"; then
    echo "Warning: this installer is intended for Raspberry Pi hardware."
elif [ ! -f /proc/device-tree/model ]; then
    echo "Warning: /proc/device-tree/model not found. Continuing anyway."
fi

log "Installing bootstrap packages"
sudo apt-get update
sudo apt-get install -y git ca-certificates curl

log "Preparing repository at ${INSTALL_DIR}"
if [ -d "${INSTALL_DIR}/.git" ]; then
    if [ "${INKPI_FORCE_REFRESH}" = "1" ]; then
        backup_and_reclone "INKPI_FORCE_REFRESH=1 was set."
    elif git -C "${INSTALL_DIR}" diff --quiet \
        && git -C "${INSTALL_DIR}" diff --cached --quiet \
        && [ -z "$(git -C "${INSTALL_DIR}" ls-files --others --exclude-standard)" ]; then
        git -C "${INSTALL_DIR}" fetch origin "${BRANCH}"
        git -C "${INSTALL_DIR}" checkout "${BRANCH}"
        git -C "${INSTALL_DIR}" pull --ff-only origin "${BRANCH}"
    else
        echo "Warning: ${INSTALL_DIR} has local changes. Skipping git update to avoid overwriting them."
    fi

    if ! has_required_deploy_files; then
        backup_and_reclone "${INSTALL_DIR} is missing current deployment scripts."
    fi
elif [ -e "${INSTALL_DIR}" ]; then
    die "${INSTALL_DIR} already exists but is not a git repository. Move it away or set INKPI_DIR."
else
    clone_repository
fi

cd "${INSTALL_DIR}"

log "Writing InkPi runtime settings"
mkdir -p .inkpi
cat > .inkpi/runtime_settings.json <<EOF
{
  "calligraphy_style": "${CALLIGRAPHY_STYLE}"
}
EOF

upsert_env "INKPI_UI_MODE" "${INKPI_UI_MODE}" ".inkpi/cloud.env"
upsert_env "INKPI_CALLIGRAPHY_STYLE" "${CALLIGRAPHY_STYLE}" ".inkpi/cloud.env"
upsert_env "INKPI_CLOUD_DEVICE_NAME" "${INKPI_CLOUD_DEVICE_NAME}" ".inkpi/cloud.env"
upsert_env "INKPI_DISPLAY_ROTATION" "${INKPI_DISPLAY_ROTATION}" ".inkpi/cloud.env"
if [ -n "${INKPI_CLOUD_BACKEND_URL:-}" ]; then
    upsert_env "INKPI_CLOUD_BACKEND_URL" "${INKPI_CLOUD_BACKEND_URL}" ".inkpi/cloud.env"
fi
if [ -n "${INKPI_CLOUD_DEVICE_KEY:-}" ]; then
    upsert_env "INKPI_CLOUD_DEVICE_KEY" "${INKPI_CLOUD_DEVICE_KEY}" ".inkpi/cloud.env"
fi

chmod +x deploy_rpi.sh scripts/*.sh

log "Running InkPi deployment"
env \
    INKPI_BRANCH="${BRANCH}" \
    INKPI_UI_MODE="${INKPI_UI_MODE}" \
    INKPI_CALLIGRAPHY_STYLE="${CALLIGRAPHY_STYLE}" \
    INSTALL_KIOSK="${INSTALL_KIOSK}" \
    START_APP="${START_APP}" \
    RUN_SELF_TEST="${RUN_SELF_TEST}" \
    INKPI_CLOUD_DEVICE_NAME="${INKPI_CLOUD_DEVICE_NAME}" \
    INKPI_SKIP_HEALTHCHECK="${INKPI_SKIP_HEALTHCHECK:-0}" \
    INKPI_DISPLAY_ROTATION="${INKPI_DISPLAY_ROTATION}" \
    MODEL_SOURCE="${MODEL_SOURCE:-}" \
    PADDLEPADDLE_PACKAGE="${PADDLEPADDLE_PACKAGE:-paddlepaddle}" \
    bash ./deploy_rpi.sh

log "InkPi deployment complete"
echo "Project: ${INSTALL_DIR}"
echo "UI mode: ${INKPI_UI_MODE}"
echo "Style:   ${CALLIGRAPHY_STYLE}"
echo "Run:     cd ${INSTALL_DIR} && scripts/inkpi-launch.sh"
if [ "${INSTALL_KIOSK}" = "1" ]; then
    echo "Kiosk is installed. Reboot or log in on tty1 to auto-start Qt."
fi
