"""End-to-end check for local save -> async cloud upload."""

from __future__ import annotations

import importlib
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path

import requests
from werkzeug.serving import make_server

from cloud_api.app import create_app
from models.evaluation_result import EvaluationResult
from services.database_service import DatabaseService


def main() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        cloud_db = temp_root / "cloud.db"
        local_db = temp_root / "local.db"

        app = create_app(
            {
                "TESTING": True,
                "DATABASE": str(cloud_db),
                "DEVICE_KEY": "device-key",
                "DEFAULT_USERNAME": "demo",
                "DEFAULT_PASSWORD": "demo123456",
                "DEFAULT_DISPLAY_NAME": "InkPi Demo",
            }
        )
        server = make_server("127.0.0.1", 0, app)
        port = server.server_port

        try:
            import threading

            server_thread = threading.Thread(target=server.serve_forever, daemon=True)
            server_thread.start()

            os.environ["INKPI_CLOUD_BACKEND_URL"] = f"http://127.0.0.1:{port}"
            os.environ["INKPI_CLOUD_DEVICE_KEY"] = "device-key"
            os.environ["INKPI_CLOUD_DEVICE_NAME"] = "InkPi-Test-RPi"

            import services.cloud_sync_service as cloud_sync_module

            importlib.reload(cloud_sync_module)

            local_db_service = DatabaseService(local_db)
            result = EvaluationResult.from_rubric_scores(
                total_score=91,
                feedback="结构稳定，笔画干净。",
                timestamp=datetime.now(),
                script="regular",
                character_name="永",
                ocr_confidence=0.97,
                quality_level="good",
                quality_confidence=0.94,
                image_path=None,
                processed_image_path=None,
                rubric_family="regular_rubric_v1",
                rubric_scores={
                    "bifa_dianhua": 100,
                    "jieti_zifa": 80,
                    "bubai_zhangfa": 60,
                    "mofa_bili": 80,
                    "guifan_wanzheng": 100,
                },
                score_debug={
                    "probabilities": {"good": 0.94},
                    "quality_features": {"center_quality": 0.93},
                    "geometry_features": {"projection_balance": 0.87},
                    "calibration": {"feature_quality": 0.86},
                },
            )
            local_id = local_db_service.save(result)

            deadline = time.time() + 5
            while time.time() < deadline:
                response = requests.post(
                    f"http://127.0.0.1:{port}/api/auth/login",
                    json={"username": "demo", "password": "demo123456"},
                    timeout=2,
                )
                token = response.json()["token"]
                history = requests.get(
                    f"http://127.0.0.1:{port}/api/results?limit=10",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=2,
                ).json()
                items = history.get("items", [])
                matched = next((item for item in items if item["local_record_id"] == local_id), None)
                if matched:
                    assert matched["rubric_family"] == "regular_rubric_v1"
                    assert matched["rubric_items"][0]["label"] == "笔法点画"
                    print(f"PASS cloud sync propagated local record {local_id}")
                    return 0
                time.sleep(0.2)

            print("FAIL cloud sync timeout")
            return 1
        finally:
            server.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
