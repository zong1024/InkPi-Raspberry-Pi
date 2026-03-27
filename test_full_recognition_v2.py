"""Smoke tests for the isolated next-gen recognition pipeline."""

from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

from full_recognition_v2.factory import build_default_full_pipeline
from full_recognition_v2.paddle_provider import PaddleOcrCandidateProvider
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

    def test_default_factory_builds_pipeline(self) -> None:
        pipeline = build_default_full_pipeline()
        self.assertIsNotNone(pipeline)

    def test_paddle_provider_prefers_large_single_character_detections(self) -> None:
        template_path = Path("C:/Users/zongrui/Documents/2/models/templates/shui_kaishu_standard.png")
        image = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
        self.assertIsNotNone(image)

        class FakePredictor:
            def __init__(self) -> None:
                self.calls = 0

            def predict(self, prepared):
                self.calls += 1
                if self.calls == 1:
                    return [
                        SimpleNamespace(
                            json={
                                "res": {
                                    "rec_texts": ["水", "行笔轻快"],
                                    "rec_scores": [0.95, 0.99],
                                    "dt_polys": [
                                        [[0, 0], [320, 0], [320, 320], [0, 320]],
                                        [[40, 250], [140, 250], [140, 290], [40, 290]],
                                    ],
                                }
                            }
                        )
                    ]
                return [
                    SimpleNamespace(
                        json={
                            "res": {
                                "rec_texts": ["小", "水"],
                                "rec_scores": [0.99, 0.92],
                                "dt_polys": [
                                    [[250, 8], [310, 8], [310, 52], [250, 52]],
                                    [[25, 45], [295, 45], [295, 265], [25, 265]],
                                ],
                            }
                        }
                    )
                ]

        provider = PaddleOcrCandidateProvider()
        provider._ocr = FakePredictor()
        candidates = provider.get_candidates(image, limit=3)

        self.assertGreaterEqual(len(candidates), 2)
        self.assertEqual(candidates[0].key, "shui")
        self.assertGreater(candidates[0].provider_score, candidates[1].provider_score)


if __name__ == "__main__":
    unittest.main()
