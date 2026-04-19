"""Regression tests for the InkPi cloud API."""

from __future__ import annotations

import gc
import tempfile
import unittest
from pathlib import Path

from cloud_api.app import create_app
from models.evaluation_framework import RUBRIC_VERSION, build_rubric_items, build_rubric_preview_total


def build_upload_payload(
    local_record_id: int,
    total_score: int,
    quality_level: str,
    character_name: str,
    *,
    script: str = "regular",
    timestamp: str = "2026-03-30T12:34:56",
    rubric_scores: dict[str, int] | None = None,
) -> dict:
    default_scores = (
        {
            "bifa_dianhua": 80,
            "jieti_zifa": 80,
            "bubai_zhangfa": 60,
            "mofa_bili": 80,
            "guifan_wanzheng": 100,
        }
        if script == "regular"
        else {
            "yongbi_xianzhi": 80,
            "jieti_qushi": 60,
            "liandai_jiezou": 100,
            "moqi_bili": 80,
            "guifan_shibie": 60,
        }
    )
    scores = rubric_scores or default_scores
    rubric_items = build_rubric_items(scores, script=script)
    rubric_family = "regular_rubric_v1" if script == "regular" else "running_rubric_v1"

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
        "rubric_version": RUBRIC_VERSION,
        "rubric_family": rubric_family,
        "rubric_items": rubric_items,
        "rubric_summary": {
            "best": max(rubric_items, key=lambda item: item["score"]),
            "weakest": min(rubric_items, key=lambda item: item["score"]),
        },
        "rubric_source_refs": [],
        "rubric_preview_total": build_rubric_preview_total(rubric_items),
        "score_debug": {
            "probabilities": {"good": 0.91},
            "quality_features": {"center_quality": 0.92},
            "geometry_features": {"projection_balance": 0.86},
            "calibration": {"feature_quality": 0.84},
            "rubric_family": rubric_family,
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
        self.assertEqual(listing_payload["items"][0]["rubric_family"], "running_rubric_v1")
        self.assertEqual(listing_payload["items"][0]["rubric_items"][2]["label"], "连带节奏")
        self.assertNotIn("score_debug", listing_payload["items"][0])

        detail = self.client.get(f"/api/results/{result_id}", headers=headers)
        self.assertEqual(detail.status_code, 200)
        detail_payload = detail.get_json()["result"]
        self.assertEqual(detail_payload["ocr_confidence"], 0.97)
        self.assertEqual(detail_payload["quality_confidence"], 0.91)
        self.assertEqual(detail_payload["script"], "running")
        self.assertEqual(detail_payload["rubric_summary"]["best"]["label"], "连带节奏")
        self.assertEqual(detail_payload["practice_profile"]["script"], "running")
        self.assertEqual(detail_payload["scope_boundary"]["current_script"], "running")
        self.assertEqual(detail_payload["score_debug"]["calibration"]["feature_quality"], 0.84)
        self.assertEqual(detail_payload["expert_review_summary"]["validation_status"], "pending_review")

    def test_history_summary_methodology_and_delete(self) -> None:
        headers = self.login_headers()

        uploads = [
            build_upload_payload(
                local_record_id=1,
                total_score=95,
                quality_level="good",
                character_name="永",
                script="regular",
                timestamp="2026-04-06T12:00:00",
                rubric_scores={
                    "bifa_dianhua": 100,
                    "jieti_zifa": 80,
                    "bubai_zhangfa": 60,
                    "mofa_bili": 80,
                    "guifan_wanzheng": 100,
                },
            ),
            build_upload_payload(
                local_record_id=2,
                total_score=82,
                quality_level="medium",
                character_name="墨",
                script="running",
                timestamp="2026-04-05T12:00:00",
            ),
            build_upload_payload(
                local_record_id=3,
                total_score=68,
                quality_level="bad",
                character_name="永",
                script="regular",
                timestamp="2026-04-04T12:00:00",
                rubric_scores={
                    "bifa_dianhua": 40,
                    "jieti_zifa": 60,
                    "bubai_zhangfa": 40,
                    "mofa_bili": 40,
                    "guifan_wanzheng": 60,
                },
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
        self.assertAlmostEqual(summary_payload["rubric_averages"]["jieti_zifa"], 70.0)
        self.assertEqual(summary_payload["script_counts"]["regular"]["count"], 2)
        self.assertEqual(summary_payload["available_scripts"][0]["key"], "regular")
        self.assertTrue(summary_payload["available_devices"])

        methodology = self.client.get("/api/system/methodology?script=running", headers=headers)
        self.assertEqual(methodology.status_code, 200)
        methodology_payload = methodology.get_json()
        self.assertEqual(methodology_payload["framework_overview"]["current_scripts"], ["楷书", "行书"])
        self.assertEqual(methodology_payload["current_script_scope"]["script"], "running")
        self.assertEqual(methodology_payload["current_script_scope"]["script_label"], "行书")
        self.assertEqual(methodology_payload["rubric_definitions"]["running"]["items"][0]["label"], "用笔线质")
        self.assertEqual(methodology_payload["validation_snapshot"]["current_sample_count"], 3)
        self.assertEqual(methodology_payload["validation_plan"]["label_target"], 500)
        self.assertTrue(methodology_payload["rubric_source_catalog"][0]["organization"])

        validation = self.client.get("/api/validation/overview?script=regular", headers=headers)
        self.assertEqual(validation.status_code, 200)
        validation_payload = validation.get_json()
        self.assertIn("rubric_gap_averages", validation_payload["overview"])

        filtered = self.client.get("/api/results?keyword=永&quality_level=good&script=regular", headers=headers)
        self.assertEqual(filtered.status_code, 200)
        filtered_payload = filtered.get_json()
        self.assertEqual(filtered_payload["total"], 1)
        self.assertEqual(filtered_payload["items"][0]["total_score"], 95)

        result_id = filtered_payload["items"][0]["id"]
        delete_response = self.client.delete(f"/api/results/{result_id}", headers=headers)
        self.assertEqual(delete_response.status_code, 200)

        listing = self.client.get("/api/results?script=regular", headers=headers).get_json()
        self.assertEqual(listing["total"], 1)

    def test_expert_review_flow_uses_rubric_items(self) -> None:
        headers = self.login_headers()
        created = self.upload_result(
            build_upload_payload(
                local_record_id=22,
                total_score=84,
                quality_level="medium",
                character_name="墨",
                script="running",
            )
        )["result"]

        review_payload = {
            "reviewer_name": "张老师",
            "reviewer_role": "书法教师",
            "review_score": 86,
            "review_level": "medium",
            "rubric_version": "manual_rubric_v1",
            "rubric_items": [
                {"key": "yongbi_xianzhi", "label": "用笔线质", "score": 80},
                {"key": "jieti_qushi", "label": "结体取势", "score": 60},
            ],
            "notes": "线质较稳，但取势还需要再收一收。",
        }

        review_response = self.client.post(
            f"/api/results/{created['id']}/reviews",
            headers=headers,
            json=review_payload,
        )
        self.assertEqual(review_response.status_code, 200)
        review_json = review_response.get_json()
        self.assertEqual(review_json["review"]["reviewer_name"], "张老师")
        self.assertEqual(review_json["review"]["rubric_items"][0]["label"], "用笔线质")
        self.assertEqual(review_json["summary"]["review_count"], 1)

        detail = self.client.get(f"/api/results/{created['id']}", headers=headers).get_json()["result"]
        self.assertEqual(detail["expert_review_summary"]["validation_status"], "reviewed")
        self.assertEqual(detail["expert_reviews"][0]["rubric_items"][1]["key"], "jieti_qushi")


if __name__ == "__main__":
    unittest.main()
