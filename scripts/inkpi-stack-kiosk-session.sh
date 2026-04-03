#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
QT_PID_FILE="${PROJECT_DIR}/data/runtime_pids/qt_ui.pid"

cleanup_stack() {
    bash "${PROJECT_DIR}/scripts/stop_server_stack.sh" >/dev/null 2>&1 || true
}

wait_for_qt_exit() {
    while true; do
        if [ ! -f "${QT_PID_FILE}" ]; then
            return 0
        fi

        local qt_pid
        qt_pid="$(cat "${QT_PID_FILE}" 2>/dev/null || true)"
        if [ -z "${qt_pid}" ] || ! kill -0 "${qt_pid}" >/dev/null 2>&1; then
            return 0
        fi
        sleep 2
    done
}

trap cleanup_stack EXIT INT TERM

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
    cleanup_stack
    bash "${PROJECT_DIR}/scripts/start_server_stack.sh"
    wait_for_qt_exit
    cleanup_stack

    if [ "${INKPI_KIOSK_ONCE:-0}" = "1" ]; then
        exit 0
    fi

    sleep 2
done
