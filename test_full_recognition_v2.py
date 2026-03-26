"""Smoke tests for the isolated next-gen recognition pipeline."""

from __future__ import annotations

import unittest
from pathlib import Path

import cv2
import numpy as np

from full_recognition_v2.pipeline import FullRecognitionPipeline
from full_recognition_v2.providers import ScriptedCandidateProvider


class FullRecognitionV2Test(unittest.TestCase):
    def test_blank_image_is_rejected(self) -> None:
        pipeline = FullRecognitionPipeline()
        blank = np.ones((224, 224), dtype=np.uint8) * 255
        decision = pipeline.analyze(blank)
        self.assertEqual(decision.status, "rejected")

    def test_scripted_candidate_matches_shen_template(self) -> None:
        template_path = Path("C:/Users/zongrui/Documents/2/models/templates/shen_kaishu_standard.png")
        image = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
        self.assertIsNotNone(image)

        pipeline = FullRecognitionPipeline(
            providers=[ScriptedCandidateProvider(["shen", "yong", "shui"])]
        )
        decision = pipeline.analyze(image)
        self.assertEqual(decision.status, "matched")
        self.assertEqual(decision.character_key, "shen")

    def test_competing_candidates_can_be_ambiguous(self) -> None:
        template_path = Path("C:/Users/zongrui/Documents/2/models/templates/shui_kaishu_standard.png")
        image = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
        self.assertIsNotNone(image)

        pipeline = FullRecognitionPipeline(
            providers=[ScriptedCandidateProvider(["shui", "xiao", "mu"])]
        )
        decision = pipeline.analyze(image)
        self.assertIn(decision.status, {"matched", "ambiguous"})


if __name__ == "__main__":
    unittest.main()
