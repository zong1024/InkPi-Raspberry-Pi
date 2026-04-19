"""Single-chain evaluation service: OCR -> script-routed ONNX -> source-backed rubric."""

from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.evaluation_framework import get_script_label, normalize_script
from models.evaluation_result import EvaluationResult
from services.dimension_scorer_service import dimension_scorer_service
from services.local_ocr_service import local_ocr_service
from services.operations_monitor_service import operations_monitor_service
from services.preprocessing_service import PreprocessingError
from services.quality_scorer_service import quality_scorer_service


class EvaluationService:
    """Dual-script scoring service with stable user-facing feedback."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.feedback_templates = {
            "good": [
                "当前主分稳定，说明这张作品已经具备较好的阶段性展示质量。",
                "整体完成度较高，继续按新五维标准巩固弱项会更稳。",
                "本轮结果适合作为后续训练时的对照样张。",
            ],
            "medium": [
                "当前基础已经成形，接下来更适合按正式标准逐项补强。",
                "主分和识别都较稳定，继续围绕最弱 rubric 项训练会更有效。",
                "这条记录适合拿来做下一轮定向修正的基线。",
            ],
            "bad": [
                "当前作品波动较大，建议先把主体完整性和规范性稳住。",
                "这轮主分偏低，更适合先按正式标准回正基础项。",
                "建议重新书写或重新拍摄后再进行下一轮对照。",
            ],
        }
        self.quality_labels = {"good": "甲", "medium": "乙", "bad": "待提升"}

    def evaluate(
        self,
        processed_image: np.ndarray,
        *,
        script: str | None,
        original_image_path: str | None = None,
        processed_image_path: str | None = None,
        ocr_image: np.ndarray | None = None,
    ) -> EvaluationResult:
        """Run the OCR + script-specific ONNX scoring pipeline."""

        if not script:
            raise ValueError("script_required")
        normalized_script = normalize_script(script)
        if normalized_script not in {"regular", "running"}:
            raise ValueError("unsupported_script")

        script_label = get_script_label(normalized_script)
        self.logger.info("Starting dual-script calligraphy evaluation for %s.", normalized_script)
        operations_monitor_service.record_pipeline(
            "evaluation",
            "running",
            "Evaluation pipeline started.",
            {"script": normalized_script, "script_label": script_label},
        )

        if not local_ocr_service.available:
            operations_monitor_service.record_pipeline(
                "ocr",
                "error",
                "OCR service is unavailable.",
                {
                    "local_ready": bool(getattr(local_ocr_service, "_available", False)),
                    "remote_ready": bool(local_ocr_service.remote_available),
                },
            )
            raise RuntimeError("Local OCR is unavailable. Install PaddleOCR or configure the remote OCR fallback.")

        if not quality_scorer_service.is_script_available(normalized_script):
            model_path = quality_scorer_service.get_model_path(normalized_script)
            operations_monitor_service.record_pipeline(
                "quality_model",
                "error",
                "Quality scoring model is unavailable.",
                {
                    "script": normalized_script,
                    "script_label": script_label,
                    "model_path": str(model_path),
                },
            )
            raise RuntimeError(f"script_model_unavailable:{normalized_script}:{model_path}")

        recognition_source = ocr_image if ocr_image is not None else processed_image
        operations_monitor_service.record_pipeline("ocr", "running", "Recognizing character from ROI.")
        recognition = local_ocr_service.recognize(recognition_source)
        if recognition is None:
            operations_monitor_service.record_pipeline("ocr", "error", "OCR could not lock onto a single character.")
            raise PreprocessingError(
                "未能稳定识别当前单字，请重新对准作品后再试。",
                error_type="ocr_failed",
            )
        operations_monitor_service.record_pipeline(
            "ocr",
            "done",
            "OCR recognition completed.",
            {
                "character": recognition.character,
                "confidence": round(float(recognition.confidence), 4),
                "source": recognition.source,
            },
        )

        operations_monitor_service.record_pipeline(
            "quality_model",
            "running",
            "Running script-specific ONNX quality scorer.",
            {"script": normalized_script, "script_label": script_label},
        )
        scored = quality_scorer_service.score(
            processed_image,
            character=recognition.character,
            script=normalized_script,
            ocr_confidence=recognition.confidence,
        )
        operations_monitor_service.record_pipeline(
            "quality_model",
            "done",
            "Primary score generated.",
            {
                "script": normalized_script,
                "script_label": script_label,
                "total_score": scored.total_score,
                "quality_level": scored.quality_level,
                "quality_confidence": round(float(scored.quality_confidence), 4),
            },
        )

        operations_monitor_service.record_pipeline(
            "rubric_scoring",
            "running",
            "Computing source-backed rubric items.",
            {"script": normalized_script},
        )
        rubric_result = dimension_scorer_service.score(
            processed_image,
            probabilities=scored.probabilities,
            quality_features=scored.quality_features or {},
            calibration=scored.calibration or {},
            ocr_confidence=recognition.confidence,
            script=normalized_script,
        )
        operations_monitor_service.record_pipeline(
            "rubric_scoring",
            "done",
            "Source-backed rubric scoring completed.",
            {
                "script": normalized_script,
                "rubric_family": rubric_result.rubric_family,
                "rubric_scores": rubric_result.rubric_scores,
            },
        )

        result = EvaluationResult.from_rubric_scores(
            total_score=scored.total_score,
            feedback=self._build_feedback(
                scored.quality_level,
                scored.total_score,
                recognition.character,
                normalized_script,
            ),
            timestamp=datetime.now(),
            script=normalized_script,
            image_path=original_image_path,
            processed_image_path=processed_image_path,
            character_name=recognition.character,
            ocr_confidence=recognition.confidence,
            quality_level=scored.quality_level,
            quality_confidence=scored.quality_confidence,
            rubric_family=rubric_result.rubric_family,
            rubric_scores=rubric_result.rubric_scores,
            score_debug={
                "probabilities": scored.probabilities,
                "quality_features": scored.quality_features or {},
                "geometry_features": rubric_result.geometry_features,
                "calibration": scored.calibration or {},
                "rubric_family": rubric_result.rubric_family,
                "rubric_preview_total": rubric_result.rubric_preview_total,
                "script": normalized_script,
                "script_label": script_label,
            },
        )
        self.logger.info(
            "Dual-script evaluation finished: char=%s script=%s score=%s level=%s rubric=%s ocr=%.3f",
            result.character_name,
            normalized_script,
            result.total_score,
            result.quality_level,
            result.get_rubric_family(),
            result.ocr_confidence or 0.0,
        )
        operations_monitor_service.record_pipeline(
            "evaluation",
            "done",
            "Evaluation pipeline completed.",
            {
                "script": normalized_script,
                "script_label": script_label,
                "character": result.character_name,
                "total_score": result.total_score,
                "quality_level": result.quality_level,
                "rubric_family": result.get_rubric_family(),
            },
        )
        return result

    def _build_feedback(
        self,
        quality_level: str,
        total_score: int,
        character_name: str | None,
        script: str,
    ) -> str:
        feedback_pool = self.feedback_templates.get(quality_level) or self.feedback_templates["medium"]
        base_feedback = feedback_pool[total_score % len(feedback_pool)]
        label = self.quality_labels.get(quality_level, "乙")
        script_label = get_script_label(script)
        if character_name:
            return (
                f"识别字为“{character_name}”，当前按 {script_label} 模型生成主分，"
                f"等级为“{label}”。{base_feedback}"
            )
        return base_feedback


evaluation_service = EvaluationService()
