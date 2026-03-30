"""Single-chain evaluation service: preprocess -> local OCR -> ONNX quality scoring."""

from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import EVALUATION_CONFIG, QUALITY_SCORER_CONFIG
from models.evaluation_result import EvaluationResult
from services.local_ocr_service import local_ocr_service
from services.preprocessing_service import PreprocessingError
from services.quality_scorer_service import quality_scorer_service


class EvaluationService:
    """Single-chain scoring service with no templates or dual score modes."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.config = EVALUATION_CONFIG
        self.feedback_templates = {
            "good": [
                "整体完成度很高，已经接近比赛展示时可直接使用的状态。",
                "当前字形稳定、识别清晰，适合直接进入展示或归档。",
                "这张作品表现优秀，可以作为当前阶段的优先展示样例。",
            ],
            "medium": [
                "整体已经比较稳定，但还有进一步打磨细节的空间。",
                "识别和评分都较稳定，建议继续提升笔势和整体完成度。",
                "这张作品基础不错，再收一收结构和笔意会更稳。",
            ],
            "bad": [
                "当前作品完成度偏弱，建议重新书写或重新拍摄后再试。",
                "自动识别已经完成，但评分显示这张作品还不够稳定。",
                "这张作品基础质量偏低，建议先调整字形和用笔后再测。",
            ],
        }
        self.quality_labels = {"good": "好", "medium": "中", "bad": "坏"}
        self.scorer_feedback = {
            "good": "自动识别显示这张作品整体完成度很高，适合直接进入展示或归档。",
            "medium": "自动识别显示这张作品已经比较稳定，但仍有继续打磨空间。",
            "bad": "自动识别显示这张作品质量偏弱，建议重新书写或重新拍摄后再试。",
        }

    def evaluate(
        self,
        processed_image: np.ndarray,
        original_image_path: str | None = None,
        processed_image_path: str | None = None,
        ocr_image: np.ndarray | None = None,
    ) -> EvaluationResult:
        """Run the new OCR + ONNX scoring pipeline."""

        self.logger.info("Starting single-chain calligraphy evaluation...")

        if not local_ocr_service.available:
            raise RuntimeError("Local OCR model is unavailable. Please install PaddleOCR on this device.")
        if not quality_scorer_service.available:
            raise RuntimeError(
                f"Quality scorer ONNX is unavailable: {quality_scorer_service.model_path}"
            )

        recognition_source = ocr_image if ocr_image is not None else processed_image
        recognition = local_ocr_service.recognize(recognition_source)
        if recognition is None:
            raise PreprocessingError(
                "未能稳定识别当前汉字，请重新对准单字作品后再试。",
                error_type="ocr_failed",
            )

        scored = quality_scorer_service.score(
            processed_image,
            character=recognition.character,
            ocr_confidence=recognition.confidence,
        )
        feedback = self._build_feedback(scored.quality_level, scored.total_score, recognition.character)

        result = EvaluationResult(
            total_score=scored.total_score,
            feedback=feedback,
            timestamp=datetime.now(),
            image_path=original_image_path,
            processed_image_path=processed_image_path,
            character_name=recognition.character,
            ocr_confidence=recognition.confidence,
            quality_level=scored.quality_level,
            quality_confidence=scored.quality_confidence,
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
        if isinstance(feedback_pool, list) and feedback_pool:
            base_feedback = feedback_pool[total_score % len(feedback_pool)]
        else:
            base_feedback = self.scorer_feedback.get(quality_level) or self.scorer_feedback.get("medium", "")

        label = self.quality_labels.get(quality_level, "中")
        if character_name:
            return f"自动识别为“{character_name}”，当前评测等级为“{label}”。{base_feedback}"
        return base_feedback


evaluation_service = EvaluationService()
