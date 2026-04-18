"""Tests for the cloud OCR endpoint."""

from __future__ import annotations

import gc
import io
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import cv2
import numpy as np

from cloud_api.app import create_app


class _FakeOcrService:
    available = True

    def recognize(self, image):
        del image
        return type(
            "Recognition",
            (),
            {"character": "神", "confidence": 0.93, "source": "fake", "bbox": (1.0, 2.0, 30.0, 40.0)},
        )()


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
        self.app.extensions["ocr_service"] = _FakeOcrService()
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        self.client = None
        self.app = None
        gc.collect()
        self.temp_dir.cleanup()

    def test_device_ocr_endpoint_returns_recognition(self) -> None:
        image = np.ones((96, 96), dtype=np.uint8) * 255
        ok, encoded = cv2.imencode(".jpg", image)
        self.assertTrue(ok)

        response = self.client.post(
            "/api/device/ocr",
            headers={"X-Device-Key": "device-key"},
            data={
                "image": (io.BytesIO(encoded.tobytes()), "sample.jpg"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["item"]["character"], "神")
        self.assertAlmostEqual(payload["item"]["confidence"], 0.93, places=3)

    def test_device_ocr_endpoint_uses_local_only_service_when_not_injected(self) -> None:
        image = np.ones((96, 96), dtype=np.uint8) * 255
        ok, encoded = cv2.imencode(".jpg", image)
        self.assertTrue(ok)

        self.app.extensions.pop("ocr_service", None)

        class _LocalOnlyUnavailableService:
            available = False

            def recognize(self, image):
                del image
                return None

        with patch("services.local_ocr_service.LocalOcrService", return_value=_LocalOnlyUnavailableService()) as factory:
            response = self.client.post(
                "/api/device/ocr",
                headers={"X-Device-Key": "device-key"},
                data={
                    "image": (io.BytesIO(encoded.tobytes()), "sample.jpg"),
                },
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"], "ocr_service_unavailable")
        factory.assert_called_once_with(allow_remote_fallback=False)


if __name__ == "__main__":
    unittest.main()
