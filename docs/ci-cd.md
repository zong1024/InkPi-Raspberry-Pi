# InkPi CI/CD

## Overview

InkPi now uses one shared CI workflow and three target-specific delivery tracks:

- `PR / Push CI`
  Validates Python regressions, builds the operations console, validates the miniapp source, and uploads release-ready artifacts.
- `Deploy Public Backend`
  Builds and deploys `Cloud API + WebUI` to the public host.
- `Deploy Raspberry Pi Stack`
  Builds and deploys the full device stack: `Qt + WebUI + Cloud API`.
- `Miniapp Release Candidate`
  Runs strict miniapp preflight checks and produces an importable release package.

## Repository Entrypoints

### Shared CI

- `scripts/ci_python_checks.sh`
- `scripts/ci_ops_console.sh`
- `scripts/ci_miniapp_checks.sh`

### Packaging

- `scripts/package_backend_release.sh`
- `scripts/package_rpi_release.sh`
- `scripts/package_miniapp_release.sh`

### Remote Deployment

- `scripts/deploy_backend_release.sh`
- `scripts/deploy_rpi_release.sh`
- `scripts/install_rpi_release.sh`
- `scripts/health_check_stack.sh`
- `scripts/restart_backend_stack.sh`

## GitHub Actions

### 1. Repository CI

Workflow: `.github/workflows/python-app.yml`

Responsibilities:

- run Python compile, flake8, unittest, and cloud-sync regression checks
- build the React operations console and verify the generated `web_ui/static` bundle
- run the miniapp CI pipeline
- upload backend, Raspberry Pi, and miniapp release artifacts to Actions

### 2. Public Backend Deployment

Workflow: `.github/workflows/deploy-backend.yml`

Responsibilities:

- checkout the requested ref
- rerun Python regression checks before deployment
- build the operations console and backend release bundle
- upload the bundle to the remote host through SSH
- switch the `current` symlink to the new release
- reuse shared runtime state under `/opt/inkpi/shared`
- run `setup_backend_runtime.sh -> start_backend_stack.sh -> health_check_stack.sh backend`

Required secrets:

- `INKPI_BACKEND_HOST`
- `INKPI_BACKEND_USER`
- `INKPI_BACKEND_PORT`
- `INKPI_BACKEND_TARGET_DIR`
- `INKPI_BACKEND_SSH_KEY`

### 3. Raspberry Pi Full-Stack Deployment

Workflow: `.github/workflows/deploy-rpi.yml`

Responsibilities:

- rerun Raspberry Pi regression checks with `scripts/rpi_lint_test.sh`
- package the full device release bundle
- upload the bundle and bootstrap installer to the Raspberry Pi
- call `scripts/install_rpi_release.sh` on the device
- rotate the `current` symlink under the deploy root
- preserve device data, runtime logs, and cached config under `shared/`
- run post-start health checks for `Cloud API`, `WebUI`, OCR readiness, scorer readiness, and `qt_ui`

Required secrets:

- `INKPI_RPI_HOST`
- `INKPI_RPI_USER`
- `INKPI_RPI_PORT`
- `INKPI_RPI_TARGET_DIR`
- `INKPI_RPI_SSH_KEY`

### 4. Miniapp Release Candidate

Workflow: `.github/workflows/miniapp-release.yml`

Responsibilities:

- rerun the miniapp pipeline in strict release mode
- optionally rewrite `miniapp/dist/ci-package/config.js` with `MINIAPP_API_BASE_URL`
- ensure the release package uses HTTPS and a public domain when an override is provided
- upload both `miniapp/dist/ci-package` and `dist/releases/inkpi-miniapp-*.zip`

Supporting workflow:

- `.github/workflows/miniapp-ci.yml`

This dedicated miniapp workflow runs on miniapp-related changes and keeps the branch-level miniapp checks fast and focused.

## Release Layout

### Public Backend

- `/opt/inkpi/releases/<release-id>`
- `/opt/inkpi/current`
- `/opt/inkpi/shared/data`
- `/opt/inkpi/shared/.inkpi`
- `/opt/inkpi/shared/venv`
- `/opt/inkpi/shared/runtime_logs`
- `/opt/inkpi/shared/runtime_pids`

### Raspberry Pi

- `${HOME}/inkpi-device/releases/<release-id>`
- `${HOME}/inkpi-device/current`
- `${HOME}/inkpi-device/shared/data`
- `${HOME}/inkpi-device/shared/.inkpi`
- `${HOME}/inkpi-device/shared/logs`
- `${HOME}/inkpi-device/shared/runtime_logs`
- `${HOME}/inkpi-device/shared/runtime_pids`

## Recommended Flow

1. Open a feature branch and submit a PR.
2. Wait for `InkPi CI` to pass.
3. Review the generated artifacts in GitHub Actions.
4. Trigger `Deploy Public Backend` for the cloud host.
5. Trigger `Deploy Raspberry Pi Stack` for the device.
6. Trigger `Miniapp Release Candidate` when you need an importable WeChat package.

## Validation Notes

- The public backend server does not provide camera, GPIO, LED, or I2C hardware, so the operations console will correctly report those items as unavailable there.
- Raspberry Pi hardware status still needs real-device verification even after CI passes.
- Miniapp release packaging is automated up to the importable artifact stage; the final WeChat developer-tool submission remains a manual handoff step.
