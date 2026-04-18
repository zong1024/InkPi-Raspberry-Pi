"""Regression tests for the InkPi cloud API."""

from __future__ import annotations

import gc
import tempfile
import unittest
from pathlib import Path

from cloud_api.app import create_app


def build_upload_payload(
    local_record_id: int,
    total_score: int,
    quality_level: str,
    character_name: str,
    *,
    script: str = "regular",
    timestamp: str = "2026-03-30T12:34:56",
    dimension_scores: dict[str, int] | None = None,
) -> dict:
    return {
        "local_record_id": local_record_id,
        "total_score": total_score,
        "feedback": "整体表现稳定，继续保持当前状态。",
        "timestamp": timestamp,
        "script": script,
        "character_name": character_name,
        "ocr_confidence": 0.97,
        "quality_level": quality_level,
        "quality_confidence": 0.91,
        "dimension_scores": dimension_scores
        or {
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

    def upload_result(self, payload: dict, device_name: str = "InkPi-RPi") -> dict:
        response = self.client.post(
            "/api/device/results",
            headers={"X-Device-Key": "device-key", "X-Device-Name": device_name},
            json=payload,
        )
        self.assertEqual(response.status_code, 200)
        return response.get_json()

    def test_demo_login_and_history_roundtrip(self) -> None:
        headers = self.login_headers()

        upload_payload = self.upload_result(
            build_upload_payload(
                local_record_id=12,
                total_score=88,
                quality_level="good",
                character_name="永",
                script="running",
            )
        )
        self.assertTrue(upload_payload["ok"])
        result_id = upload_payload["result"]["id"]

        listing = self.client.get("/api/results?script=running", headers=headers)
        self.assertEqual(listing.status_code, 200)
        listing_payload = listing.get_json()
        self.assertTrue(listing_payload["ok"])
        self.assertEqual(listing_payload["total"], 1)
        self.assertEqual(listing_payload["items"][0]["character_name"], "永")
        self.assertEqual(listing_payload["items"][0]["quality_level"], "good")
        self.assertEqual(listing_payload["items"][0]["script"], "running")
        self.assertEqual(listing_payload["items"][0]["script_label"], "行书")
        self.assertEqual(listing_payload["items"][0]["dimension_scores"]["integrity"], 88)
        self.assertNotIn("score_debug", listing_payload["items"][0])

        detail = self.client.get(f"/api/results/{result_id}", headers=headers)
        self.assertEqual(detail.status_code, 200)
        detail_payload = detail.get_json()["result"]
        self.assertEqual(detail_payload["ocr_confidence"], 0.97)
        self.assertEqual(detail_payload["quality_confidence"], 0.91)
        self.assertEqual(detail_payload["script"], "running")
        self.assertEqual(detail_payload["dimension_scores"]["structure"], 84)
        self.assertEqual(detail_payload["dimension_basis"][0]["label"], "结构")
        self.assertEqual(detail_payload["practice_profile"]["script"], "running")
        self.assertEqual(detail_payload["scope_boundary"]["current_script"], "running")
        self.assertEqual(detail_payload["score_debug"]["calibration"]["feature_quality"], 0.84)
        self.assertEqual(detail_payload["expert_review_summary"]["validation_status"], "pending_review")

    def test_history_summary_quantitative_fields_filters_and_delete(self) -> None:
        headers = self.login_headers()

        uploads = [
            build_upload_payload(
                local_record_id=1,
                total_score=95,
                quality_level="good",
                character_name="永",
                script="regular",
                timestamp="2026-04-06T12:00:00",
                dimension_scores={"structure": 94, "stroke": 90, "integrity": 92, "stability": 96},
            ),
            build_upload_payload(
                local_record_id=2,
                total_score=82,
                quality_level="medium",
                character_name="墨",
                script="running",
                timestamp="2026-04-05T12:00:00",
                dimension_scores={"structure": 80, "stroke": 82, "integrity": 84, "stability": 86},
            ),
            build_upload_payload(
                local_record_id=3,
                total_score=68,
                quality_level="bad",
                character_name="永",
                script="regular",
                timestamp="2026-04-04T12:00:00",
                dimension_scores={"structure": 66, "stroke": 64, "integrity": 70, "stability": 68},
            ),
        ]

        for payload in uploads:
            self.upload_result(payload)

        summary = self.client.get("/api/results/summary?script=regular", headers=headers)
        self.assertEqual(summary.status_code, 200)
        summary_payload = summary.get_json()["summary"]

        self.assertEqual(summary_payload["total"], 2)
        self.assertEqual(summary_payload["quality_counts"]["good"], 1)
        self.assertEqual(summary_payload["quality_counts"]["bad"], 1)
        self.assertEqual(summary_payload["score_distribution"]["90_plus"], 1)
        self.assertEqual(summary_payload["score_distribution"]["below_70"], 1)
        self.assertEqual(summary_payload["top_characters"][0]["character_name"], "永")
        self.assertAlmostEqual(summary_payload["dimension_averages"]["structure"], 80.0)
        self.assertEqual(summary_payload["script_counts"]["regular"]["count"], 2)
        self.assertEqual(summary_payload["available_scripts"][0]["key"], "regular")
        self.assertTrue(summary_payload["available_devices"])

        methodology = self.client.get("/api/system/methodology?script=running", headers=headers)
        self.assertEqual(methodology.status_code, 200)
        methodology_payload = methodology.get_json()
        self.assertEqual(methodology_payload["framework_overview"]["current_scripts"], ["楷书", "行书"])
        self.assertEqual(methodology_payload["current_script_scope"]["script"], "running")
        self.assertEqual(methodology_payload["current_script_scope"]["script_label"], "行书")
        self.assertEqual(methodology_payload["dimension_basis"][0]["label"], "结构")
        self.assertEqual(methodology_payload["validation_snapshot"]["current_sample_count"], 3)
        self.assertEqual(methodology_payload["validation_plan"]["label_target"], 500)

        filtered = self.client.get("/api/results?keyword=永&quality_level=good&script=regular", headers=headers)
        self.assertEqual(filtered.status_code, 200)
        filtered_payload = filtered.get_json()
        self.assertEqual(filtered_payload["total"], 1)
        self.assertEqual(filtered_payload["items"][0]["character_name"], "永")
        self.assertEqual(filtered_payload["items"][0]["script"], "regular")

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

    def test_expert_review_roundtrip_and_validation_metrics(self) -> None:
        headers = self.login_headers()

        upload = self.upload_result(
            build_upload_payload(
                local_record_id=99,
                total_score=88,
                quality_level="good",
                character_name="永",
                script="regular",
                dimension_scores={"structure": 84, "stroke": 80, "integrity": 88, "stability": 82},
            )
        )
        result_id = upload["result"]["id"]

        review_response = self.client.post(
            f"/api/results/{result_id}/reviews",
            headers=headers,
            json={
                "reviewer_name": "王老师",
                "reviewer_role": "书法教师",
                "review_score": 89,
                "dimension_scores": {
                    "structure": 86,
                    "stroke": 81,
                    "integrity": 90,
                    "stability": 84,
                },
                "notes": "结构较稳，收笔还可以更干净。",
            },
        )
        self.assertEqual(review_response.status_code, 200)
        review_payload = review_response.get_json()
        self.assertEqual(review_payload["review"]["reviewer_name"], "王老师")
        self.assertEqual(review_payload["summary"]["review_count"], 1)
        self.assertTrue(review_payload["summary"]["agreement"])
        self.assertEqual(review_payload["summary"]["average_review_score"], 89.0)
        self.assertEqual(review_payload["summary"]["score_gap"], 1.0)

        review_listing = self.client.get(f"/api/results/{result_id}/reviews", headers=headers)
        self.assertEqual(review_listing.status_code, 200)
        review_listing_payload = review_listing.get_json()
        self.assertEqual(len(review_listing_payload["items"]), 1)
        self.assertEqual(review_listing_payload["items"][0]["dimension_scores"]["structure"], 86.0)
        self.assertEqual(review_listing_payload["summary"]["validation_status"], "reviewed")

        detail = self.client.get(f"/api/results/{result_id}", headers=headers)
        self.assertEqual(detail.status_code, 200)
        detail_payload = detail.get_json()["result"]
        self.assertEqual(detail_payload["expert_review_summary"]["review_count"], 1)
        self.assertEqual(detail_payload["expert_reviews"][0]["reviewer_role"], "书法教师")

        validation = self.client.get("/api/validation/overview?script=regular", headers=headers)
        self.assertEqual(validation.status_code, 200)
        validation_payload = validation.get_json()
        self.assertEqual(validation_payload["overview"]["reviewed_result_count"], 1)
        self.assertEqual(validation_payload["overview"]["review_record_count"], 1)
        self.assertEqual(validation_payload["overview"]["pending_review_count"], 0)
        self.assertEqual(validation_payload["overview"]["review_coverage_rate"], 100.0)
        self.assertEqual(validation_payload["overview"]["agreement_rate"], 100.0)
        self.assertEqual(validation_payload["overview"]["average_manual_score"], 89.0)
        self.assertEqual(validation_payload["overview"]["average_score_gap"], 1.0)
        self.assertAlmostEqual(validation_payload["overview"]["dimension_gap_averages"]["structure"], 2.0)
        self.assertEqual(validation_payload["validation_snapshot"]["reviewed_result_count"], 1)
        self.assertEqual(validation_payload["validation_plan"]["expert_review_target"], 3)


if __name__ == "__main__":
    unittest.main()
