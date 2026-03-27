"""Application-facing tests for the isolated full-recognition service."""

from __future__ import annotations

import unittest
from pathlib import Path

import cv2
import numpy as np

from full_recognition_v2.pipeline import FullRecognitionPipeline
from full_recognition_v2.providers import ScriptedCandidateProvider
from full_recognition_v2.service import FullRecognitionService


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
            FullRecognitionPipeline(providers=[ScriptedCandidateProvider(["黄"])])
        )
        analysis = service.analyze(image)

        self.assertEqual(analysis.status, "untemplated")
        self.assertFalse(analysis.score_ready)
        self.assertEqual(analysis.next_action, "add_template")
        self.assertEqual(analysis.character_display, "黄")

    def test_rejected_analysis_requests_retry(self) -> None:
        blank = np.ones((224, 224), dtype=np.uint8) * 255
        service = FullRecognitionService(FullRecognitionPipeline())
        analysis = service.analyze(blank)

        self.assertEqual(analysis.status, "rejected")
        self.assertEqual(analysis.next_action, "retry")
        self.assertFalse(analysis.score_ready)


if __name__ == "__main__":
    unittest.main()
