#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${INKPI_VENV_DIR:-${PROJECT_DIR}/venv}"
LOG_DIR="${INKPI_LOG_DIR:-${PROJECT_DIR}/data/runtime_logs}"
PID_DIR="${INKPI_PID_DIR:-${PROJECT_DIR}/data/runtime_pids}"

mkdir -p "${LOG_DIR}" "${PID_DIR}"

export PROJECT_DIR
export VENV_DIR
export LOG_DIR
export PID_DIR
export PYTHONUNBUFFERED=1
export QT_AUTO_SCREEN_SCALE_FACTOR=0
export QT_SCALE_FACTOR=1
export INKPI_WEB_HOST="${INKPI_WEB_HOST:-0.0.0.0}"
export INKPI_WEB_PORT="${INKPI_WEB_PORT:-5000}"
export INKPI_CLOUD_PORT="${INKPI_CLOUD_PORT:-5001}"
export INKPI_WINDOW_WIDTH="${INKPI_WINDOW_WIDTH:-480}"
export INKPI_WINDOW_HEIGHT="${INKPI_WINDOW_HEIGHT:-320}"
export INKPI_FULLSCREEN="${INKPI_FULLSCREEN:-0}"

if [ -d "${VENV_DIR}" ]; then
    # shellcheck disable=SC1091
    source "${VENV_DIR}/bin/activate"
fi

if [ -f "${PROJECT_DIR}/.inkpi/cloud.env" ]; then
    # shellcheck disable=SC1091
    source "${PROJECT_DIR}/.inkpi/cloud.env"
fi

if [ -f "${PROJECT_DIR}/.inkpi/server.env" ]; then
    # shellcheck disable=SC1091
    source "${PROJECT_DIR}/.inkpi/server.env"
fi

find_xfce_session_pid() {
    pgrep -u "${USER}" -n -f "xfce4-session|xfdesktop|xfwm4" || true
}

session_env_value() {
    local key="$1"
    local session_pid
    session_pid="$(find_xfce_session_pid)"
    if [ -z "${session_pid}" ] || [ ! -r "/proc/${session_pid}/environ" ]; then
        return 1
    fi
    tr '\0' '\n' < "/proc/${session_pid}/environ" | sed -n "s/^${key}=//p" | tail -n 1
}

ensure_xfce_runtime() {
    if [ -z "${DISPLAY:-}" ]; then
        DISPLAY="$(session_env_value DISPLAY || true)"
    fi
    if [ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ]; then
        DBUS_SESSION_BUS_ADDRESS="$(session_env_value DBUS_SESSION_BUS_ADDRESS || true)"
    fi
    if [ -z "${XDG_RUNTIME_DIR:-}" ]; then
        XDG_RUNTIME_DIR="$(session_env_value XDG_RUNTIME_DIR || true)"
    fi
    if [ -z "${XDG_RUNTIME_DIR:-}" ]; then
        XDG_RUNTIME_DIR="/run/user/$(id -u)"
    fi
    if [ -z "${DISPLAY:-}" ]; then
        echo "No XFCE DISPLAY detected. Start an XFCE session first." >&2
        return 1
    fi
    export DISPLAY
    export DBUS_SESSION_BUS_ADDRESS
    export XDG_RUNTIME_DIR
}

is_pid_running() {
    local pid="$1"
    [ -n "${pid}" ] && kill -0 "${pid}" >/dev/null 2>&1
}
