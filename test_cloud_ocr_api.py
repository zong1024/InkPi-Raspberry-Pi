"""Tests for the cloud OCR candidate endpoint."""

from __future__ import annotations

import gc
import io
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from cloud_api.app import create_app


class _FakeOcrProvider:
    available = True

    def get_candidates(self, image, limit: int = 8):
        del image
        return [
            type("Candidate", (), {"key": "shen", "display": "神", "provider_score": 0.93, "provider": "fake"}),
            type("Candidate", (), {"key": "shui", "display": "水", "provider_score": 0.61, "provider": "fake"}),
        ][:limit]


class CloudOcrApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "cloud-test.db"
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE": str(db_path),
                "DEVICE_KEY": "device-key",
                "DEFAULT_USERNAME": "demo",
                "DEFAULT_PASSWORD": "demo123456",
                "DEFAULT_DISPLAY_NAME": "InkPi Demo",
            }
        )
        self.app.extensions["full_ocr_provider"] = _FakeOcrProvider()
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        self.client = None
        self.app = None
        gc.collect()
        self.temp_dir.cleanup()

    def test_device_ocr_endpoint_returns_candidates(self) -> None:
        image = np.ones((96, 96), dtype=np.uint8) * 255
        ok, encoded = cv2.imencode(".jpg", image)
        self.assertTrue(ok)

        response = self.client.post(
            "/api/device/full-recognition/candidates",
            headers={"X-Device-Key": "device-key"},
            data={
                "limit": "4",
                "image": (io.BytesIO(encoded.tobytes()), "sample.jpg"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["items"][0]["display"], "神")
        self.assertEqual(payload["items"][1]["display"], "水")


if __name__ == "__main__":
    unittest.main()
