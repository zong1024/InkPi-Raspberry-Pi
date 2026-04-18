#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/_server_runtime.sh"

DEPLOY_MODE="${1:-${INKPI_DEPLOY_MODE:-backend}}"
HEALTH_HOST="${INKPI_HEALTH_HOST:-127.0.0.1}"
HEALTH_ATTEMPTS="${INKPI_HEALTH_ATTEMPTS:-45}"
HEALTH_SLEEP_SECONDS="${INKPI_HEALTH_SLEEP_SECONDS:-1}"

case "${DEPLOY_MODE}" in
    backend|server) ;;
    *)
        echo "Unsupported deploy mode: ${DEPLOY_MODE}" >&2
        exit 1
        ;;
esac

python3 - \
    "${HEALTH_HOST}" \
    "${INKPI_WEB_PORT}" \
    "${INKPI_CLOUD_PORT}" \
    "${HEALTH_ATTEMPTS}" \
    "${HEALTH_SLEEP_SECONDS}" \
    "${DEPLOY_MODE}" \
    "${PID_DIR}" <<'PY'
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request


host = sys.argv[1]
web_port = int(sys.argv[2])
cloud_port = int(sys.argv[3])
attempts = int(sys.argv[4])
sleep_seconds = float(sys.argv[5])
deploy_mode = sys.argv[6]
pid_dir = sys.argv[7]


def fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=2.0) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload or "{}")


def qt_process_running() -> bool:
    pid_file = os.path.join(pid_dir, "qt_ui.pid")
    if not os.path.exists(pid_file):
        return False
    try:
        pid = int(open(pid_file, encoding="utf-8").read().strip())
        os.kill(pid, 0)
        return True
    except Exception:
        return False


last_error = "health check not started"
last_snapshot: dict | None = None

for attempt in range(1, attempts + 1):
    try:
        cloud_health = fetch_json(f"http://{host}:{cloud_port}/api/health")
        web_health = fetch_json(f"http://{host}:{web_port}/api/health")
        ops_status = fetch_json(f"http://{host}:{web_port}/api/ops/status")

        snapshot = ops_status.get("snapshot") or {}
        last_snapshot = snapshot
        stack = snapshot.get("stack") or {}
        models = snapshot.get("models") or {}
        cloud_stack = stack.get("cloud_api") or {}
        ocr_status = models.get("ocr") or {}
        scorer_status = models.get("quality_scorer") or {}

        errors = []
        if str(cloud_health.get("status")) != "ok" and not bool(cloud_health.get("ok")):
            errors.append(f"cloud_api /api/health returned {cloud_health}")
        if str(web_health.get("status")) != "ok":
            errors.append(f"web_ui /api/health returned {web_health}")
        if not bool(cloud_stack.get("healthy")):
            errors.append(f"ops snapshot reports cloud_api unhealthy: {cloud_stack}")
        if not bool(scorer_status.get("ready")):
            errors.append(f"quality scorer is not ready: {scorer_status}")
        if not bool(ocr_status.get("overall_ready")):
            errors.append(f"OCR is not ready: {ocr_status}")
        if deploy_mode == "server" and not qt_process_running():
            errors.append("qt_ui is not running")

        if not errors:
            summary = {
                "deploy_mode": deploy_mode,
                "cloud_api": cloud_stack,
                "web_ui": stack.get("web_ui") or {},
                "ocr": ocr_status,
                "quality_scorer": scorer_status,
            }
            if deploy_mode == "server":
                summary["qt_ui"] = stack.get("qt_ui") or {"running": True}
            print("Stack health check passed.")
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            sys.exit(0)

        last_error = "; ".join(errors)
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        last_error = str(exc)

    time.sleep(sleep_seconds)

print("Stack health check failed.", file=sys.stderr)
print(last_error, file=sys.stderr)
if last_snapshot is not None:
    print(json.dumps(last_snapshot, ensure_ascii=False, indent=2), file=sys.stderr)
sys.exit(1)
PY
