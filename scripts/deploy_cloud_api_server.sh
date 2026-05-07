#!/usr/bin/env bash
# Deploy only the InkPi cloud history API to a public Linux server.
# This script does not touch nginx/caddy/apache/blog ports. It creates an
# isolated systemd service that listens on INKPI_CLOUD_PORT, default 23334.

set -euo pipefail

REPO_URL="${INKPI_REPO_URL:-https://github.com/zong1024/InkPi-Raspberry-Pi.git}"
BRANCH="${INKPI_BRANCH:-master}"
APP_DIR="${INKPI_CLOUD_APP_DIR:-/opt/inkpi-cloud-api}"
ENV_FILE="${INKPI_CLOUD_ENV_FILE:-/etc/inkpi-cloud-api.env}"
SERVICE_NAME="${INKPI_CLOUD_SERVICE_NAME:-inkpi-cloud-api}"
SERVICE_USER="${INKPI_CLOUD_SERVICE_USER:-inkpi}"
PORT="${INKPI_CLOUD_PORT:-23334}"

if [ "$(id -u)" -ne 0 ]; then
    SUDO="sudo"
else
    SUDO=""
fi

USER_DEVICE_KEY="${INKPI_CLOUD_DEVICE_KEY:-}"
USER_DEMO_USER="${INKPI_CLOUD_DEMO_USER:-}"
USER_DEMO_PASSWORD="${INKPI_CLOUD_DEMO_PASSWORD:-}"
USER_DISPLAY_NAME="${INKPI_CLOUD_DEMO_DISPLAY_NAME:-}"

log() {
    printf '\n[%s] %s\n' "$(date '+%H:%M:%S')" "$*"
}

quote_env() {
    printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"
}

random_secret() {
    python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
}

if [ -f "${ENV_FILE}" ]; then
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
fi

DEVICE_KEY="${USER_DEVICE_KEY:-${INKPI_CLOUD_DEVICE_KEY:-$(random_secret)}}"
DEMO_USER="${USER_DEMO_USER:-${INKPI_CLOUD_DEMO_USER:-inkpi}}"
DEMO_PASSWORD="${USER_DEMO_PASSWORD:-${INKPI_CLOUD_DEMO_PASSWORD:-$(random_secret)}}"
DISPLAY_NAME="${USER_DISPLAY_NAME:-${INKPI_CLOUD_DEMO_DISPLAY_NAME:-InkPi}}"

log "Installing system packages"
${SUDO} apt-get update
${SUDO} apt-get install -y git ca-certificates curl python3 python3-venv python3-pip

if ! id "${SERVICE_USER}" >/dev/null 2>&1; then
    log "Creating service user ${SERVICE_USER}"
    ${SUDO} useradd --system --create-home --shell /usr/sbin/nologin "${SERVICE_USER}"
fi

log "Preparing repository at ${APP_DIR}"
if [ -d "${APP_DIR}/.git" ]; then
    ${SUDO} git -C "${APP_DIR}" fetch origin "${BRANCH}"
    ${SUDO} git -C "${APP_DIR}" checkout "${BRANCH}"
    ${SUDO} git -C "${APP_DIR}" pull --ff-only origin "${BRANCH}"
elif [ -e "${APP_DIR}" ]; then
    echo "Error: ${APP_DIR} exists but is not a git repository." >&2
    exit 1
else
    ${SUDO} git clone --branch "${BRANCH}" "${REPO_URL}" "${APP_DIR}"
fi

${SUDO} chown -R "${SERVICE_USER}:${SERVICE_USER}" "${APP_DIR}"

log "Installing Python packages"
${SUDO} -u "${SERVICE_USER}" python3 -m venv "${APP_DIR}/venv"
${SUDO} -u "${SERVICE_USER}" "${APP_DIR}/venv/bin/python" -m pip install --upgrade pip
${SUDO} -u "${SERVICE_USER}" "${APP_DIR}/venv/bin/python" -m pip install \
    "Flask>=3.0.0" \
    "Werkzeug>=3.0.0" \
    "gunicorn>=22.0.0"

log "Writing environment file ${ENV_FILE}"
${SUDO} tee "${ENV_FILE}" >/dev/null <<EOF
INKPI_CLOUD_PORT=${PORT}
INKPI_CLOUD_DEVICE_KEY=$(quote_env "${DEVICE_KEY}")
INKPI_CLOUD_DEMO_USER=$(quote_env "${DEMO_USER}")
INKPI_CLOUD_DEMO_PASSWORD=$(quote_env "${DEMO_PASSWORD}")
INKPI_CLOUD_DEMO_DISPLAY_NAME=$(quote_env "${DISPLAY_NAME}")
EOF
${SUDO} chmod 600 "${ENV_FILE}"

log "Installing systemd service ${SERVICE_NAME}"
${SUDO} tee "/etc/systemd/system/${SERVICE_NAME}.service" >/dev/null <<EOF
[Unit]
Description=InkPi Cloud History API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${APP_DIR}/venv/bin/gunicorn --workers 2 --bind 0.0.0.0:${PORT} cloud_api.app:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

${SUDO} systemctl daemon-reload
${SUDO} systemctl enable --now "${SERVICE_NAME}"

if command -v ufw >/dev/null 2>&1 && ${SUDO} ufw status | grep -qi "Status: active"; then
    log "Allowing ${PORT}/tcp through ufw"
    ${SUDO} ufw allow "${PORT}/tcp"
fi

log "Health check"
curl -fsS "http://127.0.0.1:${PORT}/api/health" >/dev/null

echo ""
echo "InkPi cloud API is running."
echo "URL:        http://$(hostname -I | awk '{print $1}'):${PORT}"
echo "Device key is stored in: ${ENV_FILE}"
echo "Miniapp login user:     ${DEMO_USER}"
echo "Miniapp login password: ${DEMO_PASSWORD}"
echo ""
echo "Raspberry Pi .inkpi/cloud.env:"
echo "INKPI_CLOUD_BACKEND_URL=http://202.60.232.93:${PORT}"
echo "INKPI_CLOUD_DEVICE_KEY=${DEVICE_KEY}"
echo "INKPI_CLOUD_DEVICE_NAME=InkPi-Raspberry-Pi"
