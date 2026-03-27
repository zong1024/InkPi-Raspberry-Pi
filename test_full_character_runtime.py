"""Regression tests for the all-character runtime flow."""

from __future__ import annotations

import unittest
from pathlib import Path

import cv2

import services.recognition_flow_service as recognition_flow_module
from full_recognition_v2.service import FullRecognitionAnalysis, FullRecognitionCandidateView
from services.evaluation_service import evaluation_service


class _StubFullRecognitionService:
    @property
    def is_candidate_ready(self) -> bool:
        return True

    def analyze(self, image, limit: int = 8):
        del image, limit
        return FullRecognitionAnalysis(
            status="untemplated",
            character_key="shen",
            character_display="神",
            confidence=0.91,
            score_ready=False,
            template_ready=False,
            title="已识别为 神",
            message="已识别为 神，当前字暂无本地模板，已切换到通用评分。",
            next_action="generic_score",
            candidates=[
                FullRecognitionCandidateView(
                    key="shen",
                    display="神",
                    confidence=0.91,
                    source="remote_ocr",
                )
            ],
        )


class FullCharacterRuntimeTests(unittest.TestCase):
    def test_untemplated_character_uses_generic_scoring(self) -> None:
        template_path = Path(__file__).resolve().parent / "models" / "templates" / "shen_kaishu_standard.png"
        image = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
        self.assertIsNotNone(image)

        original_service = recognition_flow_module.full_recognition_service
        recognition_flow_module.full_recognition_service = _StubFullRecognitionService()
        try:
            result = evaluation_service.evaluate(image, enable_recognition=True)
        finally:
            recognition_flow_module.full_recognition_service = original_service

        self.assertEqual(result.character_name, "神")
        self.assertEqual(result.recognition_status, "untemplated")
        self.assertEqual(result.score_mode, "generic")
        self.assertIn("通用评分", result.feedback)
        self.assertGreaterEqual(result.total_score, 0)


if __name__ == "__main__":
    unittest.main()
