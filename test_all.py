"""Regression tests for the source-backed rubric InkPi runtime."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from models.evaluation_framework import LEGACY_RUBRIC_VERSION, RUBRIC_VERSION
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
    def test_roundtrip_keeps_script_rubric_and_debug(self) -> None:
        result = EvaluationResult.from_rubric_scores(
            total_score=88,
            feedback="整体比较稳定，继续保持。",
            timestamp=datetime(2026, 3, 30, 12, 0, 0),
            script="running",
            character_name="永",
            ocr_confidence=0.93,
            quality_level="good",
            quality_confidence=0.81,
            image_path=None,
            processed_image_path=None,
            rubric_family="running_rubric_v1",
            rubric_scores={
                "yongbi_xianzhi": 80,
                "jieti_qushi": 60,
                "liandai_jiezou": 100,
                "moqi_bili": 80,
                "guifan_shibie": 60,
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
        self.assertEqual(payload["rubric_version"], RUBRIC_VERSION)
        self.assertEqual(payload["rubric_family"], "running_rubric_v1")
        self.assertEqual(payload["rubric_items"][0]["basis_codes"][0], "CAA-EXAM-2018")
        self.assertEqual(payload["rubric_summary"]["best"]["label"], "连带节奏")
        self.assertEqual(payload["practice_profile"]["script"], "running")
        self.assertFalse(payload["is_legacy_standard"])
        self.assertEqual(rebuilt.get_rubric_items()[2]["label"], "连带节奏")
        self.assertEqual(rebuilt.score_debug["calibration"]["feature_quality"], 0.83)

    def test_legacy_payload_remains_legacy(self) -> None:
        result = EvaluationResult(
            total_score=76,
            feedback="旧版记录。",
            timestamp=datetime(2026, 3, 30, 12, 0, 0),
            script="regular",
            character_name="永",
            ocr_confidence=0.88,
            quality_level="medium",
            quality_confidence=0.73,
            dimension_scores={
                "structure": 80,
                "stroke": 74,
                "integrity": 78,
                "stability": 76,
            },
        )

        payload = result.to_dict()
        self.assertEqual(payload["rubric_version"], LEGACY_RUBRIC_VERSION)
        self.assertTrue(payload["is_legacy_standard"])
        self.assertIn("dimension_scores", payload)
        self.assertEqual(payload["practice_profile"]["stage_key"], "legacy")


class DimensionScorerServiceTests(unittest.TestCase):
    def test_rubric_scores_are_stable_anchor_values_for_regular_and_running(self) -> None:
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

        regular_scores = dimension_scorer_service.compute_rubric_scores(**base_inputs, script="regular")
        running_scores = dimension_scorer_service.compute_rubric_scores(**base_inputs, script="running")

        self.assertEqual(
            set(regular_scores.keys()),
            {"bifa_dianhua", "jieti_zifa", "bubai_zhangfa", "mofa_bili", "guifan_wanzheng"},
        )
        self.assertEqual(
            set(running_scores.keys()),
            {"yongbi_xianzhi", "jieti_qushi", "liandai_jiezou", "moqi_bili", "guifan_shibie"},
        )
        self.assertTrue(all(value in {20, 40, 60, 80, 100} for value in regular_scores.values()))
        self.assertTrue(all(value in {20, 40, 60, 80, 100} for value in running_scores.values()))
        self.assertNotEqual(regular_scores["bifa_dianhua"], running_scores["yongbi_xianzhi"])


class EvaluationServiceTests(unittest.TestCase):
    def test_dual_script_evaluation_uses_explicit_script_and_rubric(self) -> None:
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
        self.assertIn("按 行书 模型生成主分", result.feedback)
        self.assertEqual(result.score_debug["script"], "running")
        self.assertEqual(score_mock.call_args.kwargs["script"], "running")
        self.assertEqual(result.get_rubric_version(), RUBRIC_VERSION)
        self.assertEqual(result.get_rubric_family(), "running_rubric_v1")
        self.assertEqual(len(result.get_rubric_items()), 5)

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

        def fake_score(image, character, *, script, ocr_confidence):
            score_inputs["score_mean"] = float(np.mean(image))
            score_inputs["score_script"] = script
            score_inputs["score_ocr_confidence"] = ocr_confidence
            return build_quality_score(total_score=84, level="medium", script=script)

        processed_image = np.ones((64, 64), dtype=np.uint8) * 180
        ocr_image = np.ones((64, 64), dtype=np.uint8) * 70

        with (
            patch.object(local_ocr_service, "_available", True),
            patch.object(local_ocr_service, "_ocr", object()),
            patch("services.evaluation_service.local_ocr_service.recognize", side_effect=fake_recognize),
            patch("services.evaluation_service.quality_scorer_service.is_script_available", return_value=True),
            patch("services.evaluation_service.quality_scorer_service.score", side_effect=fake_score),
        ):
            result = evaluation_service.evaluate(
                processed_image,
                script="regular",
                ocr_image=ocr_image,
            )

        self.assertEqual(score_inputs["ocr_mean"], float(np.mean(ocr_image)))
        self.assertEqual(score_inputs["score_mean"], float(np.mean(processed_image)))
        self.assertEqual(score_inputs["score_script"], "regular")
        self.assertEqual(score_inputs["score_ocr_confidence"], 0.91)
        self.assertEqual(result.get_rubric_family(), "regular_rubric_v1")


class DatabaseServiceTests(unittest.TestCase):
    def test_database_roundtrip_keeps_rubric_and_legacy_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db = DatabaseService(Path(temp_dir) / "results.db")

            new_result = EvaluationResult.from_rubric_scores(
                total_score=87,
                feedback="新标准记录。",
                timestamp=datetime(2026, 4, 1, 9, 30, 0),
                script="regular",
                character_name="永",
                ocr_confidence=0.97,
                quality_level="good",
                quality_confidence=0.9,
                image_path=None,
                processed_image_path=None,
                rubric_family="regular_rubric_v1",
                rubric_scores={
                    "bifa_dianhua": 80,
                    "jieti_zifa": 80,
                    "bubai_zhangfa": 60,
                    "mofa_bili": 80,
                    "guifan_wanzheng": 100,
                },
                score_debug={"calibration": {"feature_quality": 0.88}},
            )
            legacy_result = EvaluationResult(
                total_score=74,
                feedback="旧标准记录。",
                timestamp=datetime(2026, 4, 1, 10, 30, 0),
                script="regular",
                character_name="墨",
                ocr_confidence=0.88,
                quality_level="medium",
                quality_confidence=0.74,
                dimension_scores={
                    "structure": 78,
                    "stroke": 72,
                    "integrity": 74,
                    "stability": 70,
                },
            )

            new_id = db.save(new_result)
            legacy_id = db.save(legacy_result)

            fetched_new = db.get_by_id(new_id)
            fetched_legacy = db.get_by_id(legacy_id)

            self.assertIsNotNone(fetched_new)
            self.assertIsNotNone(fetched_legacy)
            self.assertEqual(fetched_new.get_rubric_version(), RUBRIC_VERSION)
            self.assertEqual(fetched_new.get_rubric_family(), "regular_rubric_v1")
            self.assertEqual(fetched_new.get_rubric_summary()["best"]["label"], "规范完整")
            self.assertEqual(fetched_legacy.get_rubric_version(), LEGACY_RUBRIC_VERSION)
            self.assertTrue(fetched_legacy.is_legacy_standard())
            self.assertEqual(fetched_legacy.dimension_scores["integrity"], 74)


if __name__ == "__main__":
    unittest.main()
