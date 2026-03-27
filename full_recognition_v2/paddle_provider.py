"""PaddleOCR-backed candidate provider for the isolated full-recognition pipeline."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from pathlib import Path
from typing import List, Sequence

import cv2
import numpy as np

from full_recognition_v2.providers import CandidateProvider
from full_recognition_v2.types import RecognitionCandidate
from services.character_geometry_service import character_geometry_service
from services.template_manager import template_manager


@dataclass
class OcrDetection:
    """Flattened OCR detection used for downstream candidate scoring."""

    text: str
    score: float
    bbox: tuple[float, float, float, float]
    area_share: float
    center_distance: float
    source: str


class PaddleOcrCandidateProvider(CandidateProvider):
    """Large-vocabulary OCR provider that can feed top-k candidates into local reranking."""

    name = "paddleocr"

    def __init__(
        self,
        lang: str = "ch",
        device: str | None = None,
        model_dir: str | None = None,
        disable_model_source_check: bool = True,
    ) -> None:
        self.logger = logging.getLogger(__name__)
        self.lang = lang
        self.device = device or os.getenv("INKPI_FULL_OCR_DEVICE", "gpu:0")
        self.model_dir = Path(model_dir) if model_dir else None
        self.disable_model_source_check = disable_model_source_check
        self._ocr = None
        self._init_ocr()

    def _init_ocr(self) -> None:
        try:
            if self.disable_model_source_check:
                os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

            from paddleocr import PaddleOCR  # type: ignore

            kwargs = {
                "lang": self.lang,
                "device": self.device,
                "use_doc_orientation_classify": False,
                "use_doc_unwarping": False,
                "use_textline_orientation": False,
            }
            if self.model_dir:
                kwargs["text_recognition_model_dir"] = str(self.model_dir)

            self._ocr = PaddleOCR(**kwargs)
        except ImportError:
            self.logger.info("PaddleOCR is not installed; PaddleOcrCandidateProvider stays inactive.")
            self._ocr = None
        except TypeError:
            # Fall back to the older PaddleOCR constructor shape.
            try:
                from paddleocr import PaddleOCR  # type: ignore

                kwargs = {
                    "lang": self.lang,
                    "use_angle_cls": False,
                    "show_log": False,
                }
                if self.model_dir:
                    kwargs["rec_model_dir"] = str(self.model_dir)
                self._ocr = PaddleOCR(**kwargs)
            except Exception as exc:  # noqa: BLE001
                self.logger.warning("Failed to initialize legacy PaddleOCR: %s", exc)
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

        detections = self._collect_detections(image)
        if not detections:
            return []

        best_scores: dict[str, float] = {}
        for detection in detections:
            if len(detection.text) != 1:
                continue

            key = template_manager.resolve_character_key(detection.text)
            provider_score = self._score_detection(detection)
            if provider_score > best_scores.get(key, 0.0):
                best_scores[key] = provider_score

        ordered = sorted(best_scores.items(), key=lambda item: item[1], reverse=True)
        return [
            RecognitionCandidate(
                key=key,
                display=template_manager.to_display_character(key),
                provider_score=float(score),
                provider=self.name,
            )
            for key, score in ordered[:limit]
        ]

    def _collect_detections(self, image: np.ndarray) -> List[OcrDetection]:
        subject = character_geometry_service.extract_subject(image)
        variants: list[tuple[str, np.ndarray]] = [("full", image)]
        if subject is not None:
            variants.insert(0, ("roi", subject.binary))
        loose_roi = self._extract_loose_roi(image)
        if loose_roi is not None:
            variants.insert(0, ("ocr_roi", loose_roi))

        merged: List[OcrDetection] = []
        for source, variant in variants:
            prepared = self._prepare_image(variant)
            try:
                result = self._run_ocr(prepared)
            except Exception as exc:  # noqa: BLE001
                self.logger.warning("PaddleOCR inference failed on %s variant: %s", source, exc)
                continue
            merged.extend(self._parse_result(result, prepared.shape[:2], source))
        return merged

    def _run_ocr(self, prepared: np.ndarray):
        if hasattr(self._ocr, "predict"):
            return self._ocr.predict(prepared)
        return self._ocr.ocr(prepared, cls=False)

    def _parse_result(
        self,
        result,
        shape: Sequence[int],
        source: str,
    ) -> List[OcrDetection]:
        if not result:
            return []

        height, width = int(shape[0]), int(shape[1])
        if result and isinstance(result, list) and result[0] and isinstance(result[0], list) and len(result[0][0]) >= 2:
            return self._parse_legacy_result(result, width, height, source)

        parsed: List[OcrDetection] = []
        for page in result:
            payload = getattr(page, "json", None)
            if not isinstance(payload, dict):
                continue
            res = payload.get("res") or {}
            texts = res.get("rec_texts") or []
            scores = res.get("rec_scores") or []
            polys = res.get("dt_polys") or []
            for index, text in enumerate(texts):
                detection = self._build_detection(
                    text=text,
                    score=scores[index] if index < len(scores) else 0.0,
                    poly=polys[index] if index < len(polys) else None,
                    width=width,
                    height=height,
                    source=source,
                )
                if detection is not None:
                    parsed.append(detection)
        return parsed

    def _parse_legacy_result(self, result, width: int, height: int, source: str) -> List[OcrDetection]:
        parsed: List[OcrDetection] = []
        for line in result:
            if not isinstance(line, list):
                continue
            for item in line:
                if not item or len(item) < 2:
                    continue
                poly = item[0]
                text, score = item[1]
                detection = self._build_detection(text, score, poly, width, height, source)
                if detection is not None:
                    parsed.append(detection)
        return parsed

    def _build_detection(
        self,
        text,
        score,
        poly,
        width: int,
        height: int,
        source: str,
    ) -> OcrDetection | None:
        text = str(text or "").strip()
        if not text:
            return None

        score = float(score or 0.0)
        bbox = self._poly_to_bbox(poly, width, height)
        center_x = (bbox[0] + bbox[2]) / 2.0
        center_y = (bbox[1] + bbox[3]) / 2.0
        normalized_dx = (center_x - width / 2.0) / max(1.0, width / 2.0)
        normalized_dy = (center_y - height / 2.0) / max(1.0, height / 2.0)
        center_distance = float(np.hypot(normalized_dx, normalized_dy))
        area_share = max(0.0, min(1.0, ((bbox[2] - bbox[0]) * (bbox[3] - bbox[1])) / max(1.0, width * height)))
        return OcrDetection(
            text=text,
            score=score,
            bbox=bbox,
            area_share=area_share,
            center_distance=center_distance,
            source=source,
        )

    def _poly_to_bbox(self, poly, width: int, height: int) -> tuple[float, float, float, float]:
        if not poly:
            return (0.0, 0.0, float(width), float(height))
        points = np.asarray(poly, dtype=np.float32).reshape(-1, 2)
        x0 = float(np.clip(np.min(points[:, 0]), 0, width))
        y0 = float(np.clip(np.min(points[:, 1]), 0, height))
        x1 = float(np.clip(np.max(points[:, 0]), 0, width))
        y1 = float(np.clip(np.max(points[:, 1]), 0, height))
        if x1 <= x0 or y1 <= y0:
            return (0.0, 0.0, float(width), float(height))
        return (x0, y0, x1, y1)

    def _score_detection(self, detection: OcrDetection) -> float:
        # Large, centered, single-character detections are more likely to be the target.
        area_bonus = np.clip((detection.area_share - 0.015) / 0.20, 0.0, 1.0)
        center_bonus = np.clip(1.0 - detection.center_distance, 0.0, 1.0)
        source_bonus = {
            "full": 1.0,
            "roi": 1.12,
            "ocr_roi": 1.18,
        }.get(detection.source, 1.0)
        score = detection.score * source_bonus * (0.45 + area_bonus * 0.30 + center_bonus * 0.25)
        return float(np.clip(score, 0.0, 0.999))

    def _prepare_image(self, image: np.ndarray) -> np.ndarray:
        if len(image.shape) == 2:
            gray = image
        else:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        normalized = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
        target_w = max(320, normalized.shape[1])
        target_h = max(320, normalized.shape[0])
        resized = cv2.resize(normalized, (target_w, target_h), interpolation=cv2.INTER_CUBIC)
        return cv2.cvtColor(resized, cv2.COLOR_GRAY2BGR)

    def _extract_loose_roi(self, image: np.ndarray) -> np.ndarray | None:
        """Build a looser OCR crop so teaching-paper annotations do not dominate the OCR stage."""
        if len(image.shape) == 2:
            gray = image.copy()
        else:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        _, binary = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary, 8)
        if num_labels <= 1:
            return None

        height, width = binary.shape
        image_area = height * width
        center_x = width / 2.0
        center_y = height / 2.0
        best_label = None
        best_score = None

        for label in range(1, num_labels):
            x, y, box_w, box_h, area = stats[label]
            if area < max(120, int(image_area * 0.0018)):
                continue

            fill_ratio = area / max(1, box_w * box_h)
            if fill_ratio <= 0.05:
                continue

            comp_x, comp_y = centroids[label]
            center_distance = float(np.hypot(comp_x - center_x, comp_y - center_y))
            score = area - 0.55 * center_distance + 900.0 * fill_ratio
            if best_score is None or score > best_score:
                best_score = score
                best_label = label

        if best_label is None:
            return None

        x, y, box_w, box_h, _ = stats[best_label]
        pad = int(max(box_w, box_h) * 0.20) + 10
        x0 = max(0, x - pad)
        y0 = max(0, y - pad)
        x1 = min(width, x + box_w + pad)
        y1 = min(height, y + box_h + pad)
        crop = gray[y0:y1, x0:x1]
        if crop.size == 0:
            return None
        return crop
