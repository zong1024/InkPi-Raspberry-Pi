#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [ -f "${PROJECT_DIR}/.inkpi/cloud.env" ]; then
    # shellcheck disable=SC1091
    source "${PROJECT_DIR}/.inkpi/cloud.env"
fi

if [ "${INKPI_UI_MODE:-webui}" = "webui" ]; then
    exec "${PROJECT_DIR}/scripts/inkpi-webui-kiosk-session.sh"
fi

apply_display_rotation() {
    local rotation="${INKPI_DISPLAY_ROTATION:-inverted}"
    local output="${INKPI_DISPLAY_OUTPUT:-}"
    local matrix="1 0 0 0 1 0 0 0 1"
    local pointer_id

    case "${rotation}" in
        normal|"")
            matrix="1 0 0 0 1 0 0 0 1"
            ;;
        inverted|180)
            rotation="inverted"
            matrix="-1 0 1 0 -1 1 0 0 1"
            ;;
        left|90)
            rotation="left"
            matrix="0 -1 1 1 0 0 0 0 1"
            ;;
        right|270)
            rotation="right"
            matrix="0 1 0 -1 0 1 0 0 1"
            ;;
        *)
            echo "Unsupported INKPI_DISPLAY_ROTATION=${rotation}; using inverted."
            rotation="inverted"
            matrix="-1 0 1 0 -1 1 0 0 1"
            ;;
    esac

    if command -v xrandr >/dev/null 2>&1; then
        if [ -z "${output}" ]; then
            output="$(xrandr --query | awk '/ connected/{print $1; exit}')"
        fi
        if [ -n "${output}" ]; then
            xrandr --output "${output}" --rotate "${rotation}" >/dev/null 2>&1 || true
        fi
    fi

    if command -v xinput >/dev/null 2>&1; then
        xinput --list --id-only 2>/dev/null | while read -r pointer_id; do
            xinput set-prop "${pointer_id}" "Coordinate Transformation Matrix" ${matrix} >/dev/null 2>&1 || true
        done
    fi
}

xset s off
xset -dpms
xset s noblank
apply_display_rotation

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
