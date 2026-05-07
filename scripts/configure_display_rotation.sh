#!/bin/bash
set -euo pipefail

rotation="${INKPI_DISPLAY_ROTATION:-inverted}"
cmdline_path="${INKPI_BOOT_CMDLINE:-}"
connector="${INKPI_DRM_CONNECTOR:-}"
mode="${INKPI_DRM_MODE:-}"
degree="180"

case "${rotation}" in
    normal|"")
        degree="0"
        ;;
    inverted|180)
        degree="180"
        ;;
    left|90)
        degree="90"
        ;;
    right|270)
        degree="270"
        ;;
    *)
        echo "Unsupported INKPI_DISPLAY_ROTATION=${rotation}; using inverted."
        degree="180"
        ;;
esac

if [ -z "${cmdline_path}" ]; then
    if [ -f /boot/firmware/cmdline.txt ]; then
        cmdline_path="/boot/firmware/cmdline.txt"
    elif [ -f /boot/cmdline.txt ]; then
        cmdline_path="/boot/cmdline.txt"
    else
        echo "Warning: no Raspberry Pi cmdline.txt found; display boot rotation was not configured."
        exit 0
    fi
fi

if [ ! -f "${cmdline_path}" ]; then
    echo "Warning: ${cmdline_path} not found; display boot rotation was not configured."
    exit 0
fi

find_connected_connector() {
    local status_path
    for status_path in /sys/class/drm/card*-*/status; do
        [ -f "${status_path}" ] || continue
        if grep -qx "connected" "${status_path}"; then
            basename "$(dirname "${status_path}")" | sed -E 's/^card[0-9]+-//'
            return 0
        fi
    done
    return 1
}

find_mode_for_connector() {
    local found_connector="$1"
    local modes_path
    for modes_path in /sys/class/drm/card*-"${found_connector}"/modes; do
        [ -f "${modes_path}" ] || continue
        sed -n '1p' "${modes_path}"
        return 0
    done
    return 1
}

if [ -z "${connector}" ]; then
    connector="$(find_connected_connector || true)"
fi

if [ -z "${connector}" ]; then
    connector="DSI-1"
    echo "Warning: no connected DRM display found; defaulting boot rotation connector to ${connector}."
fi

if [ -z "${mode}" ]; then
    mode="$(find_mode_for_connector "${connector}" || true)"
fi

if [ -z "${mode}" ]; then
    mode="480x320"
    echo "Warning: no DRM mode found for ${connector}; defaulting boot rotation mode to ${mode}."
fi

python3 - "$cmdline_path" "$connector" "$mode" "$degree" <<'PY'
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
connector = sys.argv[2]
mode = sys.argv[3]
degree = sys.argv[4]
token_prefix = f"video={connector}:"
replacement = f"{token_prefix}{mode},rotate={degree}"

content = path.read_text(encoding="utf-8").strip()
tokens = content.split()
updated = []
changed = False

for token in tokens:
    if token.startswith(token_prefix):
        body = token[len(token_prefix):]
        if "rotate=" in body:
            token = re.sub(r"rotate=[0-9]+", f"rotate={degree}", token)
        else:
            token = f"{token},rotate={degree}"
        changed = True
    updated.append(token)

if not changed:
    updated.append(replacement)

path.write_text(" ".join(updated) + "\n", encoding="utf-8")
PY

echo "Configured boot display rotation: ${connector} ${mode} rotate=${degree} in ${cmdline_path}"
