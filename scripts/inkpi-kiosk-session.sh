#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [ "${INKPI_UI_MODE:-webui}" = "webui" ]; then
    exec "${PROJECT_DIR}/scripts/inkpi-webui-kiosk-session.sh"
fi

xset s off
xset -dpms
xset s noblank

if command -v unclutter >/dev/null 2>&1; then
    unclutter -idle 0.5 -root >/dev/null 2>&1 &
fi

if command -v openbox-session >/dev/null 2>&1; then
    openbox-session >/dev/null 2>&1 &
fi

while true; do
    "${PROJECT_DIR}/scripts/inkpi-launch.sh"
    if [ "${INKPI_KIOSK_ONCE:-0}" = "1" ]; then
        exit 0
    fi
    sleep 2
done
