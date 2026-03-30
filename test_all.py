"""Regression tests for the single-chain InkPi runtime."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import tempfile
import unittest

import numpy as np

from cloud_api.app import create_app
from models.evaluation_result import EvaluationResult
from services.database_service import DatabaseService
from services.evaluation_service import evaluation_service
from services.preprocessing_service import PreprocessingError
from services.quality_scorer_service import QualityScore, quality_scorer_service
from services.local_ocr_service import OcrRecognition, local_ocr_service


@dataclass
class _PatchState:
    ocr_available: bool
    ocr_engine: object
    ocr_recognize: object
    scorer_session: object
    scorer_score: object


class EvaluationResultTests(unittest.TestCase):
    def test_to_dict_uses_new_fields(self) -> None:
        result = EvaluationResult(
            total_score=88,
            feedback="整体较稳，继续保持。",
            timestamp=datetime(2026, 3, 30, 12, 0, 0),
            character_name="水",
            ocr_confidence=0.93,
            quality_level="good",
            quality_confidence=0.81,
        )

        payload = result.to_dict()
        self.assertEqual(payload["character_name"], "水")
        self.assertEqual(payload["quality_level"], "good")
        self.assertNotIn("detail_scores", payload)
        self.assertNotIn("score_mode", payload)


class EvaluationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.patch = _PatchState(
            ocr_available=local_ocr_service._available,
            ocr_engine=local_ocr_service._ocr,
            ocr_recognize=local_ocr_service.recognize,
            scorer_session=quality_scorer_service._session,
            scorer_score=quality_scorer_service.score,
        )

    def tearDown(self) -> None:
        local_ocr_service._available = self.patch.ocr_available
        local_ocr_service._ocr = self.patch.ocr_engine
        local_ocr_service.recognize = self.patch.ocr_recognize  # type: ignore[method-assign]
        quality_scorer_service._session = self.patch.scorer_session  # type: ignore[assignment]
        quality_scorer_service.score = self.patch.scorer_score  # type: ignore[method-assign]

    def test_single_chain_evaluation_uses_ocr_and_onnx(self) -> None:
        local_ocr_service._available = True
        local_ocr_service._ocr = object()
        local_ocr_service.recognize = lambda _image: OcrRecognition(character="神", confidence=0.94)  # type: ignore[method-assign]
        quality_scorer_service._session = object()  # type: ignore[assignment]
        quality_scorer_service.score = (  # type: ignore[method-assign]
            lambda _image, character, ocr_confidence=None: QualityScore(
                total_score=91,
                quality_level="good",
                quality_confidence=0.89,
                probabilities={"bad": 0.02, "medium": 0.09, "good": 0.89},
            )
        )

        image = np.ones((224, 224), dtype=np.uint8) * 255
        result = evaluation_service.evaluate(image)
        self.assertEqual(result.character_name, "神")
        self.assertEqual(result.total_score, 91)
        self.assertEqual(result.quality_level, "good")
        self.assertAlmostEqual(result.ocr_confidence or 0.0, 0.94, places=3)

    def test_ocr_failure_blocks_scoring(self) -> None:
        local_ocr_service._available = True
        local_ocr_service._ocr = object()
        local_ocr_service.recognize = lambda _image: None  # type: ignore[method-assign]
        quality_scorer_service._session = object()  # type: ignore[assignment]

        image = np.ones((224, 224), dtype=np.uint8) * 255
        with self.assertRaises(PreprocessingError) as ctx:
            evaluation_service.evaluate(image)
        self.assertEqual(ctx.exception.error_type, "ocr_failed")


class DatabaseServiceTests(unittest.TestCase):
    def test_database_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = DatabaseService(Path(temp_dir) / "inkpi-test.db")
            result = EvaluationResult(
                total_score=77,
                feedback="结构稳定，继续练习。",
                timestamp=datetime.now(),
                character_name="永",
                ocr_confidence=0.87,
                quality_level="medium",
                quality_confidence=0.76,
            )

            record_id = service.save(result)
            fetched = service.get_by_id(record_id)
            self.assertIsNotNone(fetched)
            assert fetched is not None
            self.assertEqual(fetched.character_name, "永")
            self.assertEqual(fetched.quality_level, "medium")
            self.assertAlmostEqual(fetched.ocr_confidence or 0.0, 0.87, places=3)


class CloudApiTests(unittest.TestCase):
    def test_cloud_history_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(
                {
                    "TESTING": True,
                    "DATABASE": str(Path(temp_dir) / "cloud-test.db"),
                    "DEVICE_KEY": "device-key",
                    "DEFAULT_USERNAME": "demo",
                    "DEFAULT_PASSWORD": "demo123456",
                    "DEFAULT_DISPLAY_NAME": "InkPi Demo",
                }
            )
            client = app.test_client()

            login = client.post(
                "/api/auth/login",
                json={"username": "demo", "password": "demo123456"},
            )
            token = login.get_json()["token"]

            upload = client.post(
                "/api/device/results",
                headers={"X-Device-Key": "device-key", "X-Device-Name": "InkPi-RPi"},
                json={
                    "local_record_id": 3,
                    "total_score": 83,
                    "feedback": "整体较稳。",
                    "timestamp": "2026-03-30T18:00:00",
                    "character_name": "神",
                    "ocr_confidence": 0.91,
                    "quality_level": "medium",
                    "quality_confidence": 0.78,
                },
            )
            self.assertEqual(upload.status_code, 200)

            listing = client.get("/api/results", headers={"Authorization": f"Bearer {token}"})
            payload = listing.get_json()
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["items"][0]["character_name"], "神")
            self.assertEqual(payload["items"][0]["quality_level"], "medium")


if __name__ == "__main__":
    unittest.main()
