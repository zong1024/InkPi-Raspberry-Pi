"""Regression tests for the InkPi cloud API."""

from __future__ import annotations

import gc
import tempfile
import unittest
from pathlib import Path

from cloud_api.app import create_app


class CloudApiTests(unittest.TestCase):
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
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        self.client = None
        self.app = None
        gc.collect()
        self.temp_dir.cleanup()

    def test_demo_login_and_history_roundtrip(self) -> None:
        login = self.client.post(
            "/api/auth/login",
            json={"username": "demo", "password": "demo123456"},
        )
        self.assertEqual(login.status_code, 200)
        data = login.get_json()
        self.assertTrue(data["ok"])
        token = data["token"]

        upload = self.client.post(
            "/api/device/results",
            headers={"X-Device-Key": "device-key", "X-Device-Name": "InkPi-RPi"},
            json={
                "local_record_id": 12,
                "total_score": 88,
                "feedback": "整体较稳，继续保持当前写法。",
                "timestamp": "2026-03-30T12:34:56",
                "character_name": "水",
                "ocr_confidence": 0.97,
                "quality_level": "good",
                "quality_confidence": 0.91,
            },
        )
        self.assertEqual(upload.status_code, 200)
        upload_payload = upload.get_json()
        self.assertTrue(upload_payload["ok"])
        result_id = upload_payload["result"]["id"]

        listing = self.client.get("/api/results", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(listing.status_code, 200)
        listing_payload = listing.get_json()
        self.assertTrue(listing_payload["ok"])
        self.assertEqual(listing_payload["total"], 1)
        self.assertEqual(listing_payload["items"][0]["character_name"], "水")
        self.assertEqual(listing_payload["items"][0]["quality_level"], "good")

        detail = self.client.get(f"/api/results/{result_id}", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(detail.status_code, 200)
        detail_payload = detail.get_json()
        self.assertEqual(detail_payload["result"]["ocr_confidence"], 0.97)
        self.assertEqual(detail_payload["result"]["quality_confidence"], 0.91)


if __name__ == "__main__":
    unittest.main()
