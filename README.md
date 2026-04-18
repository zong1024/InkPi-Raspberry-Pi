# InkPi

InkPi is a single-character calligraphy evaluation project that combines:

- `PyQt6` desktop UI
- local `WebUI` for debugging and result inspection
- `Cloud API` for shared history and remote OCR fallback
- `MiniApp` result browsing, statistics, and cloud record management
- ONNX-based scoring and four-dimension explanation scores

Current main pipeline:

`capture/upload -> preprocessing -> OCR -> ONNX quality scoring -> four-dimension explanation -> local SQLite -> cloud sync`

## Main Entry Points

- Qt desktop UI: `python main.py`
- Local WebUI: `python -m web_ui.app`
- Cloud API: `python cloud_api/app.py`

Default ports:

- WebUI: `http://127.0.0.1:5000`
- Cloud API: `http://127.0.0.1:5001`

## Four-Dimension Scoring

The primary score remains `total_score`.  
The explanation layer adds four dimension scores:

- `structure` / 结构
- `stroke` / 笔画
- `integrity` / 完整
- `stability` / 稳定

Implementation notes:

- `services/quality_scorer_service.py` keeps the main ONNX scoring pipeline
- `services/dimension_scorer_service.py` builds four explanation scores
- `models/evaluation_result.py` stores `dimension_scores` and `score_debug`
- `models/evaluation_framework.py` defines basis cards, practice guidance, and validation targets
- Qt shows user-facing scores only
- WebUI shows debug data for evaluation inspection
- Cloud API returns `dimension_scores` in list/detail payloads
- Cloud API now also exposes reviewer-facing methodology data at `/api/system/methodology`

## Reviewer-Oriented Positioning

To avoid overstating the system, the current project should be presented as:

- a `single-character`, `regular-script`, `beginner-friendly` assistant
- a system that keeps `total_score` as the primary score and uses four dimensions for explanation
- a product that supports `teacher-assisted review`, not an automated replacement for expert grading

The mobile miniapp now exposes:

- quantitative statistics and progress trends
- record deletion and batch management
- explanation-basis cards for each dimension
- practice guidance derived from the weakest dimension
- validation snapshot fields such as sample count, character coverage, device count, and target progress

For a detailed reviewer-facing write-up, see:

- `docs/evaluation-basis-and-validation.md`

## Runtime Layout

- `views/`: PyQt6 UI pages
- `services/`: camera, preprocessing, OCR, scoring, database, cloud sync
- `models/`: runtime models and ONNX assets
- `web_ui/`: local browser UI and Flask routes
- `cloud_api/`: shared cloud-facing Flask API
- `miniapp/`: mobile viewer with history, quantitative statistics, and delete management
- `training/`: scoring model training pipeline
- `docs/`: flow chart, project documentation, PPT assets

## Linux / XFCE Deployment

The project now targets Linux/XFCE for graphical Qt deployment.  
The old Windows desktop simulator scripts have been removed.

Server setup:

```bash
bash scripts/setup_server_runtime.sh
```

Public backend only:

```bash
bash scripts/setup_backend_runtime.sh
INKPI_WEB_PORT=5000 INKPI_CLOUD_PORT=23333 bash scripts/start_backend_stack.sh
```

Start the full stack:

```bash
bash scripts/start_server_stack.sh
```

Install tty1 kiosk autostart for the full stack:

```bash
INKPI_KIOSK_MODE=stack bash scripts/install_kiosk.sh
```

Stop the full stack:

```bash
bash scripts/stop_server_stack.sh
```

Stop the public backend only:

```bash
bash scripts/stop_backend_stack.sh
```

Restart the public backend only:

```bash
bash scripts/restart_backend_stack.sh
```

Run backend health checks:

```bash
bash scripts/health_check_stack.sh backend
```

What the stack script starts:

- `Cloud API` on `INKPI_CLOUD_PORT` (default `5001`)
- `WebUI` on `INKPI_WEB_PORT` (default `5000`)
- `Qt UI` inside the current XFCE session

What the backend-only script starts:

- `Cloud API` on `INKPI_CLOUD_PORT` (recommended public port `23333`)
- `WebUI` on `INKPI_WEB_PORT` (default `5000`)

Useful environment overrides:

```bash
export INKPI_WEB_HOST=0.0.0.0
export INKPI_WEB_PORT=5000
export INKPI_CLOUD_PORT=5001
export INKPI_WINDOW_WIDTH=480
export INKPI_WINDOW_HEIGHT=320
export INKPI_FULLSCREEN=0
```

Optional runtime env files:

- `.inkpi/cloud.env`
- `.inkpi/server.env`

Example cloud sync configuration:

```env
INKPI_CLOUD_BACKEND_URL=http://202.60.232.93:23333
INKPI_CLOUD_DEVICE_KEY=your-device-key
INKPI_CLOUD_DEVICE_NAME=InkPi-XFCE
```

Raspberry Pi note:

- `paddlepaddle` / `paddleocr` are installed only on supported `x86_64` / `AMD64` environments
- ARM devices can still evaluate through the built-in remote OCR fallback when `INKPI_CLOUD_BACKEND_URL` and `INKPI_CLOUD_DEVICE_KEY` are configured

## Local Development

Install dependencies:

```bash
pip install -r requirements.txt
```

Run Qt:

```bash
python main.py
```

Run WebUI:

```bash
python -m web_ui.app
```

Run Cloud API:

```bash
python cloud_api/app.py
```

## Tests

Common regression checks:

```bash
python -m unittest test_web_ui.py
python -m unittest test_all.py
python -m unittest test_cloud_api.py
python -m unittest test_cloud_ocr_api.py
python -m unittest test_cloud_sync_integration.py
```

