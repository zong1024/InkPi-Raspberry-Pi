#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/_server_runtime.sh"

cd "${PROJECT_DIR}"

start_process() {
    local name="$1"
    local launcher="$2"
    local pid_file="${PID_DIR}/${name}.pid"
    local log_file="${LOG_DIR}/${name}.log"

    if [ -f "${pid_file}" ]; then
        local existing_pid
        existing_pid="$(cat "${pid_file}")"
        if is_pid_running "${existing_pid}"; then
            echo "${name} is already running with PID ${existing_pid}."
            return 0
        fi
        rm -f "${pid_file}"
    fi

    nohup bash "${launcher}" >> "${log_file}" 2>&1 &
    local pid=$!
    echo "${pid}" > "${pid_file}"
    echo "Started ${name} (PID ${pid})."
}

wait_for_http() {
    local url="$1"
    local attempts="${2:-30}"
    local index
    for index in $(seq 1 "${attempts}"); do
        if command -v curl >/dev/null 2>&1; then
            if curl -fsS "${url}" >/dev/null 2>&1; then
                return 0
            fi
        else
            if python - "${url}" <<'PY'
import sys
import urllib.request

url = sys.argv[1]
try:
    urllib.request.urlopen(url, timeout=1)
except Exception:
    sys.exit(1)
sys.exit(0)
PY
                return 0
            fi
        fi
        sleep 1
    done
    return 1
}

start_process "cloud_api" "${SCRIPT_DIR}/run_cloud_api.sh"
wait_for_http "http://127.0.0.1:${INKPI_CLOUD_PORT}/api/health" 45

start_process "web_ui" "${SCRIPT_DIR}/run_web_ui.sh"
wait_for_http "http://127.0.0.1:${INKPI_WEB_PORT}/api/health" 45

start_process "qt_ui" "${SCRIPT_DIR}/run_qt_xfce.sh"
sleep 3

echo "InkPi server stack started."
echo "WebUI: http://127.0.0.1:${INKPI_WEB_PORT}"
echo "Cloud API: http://127.0.0.1:${INKPI_CLOUD_PORT}"
