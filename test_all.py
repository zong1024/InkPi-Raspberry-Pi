"""Regression tests for the dual-script InkPi runtime."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from models.evaluation_result import EvaluationResult
from services.database_service import DatabaseService
from services.dimension_scorer_service import dimension_scorer_service
from services.evaluation_service import evaluation_service
from services.local_ocr_service import OcrRecognition, local_ocr_service
from services.preprocessing_service import PreprocessingError
from services.quality_scorer_service import QualityScore, quality_scorer_service


def build_quality_score(
    total_score: int = 91,
    level: str = "good",
    *,
    script: str = "regular",
) -> QualityScore:
    return QualityScore(
        total_score=total_score,
        quality_level=level,
        quality_confidence=0.89,
        probabilities={"bad": 0.03, "medium": 0.08, "good": 0.89},
        quality_features={
            "fg_ratio": 0.45,
            "bbox_ratio": 0.41,
            "center_quality": 0.91,
            "component_norm": 0.52,
            "edge_touch": 0.10,
            "texture_std": 0.15,
        },
        calibration={
            "script": script,
            "script_label": "楷书" if script == "regular" else "行书",
            "feature_quality": 0.86,
            "probability_margin": 0.81,
            "probability_margin_norm": 0.89,
            "quality_confidence_norm": 0.92,
            "score_range_fit": 0.88,
            "final_score": float(total_score),
            "quality_range_low": 82.0,
            "quality_range_high": 98.0,
            "score_source": "calibrated",
        },
    )


class EvaluationResultTests(unittest.TestCase):
    def test_roundtrip_keeps_script_dimension_scores_and_debug(self) -> None:
        result = EvaluationResult(
            total_score=88,
            feedback="整体比较稳定，继续保持。",
            timestamp=datetime(2026, 3, 30, 12, 0, 0),
            script="running",
            character_name="永",
            ocr_confidence=0.93,
            quality_level="good",
            quality_confidence=0.81,
            dimension_scores={
                "structure": 84,
                "stroke": 80,
                "integrity": 88,
                "stability": 82,
            },
            score_debug={
                "probabilities": {"good": 0.81},
                "quality_features": {"center_quality": 0.92},
                "geometry_features": {"projection_balance": 0.86},
                "calibration": {"feature_quality": 0.83},
            },
        )

        payload = result.to_dict()
        rebuilt = EvaluationResult.from_dict(payload)

        self.assertEqual(payload["character_name"], "永")
        self.assertEqual(payload["script"], "running")
        self.assertEqual(payload["script_label"], "行书")
        self.assertEqual(payload["dimension_scores"]["structure"], 84)
        self.assertEqual(payload["dimension_summary"]["best"]["label"], "完整")
        self.assertEqual(payload["dimension_basis"][0]["key"], "structure")
        self.assertEqual(payload["practice_profile"]["script"], "running")
        self.assertEqual(rebuilt.dimension_scores["stroke"], 80)
        self.assertEqual(rebuilt.get_script(), "running")
        self.assertEqual(rebuilt.score_debug["calibration"]["feature_quality"], 0.83)


class DimensionScorerServiceTests(unittest.TestCase):
    def test_dimension_scores_are_stable_integers_for_regular_and_running(self) -> None:
        base_inputs = {
            "probabilities": {"bad": 0.05, "medium": 0.15, "good": 0.80},
            "quality_features": {
                "fg_ratio": 0.44,
                "bbox_ratio": 0.40,
                "center_quality": 0.90,
                "component_norm": 0.56,
                "edge_touch": 0.08,
                "texture_std": 0.148,
            },
            "geometry_features": {
                "projection_balance": 0.88,
                "dominant_share": 0.86,
                "bbox_fill": 0.49,
                "touches_edge": 0.0,
                "subject_edge_safe": 1.0,
                "component_count": 2.0,
                "orientation_concentration": 0.28,
                "ink_ratio": 0.20,
            },
            "calibration": {
                "feature_quality": 0.84,
                "probability_margin_norm": 0.72,
                "quality_confidence_norm": 0.87,
                "score_range_fit": 0.82,
            },
            "ocr_confidence": 0.94,
        }

        regular_scores = dimension_scorer_service.compute_dimension_scores(
            **base_inputs,
            script="regular",
        )
        running_scores = dimension_scorer_service.compute_dimension_scores(
            **base_inputs,
            script="running",
        )

        self.assertEqual(set(regular_scores.keys()), {"structure", "stroke", "integrity", "stability"})
        self.assertTrue(all(isinstance(value, int) for value in regular_scores.values()))
        self.assertTrue(all(0 <= value <= 100 for value in regular_scores.values()))
        self.assertTrue(all(0 <= value <= 100 for value in running_scores.values()))
        self.assertNotEqual(regular_scores["stroke"], running_scores["stroke"])


class EvaluationServiceTests(unittest.TestCase):
    def test_dual_script_evaluation_uses_explicit_script(self) -> None:
        image = np.ones((224, 224), dtype=np.uint8) * 255

        with (
            patch.object(local_ocr_service, "_available", True),
            patch.object(local_ocr_service, "_ocr", object()),
            patch(
                "services.evaluation_service.local_ocr_service.recognize",
                return_value=OcrRecognition(character="永", confidence=0.94),
            ),
            patch(
                "services.evaluation_service.quality_scorer_service.is_script_available",
                return_value=True,
            ),
            patch(
                "services.evaluation_service.quality_scorer_service.score",
                return_value=build_quality_score(total_score=91, level="good", script="running"),
            ) as score_mock,
        ):
            result = evaluation_service.evaluate(image, script="running")

        self.assertEqual(result.character_name, "永")
        self.assertEqual(result.get_script(), "running")
        self.assertEqual(result.get_script_label(), "行书")
        self.assertEqual(result.total_score, 91)
        self.assertIn("按行书模型评测", result.feedback)
        self.assertEqual(result.score_debug["script"], "running")
        self.assertEqual(score_mock.call_args.kwargs["script"], "running")

    def test_missing_script_is_rejected(self) -> None:
        image = np.ones((64, 64), dtype=np.uint8) * 255
        with self.assertRaises(ValueError):
            evaluation_service.evaluate(image, script=None)

    def test_ocr_failure_blocks_scoring(self) -> None:
        image = np.ones((224, 224), dtype=np.uint8) * 255
        with (
            patch.object(local_ocr_service, "_available", True),
            patch.object(local_ocr_service, "_ocr", object()),
            patch("services.evaluation_service.local_ocr_service.recognize", return_value=None),
            patch(
                "services.evaluation_service.quality_scorer_service.is_script_available",
                return_value=True,
            ),
        ):
            with self.assertRaises(PreprocessingError) as ctx:
                evaluation_service.evaluate(image, script="regular")
        self.assertEqual(ctx.exception.error_type, "ocr_failed")

    def test_evaluation_prefers_explicit_ocr_image(self) -> None:
        score_inputs: dict[str, float] = {}

        def fake_recognize(image):
            score_inputs["ocr_mean"] = float(np.mean(image))
            return OcrRecognition(character="永", confidence=0.91)

        def fake_score(image, character, *, script, ocr_confidence=None):
            score_inputs["score_mean"] = float(np.mean(image))
            return build_quality_score(total_score=84, level="medium", script=script)

        processed_image = np.zeros((64, 64), dtype=np.uint8)
        ocr_image = np.ones((64, 64), dtype=np.uint8) * 255

        with (
            patch.object(local_ocr_service, "_available", True),
            patch.object(local_ocr_service, "_ocr", object()),
            patch("services.evaluation_service.local_ocr_service.recognize", side_effect=fake_recognize),
            patch(
                "services.evaluation_service.quality_scorer_service.is_script_available",
                return_value=True,
            ),
            patch("services.evaluation_service.quality_scorer_service.score", side_effect=fake_score),
        ):
            result = evaluation_service.evaluate(processed_image, script="regular", ocr_image=ocr_image)

        self.assertEqual(result.character_name, "永")
        self.assertGreater(score_inputs["ocr_mean"], 200.0)
        self.assertLess(score_inputs["score_mean"], 10.0)


class QualityScorerRoutingTests(unittest.TestCase):
    def test_service_exposes_dual_model_status(self) -> None:
        status = quality_scorer_service.get_model_status()
        self.assertIn("regular", status)
        self.assertIn("running", status)
        self.assertTrue(status["regular"]["model_path"].endswith("quality_scorer_regular.onnx"))
        self.assertTrue(status["running"]["metrics_path"].endswith("quality_scorer_running.metrics.json"))


class DatabaseServiceTests(unittest.TestCase):
    def test_database_roundtrip_keeps_script(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = DatabaseService(Path(temp_dir) / "inkpi-test.db")
            result = EvaluationResult(
                total_score=77,
                feedback="结构稳定，继续练习。",
                timestamp=datetime.now(),
                script="running",
                character_name="永",
                ocr_confidence=0.87,
                quality_level="medium",
                quality_confidence=0.76,
                dimension_scores={
                    "structure": 74,
                    "stroke": 72,
                    "integrity": 79,
                    "stability": 75,
                },
                score_debug={
                    "probabilities": {"medium": 0.76},
                    "quality_features": {"fg_ratio": 0.41},
                    "geometry_features": {"bbox_fill": 0.47},
                    "calibration": {"feature_quality": 0.74},
                },
            )

            record_id = service.save(result)
            fetched = service.get_by_id(record_id)

            self.assertIsNotNone(fetched)
            assert fetched is not None
            self.assertEqual(fetched.character_name, "永")
            self.assertEqual(fetched.get_script(), "running")
            self.assertEqual(fetched.get_script_label(), "行书")
            self.assertEqual(fetched.dimension_scores["integrity"], 79)
            self.assertEqual(fetched.score_debug["calibration"]["feature_quality"], 0.74)

    def test_database_migrates_existing_schema_with_regular_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "legacy.db"
            conn = sqlite3.connect(str(db_path))
            conn.execute(
                """
                CREATE TABLE evaluation_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    total_score INTEGER NOT NULL,
                    feedback TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    image_path TEXT,
                    processed_image_path TEXT,
                    character_name TEXT,
                    ocr_confidence REAL,
                    quality_level TEXT,
                    quality_confidence REAL
                )
                """
            )
            conn.execute(
                """
                INSERT INTO evaluation_records (
                    total_score, feedback, timestamp, image_path, processed_image_path,
                    character_name, ocr_confidence, quality_level, quality_confidence
                ) VALUES (80, 'legacy', '2026-04-01T10:00:00', NULL, NULL, '永', 0.8, 'medium', 0.7)
                """
            )
            conn.commit()
            conn.close()

            service = DatabaseService(db_path)
            fetched = service.get_by_id(1)

            self.assertIsNotNone(fetched)
            assert fetched is not None
            self.assertEqual(fetched.get_script(), "regular")


if __name__ == "__main__":
    unittest.main()
