"""Application-facing tests for the isolated full-recognition service."""

from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from full_recognition_v2.pipeline import FullRecognitionPipeline
from full_recognition_v2.providers import ScriptedCandidateProvider
from full_recognition_v2.service import (
    FullRecognitionAnalysis,
    FullRecognitionCandidateView,
    FullRecognitionService,
)
from services.template_manager import template_manager


class FullRecognitionServiceV2Test(unittest.TestCase):
    def _template_path(self, name: str) -> Path:
        return Path(__file__).resolve().parent / "models" / "templates" / name

    def test_matched_analysis_is_score_ready(self) -> None:
        image = cv2.imread(str(self._template_path("shen_kaishu_standard.png")), cv2.IMREAD_GRAYSCALE)
        self.assertIsNotNone(image)

        service = FullRecognitionService(
            FullRecognitionPipeline(providers=[ScriptedCandidateProvider(["shen", "yong"])])
        )
        analysis = service.analyze(image)

        self.assertEqual(analysis.status, "matched")
        self.assertTrue(analysis.score_ready)
        self.assertEqual(analysis.next_action, "score")
        self.assertEqual(analysis.character_key, "shen")

    def test_untemplated_analysis_surfaces_character_and_next_step(self) -> None:
        image = cv2.imread(str(self._template_path("shui_kaishu_standard.png")), cv2.IMREAD_GRAYSCALE)
        self.assertIsNotNone(image)

        service = FullRecognitionService(
            FullRecognitionPipeline(providers=[ScriptedCandidateProvider(["龙"])])
        )
        analysis = service.analyze(image)

        self.assertEqual(analysis.status, "untemplated")
        self.assertFalse(analysis.score_ready)
        self.assertEqual(analysis.next_action, "add_template")
        self.assertEqual(analysis.character_display, "龙")

    def test_rejected_analysis_requests_retry(self) -> None:
        blank = np.ones((224, 224), dtype=np.uint8) * 255
        service = FullRecognitionService(FullRecognitionPipeline())
        analysis = service.analyze(blank)

        self.assertEqual(analysis.status, "rejected")
        self.assertEqual(analysis.next_action, "retry")
        self.assertFalse(analysis.score_ready)

    def test_bootstrap_template_turns_untemplated_into_matched(self) -> None:
        image = cv2.imread(str(self._template_path("shui_kaishu_standard.png")), cv2.IMREAD_GRAYSCALE)
        self.assertIsNotNone(image)

        service = FullRecognitionService(
            FullRecognitionPipeline(providers=[ScriptedCandidateProvider(["龙"])])
        )

        original_dir = template_manager.template_dir
        original_templates = copy.deepcopy(template_manager._templates)
        original_cache = dict(template_manager._cache)

        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                template_manager.template_dir = Path(temp_dir)
                template_manager._templates = {}
                template_manager._cache = {}

                before = service.analyze(image)
                self.assertEqual(before.status, "untemplated")

                result = service.bootstrap_template(image, min_confidence=0.5)
                self.assertTrue(result.created)
                self.assertEqual(result.after_status, "matched")
                self.assertTrue(Path(result.template_path).exists())

                after = service.analyze(image)
                self.assertEqual(after.status, "matched")
                self.assertTrue(after.score_ready)
            finally:
                template_manager.template_dir = original_dir
                template_manager._templates = original_templates
                template_manager._cache = original_cache

    def test_bootstrap_template_can_promote_strong_unsupported_candidate(self) -> None:
        image = cv2.imread(str(self._template_path("shui_kaishu_standard.png")), cv2.IMREAD_GRAYSCALE)
        self.assertIsNotNone(image)

        service = FullRecognitionService()

        before = FullRecognitionAnalysis(
            status="unsupported",
            character_key=None,
            character_display=None,
            confidence=0.41,
            score_ready=False,
            template_ready=False,
            title="Unsupported",
            message="Need bootstrap",
            next_action="review",
            candidates=[
                FullRecognitionCandidateView(key="黄", display="黄", confidence=0.91, source="paddleocr"),
                FullRecognitionCandidateView(key="朝", display="朝", confidence=0.73, source="paddleocr"),
            ],
        )
        after = FullRecognitionAnalysis(
            status="matched",
            character_key="黄",
            character_display="黄",
            confidence=0.88,
            score_ready=True,
            template_ready=True,
            title="Matched",
            message="Ready",
            next_action="score",
            candidates=[
                FullRecognitionCandidateView(key="黄", display="黄", confidence=0.91, source="paddleocr")
            ],
        )

        analyze_calls: list[int] = []

        def fake_analyze(_image, limit: int = 8):
            del limit
            analyze_calls.append(1)
            return before if len(analyze_calls) == 1 else after

        service.analyze = fake_analyze  # type: ignore[method-assign]
        service.extract_template_seed = lambda _image: image  # type: ignore[method-assign]

        original_dir = template_manager.template_dir
        original_templates = copy.deepcopy(template_manager._templates)
        original_cache = dict(template_manager._cache)

        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                template_manager.template_dir = Path(temp_dir)
                template_manager._templates = {}
                template_manager._cache = {}

                result = service.bootstrap_template(image, min_confidence=0.82)
                self.assertTrue(result.created)
                self.assertEqual(result.character_display, "黄")
                self.assertEqual(result.after_status, "matched")
                self.assertTrue(Path(result.template_path).exists())
            finally:
                template_manager.template_dir = original_dir
                template_manager._templates = original_templates
                template_manager._cache = original_cache

    def test_bootstrap_template_rolls_back_unusable_saved_template(self) -> None:
        image = cv2.imread(str(self._template_path("shui_kaishu_standard.png")), cv2.IMREAD_GRAYSCALE)
        self.assertIsNotNone(image)

        service = FullRecognitionService(
            FullRecognitionPipeline(providers=[ScriptedCandidateProvider(["龙"])])
        )

        original_dir = template_manager.template_dir
        original_templates = copy.deepcopy(template_manager._templates)
        original_cache = dict(template_manager._cache)
        original_load_image = template_manager.load_image

        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                template_manager.template_dir = Path(temp_dir)
                template_manager._templates = {}
                template_manager._cache = {}

                def fake_load_image(path, flags=0):
                    result = original_load_image(path, flags)
                    if result is None:
                        return None
                    if str(path).endswith("_bootstrap.png"):
                        return np.ones_like(result) * 255
                    return result

                template_manager.load_image = fake_load_image  # type: ignore[method-assign]

                result = service.bootstrap_template(image, min_confidence=0.5)
                self.assertFalse(result.created)
                self.assertIn("回滚", result.message)
                self.assertFalse(any(Path(temp_dir).glob("*.png")))
            finally:
                template_manager.template_dir = original_dir
                template_manager._templates = original_templates
                template_manager._cache = original_cache
                template_manager.load_image = original_load_image  # type: ignore[method-assign]


if __name__ == "__main__":
    unittest.main()
