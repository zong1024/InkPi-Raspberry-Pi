"""Background sync from the Raspberry Pi app to the cloud API."""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Any

import requests

from config import CLOUD_CONFIG
from models.evaluation_result import EvaluationResult


class CloudSyncService:
    """Upload finished evaluations to the cloud API without blocking the UI."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._bootstrap_env_from_file()
        self.enabled = bool(CLOUD_CONFIG.get("enabled", False))
        self.backend_url = str(
            CLOUD_CONFIG.get("backend_url") or os.environ.get("INKPI_CLOUD_BACKEND_URL", "")
        ).rstrip("/")
        self.device_name = str(
            CLOUD_CONFIG.get("device_name") or os.environ.get("INKPI_CLOUD_DEVICE_NAME", "InkPi-Raspberry-Pi")
        )
        self.device_key = str(
            CLOUD_CONFIG.get("device_key") or os.environ.get("INKPI_CLOUD_DEVICE_KEY", "")
        )
        self.timeout = float(
            CLOUD_CONFIG.get("sync_timeout") or os.environ.get("INKPI_CLOUD_SYNC_TIMEOUT", 2.5)
        )

    def _bootstrap_env_from_file(self) -> None:
        """Load `.inkpi/cloud.env` so manual `python main.py` launches still sync to cloud."""

        env_path = Path(__file__).resolve().parent.parent / ".inkpi" / "cloud.env"
        if not env_path.exists():
            return

        try:
            for raw_line in env_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    os.environ.setdefault(key, value)
        except Exception as exc:  # noqa: BLE001
            self.logger.debug("Skip loading cloud env file %s: %s", env_path, exc)

    @property
    def is_ready(self) -> bool:
        return self.enabled and bool(self.backend_url) and bool(self.device_key)

    def upload_result_async(self, result: EvaluationResult, local_record_id: int) -> bool:
        """Schedule a background upload. Returns False when sync is not configured."""

        if not self.is_ready:
            return False

        worker = threading.Thread(
            target=self._safe_upload,
            args=(result, local_record_id),
            name=f"inkpi-cloud-sync-{local_record_id}",
            daemon=True,
        )
        worker.start()
        return True

    def upload_result(self, result: EvaluationResult, local_record_id: int) -> dict[str, Any]:
        """Upload one evaluation synchronously."""

        if not self.is_ready:
            raise RuntimeError("Cloud sync is not configured")

        response = requests.post(
            f"{self.backend_url}/api/device/results",
            json=self._build_payload(result, local_record_id),
            headers={
                "Content-Type": "application/json",
                "X-Device-Key": self.device_key,
                "X-Device-Name": self.device_name,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("ok", False):
            raise RuntimeError(data.get("error", "Cloud API rejected the upload"))
        return data

    def _build_payload(self, result: EvaluationResult, local_record_id: int) -> dict[str, Any]:
        return {
            "local_record_id": local_record_id,
            "device_name": self.device_name,
            "total_score": result.total_score,
            "detail_scores": result.detail_scores,
            "feedback": result.feedback,
            "timestamp": result.timestamp.isoformat(),
            "character_name": result.character_name,
            "style": result.style,
            "style_confidence": result.style_confidence,
            "image_path": result.image_path,
            "processed_image_path": result.processed_image_path,
        }

    def _safe_upload(self, result: EvaluationResult, local_record_id: int) -> None:
        try:
            self.upload_result(result, local_record_id)
            self.logger.info("Cloud sync succeeded: local_record_id=%s", local_record_id)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Cloud sync skipped for record %s: %s", local_record_id, exc)


cloud_sync_service = CloudSyncService()