## CI Notes

GitHub Actions should focus on cross-platform Python logic.  
Raspberry Pi specific hardware paths such as `GPIO`, camera hardware, `SPI`, and `libcamera` are better covered on the real device or a self-hosted runner.

## CI/CD

The repository now defines a complete CI/CD chain for the three main delivery targets:

- `PR / Push CI`: Python checks, ops console build, miniapp validation, and release artifact packaging
- `Deploy Public Backend`: remote deployment for `Cloud API + WebUI`
- `Deploy Raspberry Pi Stack`: remote deployment for `Qt + WebUI + Cloud API`
- `Miniapp Release Candidate`: miniapp validation plus zip packaging for release handoff

Main repo entrypoints:

- `scripts/rpi_lint_test.sh`
- `scripts/ci_python_checks.sh`
- `scripts/ci_ops_console.sh`
- `scripts/ci_miniapp_checks.sh`
- `scripts/package_backend_release.sh`
- `scripts/package_rpi_release.sh`
- `scripts/package_miniapp_release.sh`
- `scripts/install_rpi_release.sh`
- `scripts/deploy_backend_release.sh`
- `scripts/deploy_rpi_release.sh`
- `scripts/restart_backend_stack.sh`
- `scripts/health_check_stack.sh`

GitHub workflow files:

- `.github/workflows/python-app.yml`
- `.github/workflows/deploy-backend.yml`
- `.github/workflows/deploy-rpi.yml`
- `.github/workflows/miniapp-ci.yml`
- `.github/workflows/miniapp-release.yml`
- `.github/workflow-snippets/rpi-device-cd.yml`

Raspberry Pi device-side release path:

1. Run `bash scripts/rpi_lint_test.sh`
2. Build the device artifact with `bash scripts/package_rpi_release.sh`
3. Copy `dist/releases/inkpi-rpi-release-*.tar.gz` to the Raspberry Pi
4. Run `INKPI_DEPLOY_MODE=server bash scripts/install_rpi_release.sh /path/to/inkpi-rpi-release-*.tar.gz`
5. Let `scripts/health_check_stack.sh` confirm `cloud_api`, `web_ui`, OCR readiness, the ONNX scorer state, and the Qt process

The device installer reuses the current `setup_*`, `start_*`, and `stop_*` scripts, keeps mutable state under `INKPI_DEPLOY_ROOT/shared`, switches `current` to a freshly unpacked release, and rolls back automatically if the post-start health check fails.

The public backend deploy script now follows the same pattern: it stops the previous stack, keeps runtime state under `INKPI_DEPLOY_TARGET_DIR/shared`, switches `current` to the new release, and finishes with `scripts/health_check_stack.sh backend`.

Default Raspberry Pi release layout:

- `${HOME}/inkpi-device/releases/<release-id>`
- `${HOME}/inkpi-device/current`
- `${HOME}/inkpi-device/shared/data`
- `${HOME}/inkpi-device/shared/.inkpi`
- `${HOME}/inkpi-device/shared/logs`
- `${HOME}/inkpi-device/shared/runtime_logs`
- `${HOME}/inkpi-device/shared/runtime_pids`

Default public backend release layout:

- `/opt/inkpi/releases/<release-id>`
- `/opt/inkpi/current`
- `/opt/inkpi/shared/data`
- `/opt/inkpi/shared/.inkpi`
- `/opt/inkpi/shared/venv`
- `/opt/inkpi/shared/runtime_logs`
- `/opt/inkpi/shared/runtime_pids`

Miniapp CI/CD entrypoints:

- `npm --prefix miniapp run ci`
- `npm --prefix miniapp run ci:release`
- `.github/workflows/miniapp-ci.yml`

The miniapp branch pipeline prepares `miniapp/dist/ci-package` on every relevant PR or push. The dedicated release workflow re-runs the pipeline in strict mode, optionally rewrites `config.js` with `MINIAPP_API_BASE_URL`, and uploads both the importable package directory and the release zip.

Recommended deployment order:

1. Open a PR and wait for `InkPi CI`
2. Review the generated artifacts in `dist/releases`
3. Trigger `Deploy Public Backend` for the cloud host
4. Trigger `Deploy Raspberry Pi Stack` for the device
5. Trigger `Miniapp Release Candidate` to get the WeChat import package

Required GitHub secrets:

- Backend: `INKPI_BACKEND_HOST`, `INKPI_BACKEND_USER`, `INKPI_BACKEND_PORT`, `INKPI_BACKEND_TARGET_DIR`, `INKPI_BACKEND_SSH_KEY`
- Raspberry Pi: `INKPI_RPI_HOST`, `INKPI_RPI_USER`, `INKPI_RPI_PORT`, `INKPI_RPI_TARGET_DIR`, `INKPI_RPI_SSH_KEY`

`Deploy Public Backend` now reruns `scripts/ci_python_checks.sh` before packaging, rebuilds `web_console` through `scripts/package_backend_release.sh`, and lets the remote deploy step execute `setup_backend_runtime.sh -> start_backend_stack.sh -> health_check_stack.sh backend`.

For the full CI/CD process, artifact strategy, and workflow responsibilities, see:

- `docs/ci-cd.md`

## Docs

- Flow chart source: `docs/inkpi-project-flow.drawio`
- Flow chart preview: `docs/inkpi-project-flow.png`
- CI/CD notes: `docs/ci-cd.md`
- Reviewer notes: `docs/evaluation-basis-and-validation.md`
- Training notes: `training/README.md`
