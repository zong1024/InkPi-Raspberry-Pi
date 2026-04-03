"""Single-chain evaluation service: preprocess -> local OCR -> ONNX quality scoring."""

from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.evaluation_result import EvaluationResult
from services.dimension_scorer_service import dimension_scorer_service
from services.local_ocr_service import local_ocr_service
from services.preprocessing_service import PreprocessingError
from services.quality_scorer_service import quality_scorer_service


class EvaluationService:
    """Single-chain scoring service with no templates or dual score modes."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.feedback_templates = {
            "good": [
                "书写稳定，结构端正，已经接近可以直接展示的状态。",
                "整体完成度很高，线条和重心都比较稳。",
                "当前作品表现优秀，适合作为阶段性展示样例。",
            ],
            "medium": [
                "整体基础不错，但还有继续收紧结构和笔势的空间。",
                "识别和评分都比较稳定，适合继续打磨细节。",
                "当前字形已经成型，再加强完整度会更好。",
            ],
            "bad": [
                "当前作品波动较大，建议重新书写或重新拍摄后再试。",
                "这次评测显示基础质量偏弱，建议先调整结构再测。",
                "主体已经识别出来，但完成度还不够稳定。",
            ],
        }
        self.quality_labels = {"good": "甲", "medium": "乙", "bad": "丙"}

    def evaluate(
        self,
        processed_image: np.ndarray,
        original_image_path: str | None = None,
        processed_image_path: str | None = None,
        ocr_image: np.ndarray | None = None,
    ) -> EvaluationResult:
        """Run the OCR + ONNX scoring pipeline."""

        self.logger.info("Starting single-chain calligraphy evaluation...")

        if not local_ocr_service.available:
            raise RuntimeError("Local OCR model is unavailable. Please install PaddleOCR or use desktop simulator mode.")
        if not quality_scorer_service.available:
            raise RuntimeError(f"Quality scorer ONNX is unavailable: {quality_scorer_service.model_path}")

        recognition_source = ocr_image if ocr_image is not None else processed_image
        recognition = local_ocr_service.recognize(recognition_source)
        if recognition is None:
            raise PreprocessingError(
                "未能稳定识别当前单字，请重新对准作品后再试。",
                error_type="ocr_failed",
            )

        scored = quality_scorer_service.score(
            processed_image,
            character=recognition.character,
            ocr_confidence=recognition.confidence,
        )
        dimension_result = dimension_scorer_service.score(
            processed_image,
            probabilities=scored.probabilities,
            quality_features=scored.quality_features or {},
            calibration=scored.calibration or {},
            ocr_confidence=recognition.confidence,
        )

        result = EvaluationResult(
            total_score=scored.total_score,
            feedback=self._build_feedback(scored.quality_level, scored.total_score, recognition.character),
            timestamp=datetime.now(),
            image_path=original_image_path,
            processed_image_path=processed_image_path,
            character_name=recognition.character,
            ocr_confidence=recognition.confidence,
            quality_level=scored.quality_level,
            quality_confidence=scored.quality_confidence,
            dimension_scores=dimension_result.dimension_scores,
            score_debug={
                "probabilities": scored.probabilities,
                "quality_features": scored.quality_features or {},
                "geometry_features": dimension_result.geometry_features,
                "calibration": scored.calibration or {},
            },
        )
        self.logger.info(
            "Single-chain evaluation finished: char=%s score=%s level=%s ocr=%.3f",
            result.character_name,
            result.total_score,
            result.quality_level,
            result.ocr_confidence or 0.0,
        )
        return result

    def _build_feedback(self, quality_level: str, total_score: int, character_name: str | None) -> str:
        feedback_pool = self.feedback_templates.get(quality_level) or self.feedback_templates["medium"]
        base_feedback = feedback_pool[total_score % len(feedback_pool)]
        label = self.quality_labels.get(quality_level, "乙")
        if character_name:
            return f"识别字为“{character_name}”，当前评测等级为“{label}”。{base_feedback}"
        return base_feedback


evaluation_service = EvaluationService()
