"""HTTP-backed OCR candidate provider for the full-recognition pipeline."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List

import cv2
import requests

from full_recognition_v2.providers import CandidateProvider
from full_recognition_v2.types import RecognitionCandidate
from services.template_manager import template_manager


class HttpOcrCandidateProvider(CandidateProvider):
    """Fetch OCR top-k candidates from a remote service."""

    name = "remote_ocr"

    def __init__(
        self,
        endpoint: str | None = None,
        device_key: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.logger = logging.getLogger(__name__)
        self._bootstrap_env_from_file()
        backend_url = os.getenv("INKPI_CLOUD_BACKEND_URL", "").rstrip("/")
        derived_endpoint = f"{backend_url}/api/device/full-recognition/candidates" if backend_url else ""
        self.endpoint = (
            str(endpoint or os.getenv("INKPI_FULL_OCR_ENDPOINT") or derived_endpoint).strip().rstrip("/")
        )
        self.device_key = str(
            device_key
            or os.getenv("INKPI_FULL_OCR_DEVICE_KEY")
            or os.getenv("INKPI_CLOUD_DEVICE_KEY")
            or ""
        ).strip()
        self.timeout = float(timeout or os.getenv("INKPI_FULL_OCR_TIMEOUT", "12.0"))

    def _bootstrap_env_from_file(self) -> None:
        """Load `.inkpi/cloud.env` so direct Python launches still see OCR backend config."""

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
                if key and not os.environ.get(key):
                    os.environ[key] = value
        except Exception as exc:  # noqa: BLE001
            self.logger.debug("Skip loading OCR env file %s: %s", env_path, exc)

    @property
    def available(self) -> bool:
        return bool(self.endpoint)

    def get_candidates(self, image, limit: int = 8) -> List[RecognitionCandidate]:
        if not self.available:
            return []

        ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
        if not ok:
            return []

        headers = {}
        if self.device_key:
            headers["X-Device-Key"] = self.device_key

        try:
            response = requests.post(
                self.endpoint,
                headers=headers,
                files={"image": ("frame.jpg", encoded.tobytes(), "image/jpeg")},
                data={"limit": str(limit)},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Remote OCR request failed: %s", exc)
            return []

        if not payload.get("ok", False):
            self.logger.warning("Remote OCR backend rejected request: %s", payload.get("error", "unknown"))
            return []

        items = payload.get("items") or []
        results: List[RecognitionCandidate] = []
        for item in items[:limit]:
            raw_key = item.get("key") or item.get("text") or item.get("display")
            if not raw_key:
                continue
            key = template_manager.resolve_character_key(str(raw_key))
            display = str(item.get("display") or template_manager.to_display_character(key))
            score = float(item.get("score", item.get("provider_score", 0.0)) or 0.0)
            results.append(
                RecognitionCandidate(
                    key=key,
                    display=display,
                    provider_score=score,
                    provider=self.name,
                )
            )
        return results
