"""Regression tests for the InkPi cloud API."""

from __future__ import annotations

import gc
import tempfile
import unittest
from pathlib import Path

from cloud_api.app import create_app


def build_upload_payload(local_record_id: int, total_score: int, quality_level: str, character_name: str) -> dict:
    return {
        "local_record_id": local_record_id,
        "total_score": total_score,
        "feedback": "整体表现稳定，继续保持当前状态。",
        "timestamp": "2026-03-30T12:34:56",
        "character_name": character_name,
        "ocr_confidence": 0.97,
        "quality_level": quality_level,
        "quality_confidence": 0.91,
        "dimension_scores": {
            "structure": 84,
            "stroke": 80,
            "integrity": 88,
            "stability": 82,
        },
        "score_debug": {
            "probabilities": {"good": 0.91},
            "quality_features": {"center_quality": 0.92},
            "geometry_features": {"projection_balance": 0.86},
            "calibration": {"feature_quality": 0.84},
        },
    }


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

    def login_headers(self) -> dict[str, str]:
        login = self.client.post(
            "/api/auth/login",
            json={"username": "demo", "password": "demo123456"},
        )
        self.assertEqual(login.status_code, 200)
        return {"Authorization": f"Bearer {login.get_json()['token']}"}

    def test_demo_login_and_history_roundtrip(self) -> None:
        headers = self.login_headers()

        upload = self.client.post(
            "/api/device/results",
            headers={"X-Device-Key": "device-key", "X-Device-Name": "InkPi-RPi"},
            json=build_upload_payload(local_record_id=12, total_score=88, quality_level="good", character_name="永"),
        )
        self.assertEqual(upload.status_code, 200)
        upload_payload = upload.get_json()
        self.assertTrue(upload_payload["ok"])
        result_id = upload_payload["result"]["id"]

        listing = self.client.get("/api/results", headers=headers)
        self.assertEqual(listing.status_code, 200)
        listing_payload = listing.get_json()
        self.assertTrue(listing_payload["ok"])
        self.assertEqual(listing_payload["total"], 1)
        self.assertEqual(listing_payload["items"][0]["character_name"], "永")
        self.assertEqual(listing_payload["items"][0]["quality_level"], "good")
        self.assertEqual(listing_payload["items"][0]["dimension_scores"]["integrity"], 88)
        self.assertNotIn("score_debug", listing_payload["items"][0])

        detail = self.client.get(f"/api/results/{result_id}", headers=headers)
        self.assertEqual(detail.status_code, 200)
        detail_payload = detail.get_json()
        self.assertEqual(detail_payload["result"]["ocr_confidence"], 0.97)
        self.assertEqual(detail_payload["result"]["quality_confidence"], 0.91)
        self.assertEqual(detail_payload["result"]["dimension_scores"]["structure"], 84)
        self.assertEqual(detail_payload["result"]["score_debug"]["calibration"]["feature_quality"], 0.84)

    def test_history_summary_filters_and_delete(self) -> None:
        headers = self.login_headers()

        uploads = [
            build_upload_payload(local_record_id=1, total_score=92, quality_level="good", character_name="神"),
            build_upload_payload(local_record_id=2, total_score=76, quality_level="medium", character_name="永"),
            build_upload_payload(local_record_id=3, total_score=61, quality_level="bad", character_name="神"),
        ]

        for payload in uploads:
          response = self.client.post(
              "/api/device/results",
              headers={"X-Device-Key": "device-key", "X-Device-Name": "InkPi-RPi"},
              json=payload,
          )
          self.assertEqual(response.status_code, 200)

        summary = self.client.get("/api/results/summary", headers=headers)
        self.assertEqual(summary.status_code, 200)
        summary_payload = summary.get_json()["summary"]
        self.assertEqual(summary_payload["total"], 3)
        self.assertEqual(summary_payload["quality_counts"]["good"], 1)
        self.assertEqual(summary_payload["top_characters"][0]["character_name"], "神")

        filtered = self.client.get("/api/results?keyword=神&quality_level=good", headers=headers)
        self.assertEqual(filtered.status_code, 200)
        filtered_payload = filtered.get_json()
        self.assertEqual(filtered_payload["total"], 1)
        self.assertEqual(filtered_payload["items"][0]["character_name"], "神")
        self.assertEqual(filtered_payload["items"][0]["quality_level"], "good")

        result_id = filtered_payload["items"][0]["id"]
        deleted = self.client.delete(f"/api/results/{result_id}", headers=headers)
        self.assertEqual(deleted.status_code, 200)

        listing = self.client.get("/api/results", headers=headers)
        self.assertEqual(listing.get_json()["total"], 2)

        remaining_ids = [item["id"] for item in listing.get_json()["items"]]
        batch_deleted = self.client.post(
            "/api/results/batch-delete",
            headers=headers,
            json={"ids": remaining_ids},
        )
        self.assertEqual(batch_deleted.status_code, 200)
        self.assertEqual(batch_deleted.get_json()["deleted_count"], 2)


if __name__ == "__main__":
    unittest.main()
