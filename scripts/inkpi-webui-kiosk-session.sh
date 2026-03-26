#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
APP_URL="${INKPI_WEBUI_URL:-http://127.0.0.1:5000}"

xset s off
xset -dpms
xset s noblank

if command -v unclutter >/dev/null 2>&1; then
    unclutter -idle 0.5 -root >/dev/null 2>&1 &
fi

if command -v openbox-session >/dev/null 2>&1; then
    openbox-session >/dev/null 2>&1 &
fi

wait_for_backend() {
    local retries=80
    while [ "${retries}" -gt 0 ]; do
        if command -v curl >/dev/null 2>&1; then
            if curl -fsS "${APP_URL}/api/health" >/dev/null 2>&1; then
                return 0
            fi
        else
            if python - <<'PY'
import sys
import urllib.request

try:
    urllib.request.urlopen("http://127.0.0.1:5000/api/health", timeout=1)
except Exception:
    sys.exit(1)
sys.exit(0)
PY
            then
                return 0
            fi
        fi
        retries=$((retries - 1))
        sleep 1
    done
    return 1
}

launch_browser() {
    if command -v chromium-browser >/dev/null 2>&1; then
        chromium-browser --kiosk --incognito --noerrdialogs --disable-infobars --check-for-update-interval=31536000 "${APP_URL}"
        return
    fi

    if command -v chromium >/dev/null 2>&1; then
        chromium --kiosk --incognito --noerrdialogs --disable-infobars --check-for-update-interval=31536000 "${APP_URL}"
        return
    fi

    if command -v google-chrome >/dev/null 2>&1; then
        google-chrome --kiosk --incognito --noerrdialogs --disable-infobars "${APP_URL}"
        return
    fi

    echo "No supported kiosk browser found."
    return 1
}

while true; do
    "${PROJECT_DIR}/scripts/inkpi-webui-launch.sh" &
    backend_pid=$!

    if ! wait_for_backend; then
        kill "${backend_pid}" >/dev/null 2>&1 || true
        wait "${backend_pid}" >/dev/null 2>&1 || true
        sleep 2
        continue
    fi

    if ! launch_browser; then
        kill "${backend_pid}" >/dev/null 2>&1 || true
        wait "${backend_pid}" >/dev/null 2>&1 || true
        exit 1
    fi

    kill "${backend_pid}" >/dev/null 2>&1 || true
    wait "${backend_pid}" >/dev/null 2>&1 || true

    if [ "${INKPI_KIOSK_ONCE:-0}" = "1" ]; then
        exit 0
    fi

    sleep 2
done
