#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_DIR}"

export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}"
export INKPI_TEST_MODE="${INKPI_TEST_MODE:-true}"
export PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK="${PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK:-True}"

python -m py_compile \
    main.py \
    cloud_api/app.py \
    cloud_api/storage.py \
    models/evaluation_framework.py \
    models/evaluation_result.py \
    test_all.py \
    test_web_ui.py \
    test_cloud_api.py \
    test_cloud_ocr_api.py \
    test_cloud_sync_integration.py

flake8 main.py cloud_api config services views web_ui test_*.py \
    --count --select=E9,F63,F7,F82 --show-source --statistics

flake8 main.py cloud_api config services views web_ui test_*.py \
    --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

python -m unittest test_web_ui.py test_all.py test_cloud_api.py test_cloud_ocr_api.py
python test_cloud_sync_integration.py
