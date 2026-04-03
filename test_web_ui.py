"""Smoke tests for the local InkPi WebUI."""

from __future__ import annotations

from datetime import datetime
import unittest
from unittest.mock import patch

from models.evaluation_result import EvaluationResult
from web_ui.app import app, state


def build_result(record_id: int = 1) -> EvaluationResult:
    return EvaluationResult(
        id=record_id,
        total_score=86,
        feedback="整体完成度不错，可以继续稳定结构。",
        timestamp=datetime(2026, 4, 1, 10, 30, 0),
        character_name="永",
        ocr_confidence=0.95,
        quality_level="good",
        quality_confidence=0.88,
        dimension_scores={
            "structure": 84,
            "stroke": 79,
            "integrity": 90,
            "stability": 82,
        },
        score_debug={
            "probabilities": {"good": 0.88},
            "quality_features": {"center_quality": 0.91},
            "geometry_features": {"projection_balance": 0.85},
            "calibration": {"feature_quality": 0.83},
        },
    )


class WebUiSmokeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = app.test_client()
        with state.lock:
            state.last_result = None
            state.last_result_id = None

    def test_health(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        response.close()

    def test_index(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"InkPi", response.data)
        response.close()

    def test_bootstrap(self) -> None:
        result = build_result()
        with patch("web_ui.app.database_service.get_statistics", return_value={"total_count": 1, "average_score": 86, "max_score": 86, "min_score": 86}), \
             patch("web_ui.app.database_service.get_recent", return_value=[result]):
            response = self.client.get("/api/bootstrap")
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertIn("history", payload)
            self.assertIn("stats", payload)
            self.assertEqual(payload["history"][0]["dimension_scores"]["integrity"], 90)
            self.assertNotIn("score_debug", payload["history"][0])
            response.close()

    def test_history_endpoint(self) -> None:
        result = build_result()
        with patch("web_ui.app.database_service.get_all", return_value=[result]):
            response = self.client.get("/api/history")
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertIn("items", payload)
            self.assertIsInstance(payload["items"], list)
            self.assertEqual(payload["items"][0]["dimension_scores"]["structure"], 84)
            self.assertNotIn("score_debug", payload["items"][0])
            response.close()

    def test_detail_includes_debug_only_on_detail_endpoint(self) -> None:
        result = build_result(3)
        with patch("web_ui.app.database_service.get_by_id", return_value=result):
            response = self.client.get("/api/results/3")
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["dimension_scores"]["stability"], 82)
            self.assertIn("score_debug", payload)
            self.assertEqual(payload["score_debug"]["calibration"]["feature_quality"], 0.83)
            response.close()


if __name__ == "__main__":
    unittest.main()
