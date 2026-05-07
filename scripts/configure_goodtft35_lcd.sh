#!/bin/bash
set -euo pipefail

profile="${INKPI_LCD_PROFILE:-}"
rotation="${INKPI_DISPLAY_ROTATION:-inverted}"
touch_calibration="${INKPI_TOUCH_CALIBRATION:-auto}"
driver_dir="${INKPI_LCD_SHOW_DIR:-/opt/inkpi/goodtft-LCD-show}"
boot_dir="${INKPI_BOOT_DIR:-}"
config_path="${INKPI_BOOT_CONFIG:-}"
cmdline_path="${INKPI_BOOT_CMDLINE:-}"
overlay_rotate="270"
touch_rotate=""

case "${profile}" in
    goodtft35a|lcd35|lcd35-show|tft35a)
        ;;
    "")
        exit 0
        ;;
    *)
        echo "Warning: unsupported GoodTFT profile ${profile}; skipping GoodTFT LCD configuration."
        exit 0
        ;;
esac

# goodtft LCD35-show uses 90 as the factory baseline:
# .have_installed = gpio:resistance:35:90:480:320
# rotate.sh then applies (90 + requested_degrees) % 360.
case "${rotation}" in
    normal|0|"")
        overlay_rotate="90"
        ;;
    left|90)
        overlay_rotate="180"
        ;;
    inverted|180)
        overlay_rotate="270"
        ;;
    right|270)
        overlay_rotate="0"
        ;;
    *)
        echo "Unsupported INKPI_DISPLAY_ROTATION=${rotation}; using inverted."
        overlay_rotate="270"
        ;;
esac

case "${touch_calibration}" in
    auto|"")
        touch_rotate="${overlay_rotate}"
        ;;
    normal|0)
        touch_rotate="0"
        ;;
    left|90)
        touch_rotate="90"
        ;;
    inverted|180)
        touch_rotate="180"
        ;;
    right|270)
        touch_rotate="270"
        ;;
    *)
        if printf '%s' "${touch_calibration}" | grep -Eq '^(0|90|180|270)$'; then
            touch_rotate="${touch_calibration}"
        else
            echo "Unsupported INKPI_TOUCH_CALIBRATION=${touch_calibration}; using auto."
            touch_rotate="${overlay_rotate}"
        fi
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
    sudo git clone --depth 1 https://github.com/goodtft/LCD-show.git "${driver_dir}"
fi

overlay_source="${driver_dir}/usr/tft35a-overlay.dtb"
calibration_source="${driver_dir}/usr/99-calibration.conf-35-${touch_rotate}"
if [ ! -f "${overlay_source}" ]; then
    echo "Error: GoodTFT tft35a overlay not found at ${overlay_source}."
    exit 1
fi
if [ ! -f "${calibration_source}" ]; then
    echo "Error: GoodTFT touch calibration not found at ${calibration_source}."
    exit 1
fi

overlay_dir="${boot_dir}/overlays"
if [ ! -d "${overlay_dir}" ] && [ -d /boot/overlays ]; then
    overlay_dir="/boot/overlays"
fi
sudo mkdir -p "${overlay_dir}"
sudo cp "${overlay_source}" "${overlay_dir}/tft35a.dtbo"

sudo touch "${config_path}"
sudo cp "${config_path}" "${config_path}.inkpi.bak.$(date +%Y%m%d%H%M%S)"

managed_begin="# >>> InkPi GoodTFT LCD35 >>>"
managed_end="# <<< InkPi GoodTFT LCD35 <<<"
old_waveshare_begin="# >>> InkPi Waveshare 4inch LCD(A) >>>"
old_waveshare_end="# <<< InkPi Waveshare 4inch LCD(A) <<<"
tmp_config="$(mktemp)"

sudo awk \
    -v begin="${managed_begin}" \
    -v end="${managed_end}" \
    -v old_begin="${old_waveshare_begin}" \
    -v old_end="${old_waveshare_end}" '
    $0 == begin || $0 == old_begin { skip = 1; next }
    $0 == end || $0 == old_end { skip = 0; next }
    $0 ~ /^dtoverlay=(waveshare35a|tft35a)(:.*)?$/ { next }
    !skip { print }
' "${config_path}" > "${tmp_config}"

{
    echo "${managed_begin}"
    echo "hdmi_force_hotplug=1"
    echo "dtparam=i2c_arm=on"
    echo "dtparam=spi=on"
    echo "enable_uart=1"
    echo "dtoverlay=tft35a:rotate=${overlay_rotate}"
    echo "hdmi_group=2"
    echo "hdmi_mode=87"
    echo "hdmi_cvt 480 320 60 6 0 0 0"
    echo "hdmi_drive=2"
    echo "${managed_end}"
} >> "${tmp_config}"

sudo cp "${tmp_config}" "${config_path}"
rm -f "${tmp_config}"

sudo mkdir -p /etc/X11/xorg.conf.d
sudo rm -f /etc/X11/xorg.conf.d/40-libinput.conf
sudo cp "${calibration_source}" /etc/X11/xorg.conf.d/99-calibration.conf
if [ -f /usr/share/X11/xorg.conf.d/10-evdev.conf ]; then
    sudo cp /usr/share/X11/xorg.conf.d/10-evdev.conf /usr/share/X11/xorg.conf.d/45-evdev.conf
fi

if [ -f "${cmdline_path}" ]; then
    sudo cp "${cmdline_path}" "${cmdline_path}.inkpi.bak.$(date +%Y%m%d%H%M%S)"
    sudo python3 - "${cmdline_path}" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
tokens = path.read_text(encoding="utf-8").strip().split()
tokens = [token for token in tokens if not token.startswith("video=")]
path.write_text(" ".join(tokens) + "\n", encoding="utf-8")
PY
fi

echo "Configured GoodTFT LCD35: display_rotate=${overlay_rotate}, touch_calibration=${touch_rotate}, config=${config_path}"
