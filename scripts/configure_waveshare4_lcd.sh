#!/bin/bash
set -euo pipefail

profile="${INKPI_LCD_PROFILE:-}"
rotation="${INKPI_DISPLAY_ROTATION:-inverted}"
driver_dir="${INKPI_LCD_SHOW_DIR:-/opt/inkpi/LCD-show}"
boot_dir="${INKPI_BOOT_DIR:-}"
config_path="${INKPI_BOOT_CONFIG:-}"
cmdline_path="${INKPI_BOOT_CMDLINE:-}"
overlay_rotate=""
display_rotate="0"
calibration_suffix=""

case "${profile}" in
    waveshare4a|4inch-rpi-lcd-a|spotpear4a)
        ;;
    "")
        exit 0
        ;;
    *)
        echo "Warning: unsupported INKPI_LCD_PROFILE=${profile}; skipping Waveshare LCD configuration."
        exit 0
        ;;
esac

case "${rotation}" in
    normal|0|"")
        overlay_rotate=""
        display_rotate="0"
        calibration_suffix=""
        ;;
    inverted|180)
        overlay_rotate="270"
        display_rotate="2"
        calibration_suffix="-180"
        ;;
    left|90)
        overlay_rotate="0"
        display_rotate="1"
        calibration_suffix="-270"
        ;;
    right|270)
        overlay_rotate="180"
        display_rotate="3"
        calibration_suffix="-90"
        ;;
    *)
        echo "Unsupported INKPI_DISPLAY_ROTATION=${rotation}; using inverted."
        overlay_rotate="270"
        display_rotate="2"
        calibration_suffix="-180"
        ;;
esac

if [ -z "${boot_dir}" ]; then
    if [ -d /boot/firmware ]; then
        boot_dir="/boot/firmware"
    else
        boot_dir="/boot"
    fi
fi

if [ -z "${config_path}" ]; then
    config_path="${boot_dir}/config.txt"
fi

if [ -z "${cmdline_path}" ]; then
    cmdline_path="${boot_dir}/cmdline.txt"
fi

sudo mkdir -p "$(dirname "${driver_dir}")"
if [ -d "${driver_dir}/.git" ]; then
    sudo git -C "${driver_dir}" fetch --depth 1 origin master || true
    sudo git -C "${driver_dir}" reset --hard origin/master || true
else
    sudo rm -rf "${driver_dir}"
    sudo git clone --depth 1 https://github.com/waveshare/LCD-show.git "${driver_dir}"
fi

overlay_source="${driver_dir}/waveshare35a-overlay.dtb"
if [ ! -f "${overlay_source}" ]; then
    echo "Error: Waveshare overlay not found at ${overlay_source}."
    exit 1
fi

overlay_dir="${boot_dir}/overlays"
if [ ! -d "${overlay_dir}" ] && [ -d /boot/overlays ]; then
    overlay_dir="/boot/overlays"
fi
sudo mkdir -p "${overlay_dir}"
sudo cp "${overlay_source}" "${overlay_dir}/waveshare35a.dtbo"

sudo touch "${config_path}"
sudo cp "${config_path}" "${config_path}.inkpi.bak.$(date +%Y%m%d%H%M%S)"

managed_begin="# >>> InkPi Waveshare 4inch LCD(A) >>>"
managed_end="# <<< InkPi Waveshare 4inch LCD(A) <<<"
tmp_config="$(mktemp)"

sudo awk -v begin="${managed_begin}" -v end="${managed_end}" '
    $0 == begin { skip = 1; next }
    $0 == end { skip = 0; next }
    !skip { print }
' "${config_path}" > "${tmp_config}"

{
    echo "${managed_begin}"
    echo "dtparam=spi=on"
    echo "hdmi_force_hotplug=1"
    echo "hdmi_group=2"
    echo "hdmi_mode=87"
    echo "hdmi_cvt 480 320 60 6 0 0 0"
    echo "hdmi_drive=2"
    if [ -n "${overlay_rotate}" ]; then
        echo "dtoverlay=waveshare35a:rotate=${overlay_rotate}"
    else
        echo "dtoverlay=waveshare35a"
    fi
    echo "display_rotate=${display_rotate}"
    echo "${managed_end}"
} >> "${tmp_config}"

sudo cp "${tmp_config}" "${config_path}"
rm -f "${tmp_config}"

calibration_source="${driver_dir}/etc/X11/xorg.conf.d/99-calibration.conf-4${calibration_suffix}"
if [ -f "${calibration_source}" ]; then
    sudo mkdir -p /usr/share/X11/xorg.conf.d
    sudo cp "${calibration_source}" /usr/share/X11/xorg.conf.d/99-calibration.conf
fi

if [ -f "${cmdline_path}" ]; then
    sudo cp "${cmdline_path}" "${cmdline_path}.inkpi.bak.$(date +%Y%m%d%H%M%S)"
    sudo python3 - "${cmdline_path}" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
tokens = path.read_text(encoding="utf-8").strip().split()
tokens = [token for token in tokens if not token.startswith("video=")]
for wanted in ("fbcon=map:10", "fbcon=font:ProFont6x11"):
    if wanted not in tokens:
        tokens.append(wanted)
path.write_text(" ".join(tokens) + "\n", encoding="utf-8")
PY
fi

echo "Configured Waveshare 4inch RPi LCD (A): rotation=${rotation}, config=${config_path}"
