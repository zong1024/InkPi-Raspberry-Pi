"""Regression tests for the single-chain InkPi runtime."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sqlite3
import tempfile
import unittest

import numpy as np

from models.evaluation_result import EvaluationResult
from services.database_service import DatabaseService
from services.dimension_scorer_service import dimension_scorer_service
from services.evaluation_service import evaluation_service
from services.local_ocr_service import OcrRecognition, local_ocr_service
from services.preprocessing_service import PreprocessingError
from services.quality_scorer_service import QualityScore, quality_scorer_service


def build_quality_score(total_score: int = 91, level: str = "good") -> QualityScore:
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


@dataclass
class _PatchState:
    ocr_available: bool
    ocr_engine: object
    ocr_recognize: object
    scorer_session: object
    scorer_score: object


class EvaluationResultTests(unittest.TestCase):
    def test_roundtrip_keeps_dimension_scores_and_debug(self) -> None:
        result = EvaluationResult(
            total_score=88,
            feedback="整体比较稳定，继续保持。",
            timestamp=datetime(2026, 3, 30, 12, 0, 0),
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
        self.assertEqual(payload["quality_level"], "good")
        self.assertEqual(payload["dimension_scores"]["structure"], 84)
        self.assertEqual(payload["dimension_summary"]["best"]["label"], "完整")
        self.assertEqual(rebuilt.dimension_scores["stroke"], 80)
        self.assertEqual(rebuilt.score_debug["calibration"]["feature_quality"], 0.83)
        self.assertNotIn("detail_scores", payload)
        self.assertNotIn("score_mode", payload)


class DimensionScorerServiceTests(unittest.TestCase):
    def test_dimension_scores_are_stable_integers(self) -> None:
        scores = dimension_scorer_service.compute_dimension_scores(
            probabilities={"bad": 0.05, "medium": 0.15, "good": 0.80},
            quality_features={
                "fg_ratio": 0.44,
                "bbox_ratio": 0.40,
                "center_quality": 0.90,
                "component_norm": 0.56,
                "edge_touch": 0.08,
                "texture_std": 0.148,
            },
            geometry_features={
                "projection_balance": 0.88,
                "dominant_share": 0.86,
                "bbox_fill": 0.49,
                "touches_edge": 0.0,
                "subject_edge_safe": 1.0,
                "component_count": 2.0,
                "orientation_concentration": 0.28,
                "ink_ratio": 0.20,
            },
            calibration={
                "feature_quality": 0.84,
                "probability_margin_norm": 0.72,
                "quality_confidence_norm": 0.87,
                "score_range_fit": 0.82,
            },
            ocr_confidence=0.94,
        )

        self.assertEqual(set(scores.keys()), {"structure", "stroke", "integrity", "stability"})
        self.assertTrue(all(isinstance(value, int) for value in scores.values()))
        self.assertTrue(all(0 <= value <= 100 for value in scores.values()))
        self.assertGreater(scores["structure"], scores["stroke"] - 5)


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
            lambda _image, character, ocr_confidence=None: build_quality_score(total_score=91, level="good")
        )

        image = np.ones((224, 224), dtype=np.uint8) * 255
        result = evaluation_service.evaluate(image)
        self.assertEqual(result.character_name, "神")
        self.assertEqual(result.total_score, 91)
        self.assertEqual(result.quality_level, "good")
        self.assertAlmostEqual(result.ocr_confidence or 0.0, 0.94, places=3)
        self.assertIsNotNone(result.dimension_scores)
        self.assertIn("geometry_features", result.score_debug)

    def test_ocr_failure_blocks_scoring(self) -> None:
        local_ocr_service._available = True
        local_ocr_service._ocr = object()
        local_ocr_service.recognize = lambda _image: None  # type: ignore[method-assign]
        quality_scorer_service._session = object()  # type: ignore[assignment]

        image = np.ones((224, 224), dtype=np.uint8) * 255
        with self.assertRaises(PreprocessingError) as ctx:
            evaluation_service.evaluate(image)
        self.assertEqual(ctx.exception.error_type, "ocr_failed")

    def test_evaluation_prefers_explicit_ocr_image(self) -> None:
        local_ocr_service._available = True
        local_ocr_service._ocr = object()

        score_inputs = {}

        def fake_recognize(image):  # type: ignore[override]
            score_inputs["ocr_mean"] = float(np.mean(image))
            return OcrRecognition(character="永", confidence=0.91)

        def fake_score(image, character, ocr_confidence=None):  # type: ignore[override]
            score_inputs["score_mean"] = float(np.mean(image))
            return build_quality_score(total_score=84, level="medium")

        local_ocr_service.recognize = fake_recognize  # type: ignore[method-assign]
        quality_scorer_service._session = object()  # type: ignore[assignment]
        quality_scorer_service.score = fake_score  # type: ignore[method-assign]

        processed_image = np.zeros((64, 64), dtype=np.uint8)
        ocr_image = np.ones((64, 64), dtype=np.uint8) * 255
        result = evaluation_service.evaluate(processed_image, ocr_image=ocr_image)

        self.assertEqual(result.character_name, "永")
        self.assertGreater(score_inputs["ocr_mean"], 200.0)
        self.assertLess(score_inputs["score_mean"], 10.0)


class QualityScorerCalibrationTests(unittest.TestCase):
    def test_good_level_scores_are_not_flat(self) -> None:
        probabilities = np.asarray([0.0005, 0.02, 0.9795], dtype=np.float32)
        strong = np.asarray([0.46, 1.0, 0.97, 0.55, 0.48, 0.145], dtype=np.float32)
        weak = np.asarray([0.28, 1.0, 0.80, 1.0, 0.70, 0.18], dtype=np.float32)

        strong_score = quality_scorer_service._calibrate_total_score(  # type: ignore[attr-defined]
            probabilities=probabilities,
            quality_level="good",
            extras=strong,
            ocr_confidence=0.98,
        )
        weak_score = quality_scorer_service._calibrate_total_score(  # type: ignore[attr-defined]
            probabilities=probabilities,
            quality_level="good",
            extras=weak,
            ocr_confidence=0.80,
        )

        self.assertGreater(strong_score, weak_score)
        self.assertGreaterEqual(strong_score, 90)
        self.assertLessEqual(weak_score, 90)


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
            self.assertEqual(fetched.quality_level, "medium")
            self.assertAlmostEqual(fetched.ocr_confidence or 0.0, 0.87, places=3)
            self.assertEqual(fetched.dimension_scores["integrity"], 79)
            self.assertEqual(fetched.score_debug["calibration"]["feature_quality"], 0.74)

    def test_database_migrates_existing_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "legacy.db"
            conn = sqlite3.connect(str(db_path))
            conn.execute(
                """
                CREATE TABLE evaluation_results (
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
            conn.commit()
            conn.close()

            service = DatabaseService(db_path)
            result = EvaluationResult(
                total_score=83,
                feedback="迁移后保存成功。",
                timestamp=datetime.now(),
                character_name="神",
                quality_level="good",
                dimension_scores={
                    "structure": 82,
                    "stroke": 80,
                    "integrity": 86,
                    "stability": 84,
                },
                score_debug={"calibration": {"feature_quality": 0.8}},
            )

            record_id = service.save(result)
            fetched = service.get_by_id(record_id)

            self.assertIsNotNone(fetched)
            assert fetched is not None
            self.assertEqual(fetched.dimension_scores["structure"], 82)


if __name__ == "__main__":
    unittest.main()
