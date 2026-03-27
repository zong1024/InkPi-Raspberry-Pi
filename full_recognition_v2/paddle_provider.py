"""PaddleOCR-backed candidate provider for the isolated full-recognition pipeline."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

import cv2
import numpy as np

from full_recognition_v2.providers import CandidateProvider
from full_recognition_v2.types import RecognitionCandidate
from services.template_manager import template_manager


class PaddleOcrCandidateProvider(CandidateProvider):
    """Large-vocabulary OCR provider that can feed top-k candidates into local reranking."""

    name = "paddleocr"

    def __init__(
        self,
        lang: str = "ch",
        use_angle_cls: bool = False,
        model_dir: str | None = None,
    ) -> None:
        self.logger = logging.getLogger(__name__)
        self.lang = lang
        self.use_angle_cls = use_angle_cls
        self.model_dir = Path(model_dir) if model_dir else None
        self._ocr = None
        self._init_ocr()

    def _init_ocr(self) -> None:
        try:
            from paddleocr import PaddleOCR  # type: ignore

            kwargs = {
                "lang": self.lang,
                "use_angle_cls": self.use_angle_cls,
                "show_log": False,
            }
            if self.model_dir:
                kwargs["rec_model_dir"] = str(self.model_dir)
            self._ocr = PaddleOCR(**kwargs)
        except ImportError:
            self.logger.info("PaddleOCR is not installed; PaddleOcrCandidateProvider stays inactive.")
            self._ocr = None
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Failed to initialize PaddleOCR: %s", exc)
            self._ocr = None

    @property
    def available(self) -> bool:
        return self._ocr is not None

    def get_candidates(self, image, limit: int = 8) -> List[RecognitionCandidate]:
        if self._ocr is None:
            return []

        prepared = self._prepare_image(image)
        try:
            result = self._ocr.ocr(prepared, cls=self.use_angle_cls)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("PaddleOCR inference failed: %s", exc)
            return []

        if not result:
            return []

        merged: List[RecognitionCandidate] = []
        best_scores = {}

        # PaddleOCR returns line-level text; split to single-char candidates.
        for line in result:
            if not line:
                continue
            for item in line:
                if not item or len(item) < 2:
                    continue
                text, confidence = item[1]
                if not text:
                    continue

                text = str(text).strip()
                confidence = float(confidence)
                for char in text:
                    key = template_manager.resolve_character_key(char)
                    display = template_manager.to_display_character(key)
                    if len(display) != 1:
                        display = char
                    score = max(best_scores.get(key, 0.0), confidence)
                    best_scores[key] = score

        ordered = sorted(best_scores.items(), key=lambda pair: pair[1], reverse=True)
        for key, score in ordered[:limit]:
            merged.append(
                RecognitionCandidate(
                    key=key,
                    display=template_manager.to_display_character(key),
                    provider_score=float(score),
                    provider=self.name,
                )
            )
        return merged

    def _prepare_image(self, image: np.ndarray) -> np.ndarray:
        if len(image.shape) == 2:
            gray = image
        else:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # OCR prefers higher contrast and visible strokes.
        normalized = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
        resized = cv2.resize(normalized, (max(320, normalized.shape[1]), max(320, normalized.shape[0])), interpolation=cv2.INTER_CUBIC)
        return cv2.cvtColor(resized, cv2.COLOR_GRAY2BGR)
