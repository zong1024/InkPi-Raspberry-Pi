"""Unified recognition flow for character detection, recognition and style resolution."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.preprocessing_service import PreprocessingError
from services.recognition_service import recognition_service
from services.style_classification_service import style_classification_service
from services.template_manager import template_manager


@dataclass
class RecognitionFlowResult:
    character_name: Optional[str]
    recognition_confidence: float
    style: str
    style_confidence: Optional[float]
    candidates: List[Tuple[str, float]] = field(default_factory=list)
    style_probabilities: Dict[str, float] = field(default_factory=dict)
    recognition_source: str = ""


class RecognitionFlowService:
    """Single place to decide whether the image is evaluable and how to label it."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.default_style = "楷书"

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
        else:
            recognition_result = recognition_service.recognize(image)
            character_name = recognition_result.character or None
            recognition_confidence = recognition_result.confidence
            candidates = recognition_result.candidates
            recognition_source = recognition_result.source or ""

        if not character_name:
            raise PreprocessingError(
                "未检测到可评测的单个汉字，请重新对准作品后再试。",
                error_type="not_calligraphy",
            )

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
