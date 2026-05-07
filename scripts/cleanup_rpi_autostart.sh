#!/bin/bash
# Remove legacy InkPi autostart entries before installing the current Qt kiosk flow.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET_USER="${SUDO_USER:-$USER}"
TARGET_HOME="$(getent passwd "${TARGET_USER}" | cut -d: -f6)"
STAMP="$(date +%Y%m%d%H%M%S)"

if [ "$(id -u)" -eq 0 ]; then
    SUDO=""
else
    SUDO="sudo"
fi

if [ -z "${TARGET_HOME}" ] || [ ! -d "${TARGET_HOME}" ]; then
    echo "Failed to resolve target home for ${TARGET_USER}."
    exit 1
fi

log() {
    echo "[cleanup] $*"
}

clean_shell_file() {
    local path="$1"
    local tmp

    if [ ! -f "${path}" ]; then
        return 0
    fi

    tmp="$(mktemp)"
    awk '
        /^# >>> InkPi/ { skip = 1; next }
        /^# <<< InkPi/ { skip = 0; next }
        /InkPi-Raspberry-Pi/ { next }
        /inkpi-(launch|webui-launch|kiosk-session|webui-kiosk-session)\.sh/ { next }
        /python[[:space:]]+(-m[[:space:]]+web_ui\.app|main\.py)/ && /[Ii]nk[Pp]i/ { next }
        !skip { print }
    ' "${path}" > "${tmp}"

    if ! cmp -s "${path}" "${tmp}"; then
        cp "${path}" "${path}.bak.${STAMP}"
        mv "${tmp}" "${path}"
        if [ "$(id -u)" -eq 0 ]; then
            chown "${TARGET_USER}:${TARGET_USER}" "${path}"
        fi
        log "cleaned ${path}"
    else
        rm -f "${tmp}"
    fi
}

clean_crontab() {
    local tmp
    local cleaned

    if ! command -v crontab >/dev/null 2>&1; then
        return 0
    fi

    tmp="$(mktemp)"
    cleaned="$(mktemp)"
    if [ "$(id -u)" -eq 0 ]; then
        if ! crontab -u "${TARGET_USER}" -l > "${tmp}" 2>/dev/null; then
            rm -f "${tmp}" "${cleaned}"
            return 0
        fi
    elif [ "${TARGET_USER}" = "$USER" ]; then
        if ! crontab -l > "${tmp}" 2>/dev/null; then
            rm -f "${tmp}" "${cleaned}"
            return 0
        fi
    else
        rm -f "${tmp}" "${cleaned}"
        return 0
    fi

    grep -v -E 'InkPi-Raspberry-Pi|inkpi-(launch|webui-launch|kiosk-session|webui-kiosk-session)\.sh|[Ii]nk[Pp]i.*(web_ui\.app|python[[:space:]]+main\.py)' \
        "${tmp}" > "${cleaned}" || true

    if ! cmp -s "${tmp}" "${cleaned}"; then
        if [ "$(id -u)" -eq 0 ]; then
            crontab -u "${TARGET_USER}" "${cleaned}"
        else
            crontab "${cleaned}"
        fi
        log "cleaned ${TARGET_USER} crontab"
    fi

    rm -f "${tmp}" "${cleaned}"
}

disable_legacy_systemd_units() {
    local units=(
        inkpi.service
        inkpi-webui.service
        inkpi-kiosk.service
        inkpi-webui-kiosk.service
    )
    local unit
    local path

    if command -v systemctl >/dev/null 2>&1; then
        for unit in "${units[@]}"; do
            ${SUDO} systemctl disable --now "${unit}" >/dev/null 2>&1 || true
            systemctl --user disable --now "${unit}" >/dev/null 2>&1 || true
        done
    fi

    for unit in "${units[@]}"; do
        for path in \
            "/etc/systemd/system/${unit}" \
            "${TARGET_HOME}/.config/systemd/user/${unit}"
        do
            if [ -f "${path}" ]; then
                if [ "${path#/etc/}" != "${path}" ]; then
                    ${SUDO} mv "${path}" "${path}.disabled-by-inkpi.${STAMP}"
                else
                    mv "${path}" "${path}.disabled-by-inkpi.${STAMP}"
                fi
                log "disabled ${path}"
            fi
        done
    done

    ${SUDO} systemctl daemon-reload >/dev/null 2>&1 || true
}

clean_desktop_autostart() {
    local paths=(
        "${TARGET_HOME}/.config/autostart/inkpi.desktop"
        "${TARGET_HOME}/.config/autostart/inkpi-webui.desktop"
        "${TARGET_HOME}/.config/autostart/InkPi.desktop"
        "/etc/xdg/autostart/inkpi.desktop"
        "/etc/xdg/autostart/inkpi-webui.desktop"
        "/etc/xdg/autostart/InkPi.desktop"
    )
    local path

    for path in "${paths[@]}"; do
        if [ -f "${path}" ]; then
            if [ "${path#/etc/}" != "${path}" ]; then
                ${SUDO} mv "${path}" "${path}.disabled-by-inkpi.${STAMP}"
            else
                mv "${path}" "${path}.disabled-by-inkpi.${STAMP}"
            fi
            log "disabled ${path}"
        fi
    done
}

log "removing legacy InkPi autostart entries for ${TARGET_USER}"
clean_shell_file "${TARGET_HOME}/.bash_profile"
clean_shell_file "${TARGET_HOME}/.profile"
clean_shell_file "${TARGET_HOME}/.bashrc"
clean_shell_file "${TARGET_HOME}/.xinitrc"
clean_crontab
disable_legacy_systemd_units
clean_desktop_autostart

log "legacy autostart cleanup finished"
