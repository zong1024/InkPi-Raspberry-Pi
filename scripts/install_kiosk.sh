#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET_USER="${SUDO_USER:-$USER}"
TARGET_HOME="$(getent passwd "${TARGET_USER}" | cut -d: -f6)"
PROFILE_PATH="${TARGET_HOME}/.bash_profile"
PROFILE_TMP="$(mktemp)"
MARK_BEGIN="# >>> InkPi kiosk >>>"
MARK_END="# <<< InkPi kiosk <<<"

if [ -z "${TARGET_HOME}" ] || [ ! -d "${TARGET_HOME}" ]; then
    echo "Failed to resolve target home for ${TARGET_USER}."
    exit 1
fi

mkdir -p "${TARGET_HOME}"
touch "${PROFILE_PATH}"

awk -v begin="${MARK_BEGIN}" -v end="${MARK_END}" '
    $0 == begin { skip = 1; next }
    $0 == end { skip = 0; next }
    $0 ~ /^[[:space:]]*startx([[:space:]].*)?$/ { next }
    !skip { print }
' "${PROFILE_PATH}" > "${PROFILE_TMP}"

cat <<EOF >> "${PROFILE_TMP}"
${MARK_BEGIN}
if [ -z "\${SSH_TTY:-}" ] && [ -z "\${DISPLAY:-}" ] && [ "\$(tty)" = "/dev/tty1" ]; then
    exec startx "${PROJECT_DIR}/scripts/inkpi-kiosk-session.sh" -- :0 vt1 -keeptty
fi
${MARK_END}
EOF

mv "${PROFILE_TMP}" "${PROFILE_PATH}"
chown "${TARGET_USER}:${TARGET_USER}" "${PROFILE_PATH}"
chmod +x "${PROJECT_DIR}/scripts/inkpi-launch.sh" "${PROJECT_DIR}/scripts/inkpi-kiosk-session.sh"

echo "InkPi kiosk startup has been installed for ${TARGET_USER}."
echo "On the next tty1 login or reboot, the app will launch fullscreen automatically."
