#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/_server_runtime.sh"

stop_process() {
    local name="$1"
    local pid_file="${PID_DIR}/${name}.pid"
    if [ ! -f "${pid_file}" ]; then
        echo "${name} is not running."
        return 0
    fi

    local pid
    pid="$(cat "${pid_file}")"
    if is_pid_running "${pid}"; then
        kill "${pid}" >/dev/null 2>&1 || true
        sleep 1
        if is_pid_running "${pid}"; then
            kill -9 "${pid}" >/dev/null 2>&1 || true
        fi
        echo "Stopped ${name} (PID ${pid})."
    else
        echo "${name} was already stopped."
    fi
    rm -f "${pid_file}"
}

stop_process "qt_ui"
stop_process "web_ui"
stop_process "cloud_api"
