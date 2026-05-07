# Codex Handoff

This file is the current working handoff for continuing InkPi work from another
Codex session. Read this before changing deployment, OCR, LCD, or sync logic.

## Current Branch

- Repository: `https://github.com/zong1024/InkPi-Raspberry-Pi.git`
- Branch: `master`
- Latest important commit: `c845a87 Install joblib for PaddleOCR runtime`
- Local workspace used by the current Codex: `C:\Users\zongrui\Documents\InkPi-Raspberry-Pi`
- Raspberry Pi intended install directory: `/home/zongrui/InkPi-Raspberry-Pi-active`

## Current Raspberry Pi Command

Use this for a clean Pi redeploy:

```bash
cd ~

curl -fsSL https://raw.githubusercontent.com/zong1024/InkPi-Raspberry-Pi/master/scripts/install_rpi_oneclick.sh | env \
  INKPI_DIR="$HOME/InkPi-Raspberry-Pi-active" \
  INKPI_FORCE_REFRESH=1 \
  INSTALL_KIOSK=1 \
  INKPI_LCD_PROFILE=goodtft35a \
  INKPI_DISPLAY_ROTATION=inverted \
  INKPI_TOUCH_CALIBRATION=auto \
  INKPI_ENABLE_TESSERACT_FALLBACK=0 \
  INKPI_CLOUD_BACKEND_URL="http://202.60.232.93:23334" \
  bash
```

Do not add `INKPI_SKIP_HEALTHCHECK=1` while debugging OCR. The health check must
fail loudly if PaddleOCR is not really online.

## Hardware State

- The actual screen driver given by the user is:

```bash
sudo rm -rf LCD-show
git clone https://github.com/goodtft/LCD-show.git
chmod -R 755 LCD-show
cd LCD-show/
sudo ./LCD35-show
```

- Therefore the project now uses `INKPI_LCD_PROFILE=goodtft35a`, not
  `waveshare4a`.
- The GoodTFT profile configures `tft35a.dtbo`, `dtoverlay=tft35a:rotate=270`
  for 180-degree user rotation, and the matching
  `99-calibration.conf-35-*` touch files.
- If the screen is correct but touch is wrong, adjust only:

```bash
INKPI_TOUCH_CALIBRATION=auto
# or one of: 0, 90, 180, 270
```

Do not go back to the old Waveshare `waveshare35a` profile unless the hardware
changes.

## OCR State

The user confirmed previous versions ran OCR locally on the Raspberry Pi. Do not
route OCR to Tesseract or remote server as the primary fix.

Current intended state:

- PaddleOCR must initialize locally on the Pi.
- Tesseract fallback is disabled by default with
  `INKPI_ENABLE_TESSERACT_FALLBACK=0`.
- `deploy_rpi.sh` now treats PaddleOCR installation failure as fatal.
- `joblib` was added explicitly because PaddleOCR initialized with:
  `ModuleNotFoundError: No module named 'joblib'`.
- `LocalOcrService` now exposes `init_error` and health check prints it.
- `PADDLE_PDX_MODEL_SOURCE` defaults to `BOS` in OCR initialization.

Expected healthy check output:

```text
Local OCR available: True
PaddleOCR initialized: True
PaddleOCR init error:
Tesseract fallback enabled: False
```

If it still fails, ask for the exact health check lines:

```text
Local OCR available:
PaddleOCR initialized:
PaddleOCR init error:
Tesseract fallback enabled:
```

Then add the missing runtime dependency or fix the init API. Do not silently
fall back to Tesseract.

## Cloud Sync State

- Cloud API server is deployed at `http://202.60.232.93:23334`.
- It must not disturb the user's existing blog service on the same server.
- Do not write secrets into docs or commits.
- Pi history sync should use the configured cloud backend URL and device key
  from `.inkpi/cloud.env`.

## Recent Fixes

- `f5328e8`: added GoodTFT LCD35 driver support.
- `4b06a45`: made PaddleOCR required again and disabled silent Tesseract takeover.
- `cb0c29d`: exposed PaddleOCR init errors in health check.
- `c845a87`: installed `joblib` explicitly for PaddleOCR runtime.

## Workspace Notes

There are unrelated untracked files in the Windows workspace, including
presentation/audit artifacts and `.claude/`. Do not stage them unless the user
explicitly asks.
