"""Unified flow for character recognition, rejection and style resolution."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from full_recognition_v2.service import full_recognition_service
from services.preprocessing_service import PreprocessingError
from services.recognition_service import recognition_service
from services.style_classification_service import style_classification_service
from services.template_manager import template_manager


@dataclass
class RecognitionFlowResult:
    """Resolved recognition metadata consumed by evaluation."""

    character_name: Optional[str]
    recognition_confidence: float
    style: str
    style_confidence: Optional[float]
    candidates: List[Tuple[str, float]] = field(default_factory=list)
    style_probabilities: Dict[str, float] = field(default_factory=dict)
    recognition_source: str = ""
    status: str = "matched"
    template_ready: bool = True
    score_ready: bool = True
    next_action: str = "score"
    message: str = ""


class RecognitionFlowService:
    """Single entry point for character and style resolution before scoring."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.default_style = "楷书"

    def _supported_character_text(self) -> str:
        supported = [
            template_manager.to_display_character(char_key)
            for char_key in template_manager.list_available_chars()
        ]
        return "、".join(supported) if supported else "当前模板库为空"

    def analyze(
        self,
        image: np.ndarray,
        requested_character: Optional[str] = None,
        requested_style: Optional[str] = None,
    ) -> RecognitionFlowResult:
        """Resolve character and style for the current evaluation image."""
        if requested_character:
            character_name = template_manager.to_display_character(
                template_manager.resolve_character_key(requested_character)
            )
            recognition_confidence = 1.0
            candidates = [(character_name, 1.0)]
            recognition_source = "user"
            status = "matched"
            template_ready = True
            score_ready = True
            next_action = "score"
            message = f"已锁定评测字：{character_name}"
        else:
            recognition = self._recognize_character(image)
            character_name = recognition.character_name
            recognition_confidence = recognition.recognition_confidence
            candidates = recognition.candidates
            recognition_source = recognition.recognition_source
            status = recognition.status
            template_ready = recognition.template_ready
            score_ready = recognition.score_ready
            next_action = recognition.next_action
            message = recognition.message

        if requested_style:
            style = template_manager.to_display_style(template_manager.resolve_style_key(requested_style))
            style_confidence = 1.0
            style_probabilities = {style: 1.0}
        else:
            style, style_confidence, style_probabilities = style_classification_service.classify(
                image,
                character_hint=character_name,
            )
            if not style:
                style = self._fallback_style(character_name)
                style_confidence = 0.0
                style_probabilities = {style: 1.0}

        style = template_manager.to_display_style(template_manager.resolve_style_key(style))
        return RecognitionFlowResult(
            character_name=character_name,
            recognition_confidence=recognition_confidence,
            style=style,
            style_confidence=style_confidence,
            candidates=candidates,
            style_probabilities=style_probabilities,
            recognition_source=recognition_source,
            status=status,
            template_ready=template_ready,
            score_ready=score_ready,
            next_action=next_action,
            message=message,
        )

    def _recognize_character(self, image: np.ndarray) -> RecognitionFlowResult:
        """Run full-vocabulary recognition first, then fall back to the legacy matcher."""
        if full_recognition_service.is_candidate_ready:
            analysis = full_recognition_service.analyze(image)
            candidates = [
                (item.display, float(item.confidence))
                for item in analysis.candidates
            ]
            if analysis.status == "matched":
                return RecognitionFlowResult(
                    character_name=analysis.character_display,
                    recognition_confidence=analysis.confidence,
                    style=self.default_style,
                    style_confidence=None,
                    candidates=candidates,
                    recognition_source="full_v2",
                    status="matched",
                    template_ready=True,
                    score_ready=True,
                    next_action="score",
                    message=analysis.message,
                )

            if analysis.status == "untemplated":
                return RecognitionFlowResult(
                    character_name=analysis.character_display,
                    recognition_confidence=analysis.confidence,
                    style=self.default_style,
                    style_confidence=None,
                    candidates=candidates,
                    recognition_source="full_v2",
                    status="untemplated",
                    template_ready=False,
                    score_ready=False,
                    next_action="generic_score",
                    message=analysis.message or "已识别出字符，但当前将切换到通用评分。",
                )

            if analysis.status == "ambiguous":
                raise PreprocessingError(
                    "识别结果不稳定，当前字形与多个候选字过于接近，请重新拍摄或先锁定评测字。",
                    error_type="ambiguous_character",
                )

            if analysis.status == "rejected":
                raise PreprocessingError(
                    analysis.message or "未检测到稳定的单字主体，请重新对准作品后再试。",
                    error_type="not_calligraphy",
                )

            raise PreprocessingError(
                analysis.message or "全字识别暂未稳定，请调整取景后重试。",
                error_type="unsupported_character",
            )

        return self._recognize_with_legacy_matcher(image)

    def _recognize_with_legacy_matcher(self, image: np.ndarray) -> RecognitionFlowResult:
        """Fallback matcher kept for environments without full OCR candidates."""
        recognition_result = recognition_service.recognize(image)
        character_name = recognition_result.character or None
        candidates = recognition_result.candidates

        if recognition_result.status == "ambiguous":
            raise PreprocessingError(
                (
                    "识别结果不稳定，当前字形与多个内置评测字模板过于接近。"
                    f"当前模板评分支持：{self._supported_character_text()}。"
                    "建议先在首页手动锁定评测字后再拍摄。"
                ),
                error_type="ambiguous_character",
            )

        if recognition_result.status == "unsupported":
            raise PreprocessingError(
                (
                    "当前作品像毛笔字，但仅靠本地模板仍无法稳定识别。"
                    "如果想评测任意汉字，请开启全字识别候选源或先手动指定评测字。"
                ),
                error_type="unsupported_character",
            )

        if recognition_result.status in {"rejected", "missing_templates"} or not character_name:
            raise PreprocessingError(
                recognition_result.reason or "未检测到可评测的单个汉字，请重新对准作品后再试。",
                error_type="not_calligraphy",
            )

        return RecognitionFlowResult(
            character_name=character_name,
            recognition_confidence=recognition_result.confidence,
            style=self.default_style,
            style_confidence=None,
            candidates=candidates,
            recognition_source=recognition_result.source or "legacy",
            status="matched",
            template_ready=True,
            score_ready=True,
            next_action="score",
            message="已使用本地模板匹配完成识别。",
        )

    def _fallback_style(self, character_name: Optional[str]) -> str:
        if character_name:
            templates = template_manager.iter_character_templates(character_name)
            if templates:
                return template_manager.to_display_style(templates[0]["style"])

        all_styles = template_manager.list_all_styles()
        if all_styles:
            return template_manager.to_display_style(all_styles[0])
        return self.default_style


recognition_flow_service = RecognitionFlowService()
