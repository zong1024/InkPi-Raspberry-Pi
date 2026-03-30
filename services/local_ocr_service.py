"""Local OCR service backed by the official PaddleOCR recognizer."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from pathlib import Path
import threading
from typing import Optional, Sequence

import cv2
import numpy as np

from config import OCR_CONFIG


@dataclass
class OcrRecognition:
    """Best single-character OCR result."""

    character: str
    confidence: float
    source: str = "paddleocr"
    bbox: tuple[float, float, float, float] | None = None


class LocalOcrService:
    """Run a local official OCR model and keep only the most likely single character."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.config = OCR_CONFIG
        self.min_confidence = float(self.config.get("min_confidence", 0.32))
        self.device = str(self.config.get("device", "cpu"))
        self.language = str(self.config.get("language", "ch"))
        self._ocr = None
        self._available = False
        self._infer_lock = threading.RLock()
        self._init_ocr()

    def _init_ocr(self) -> None:
        try:
            if self.config.get("warmup", True):
                os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

            from paddleocr import PaddleOCR  # type: ignore

            kwargs = {
                "lang": self.language,
                "device": self.device,
                "use_doc_orientation_classify": False,
                "use_doc_unwarping": False,
                "use_textline_orientation": False,
            }
            self._ocr = PaddleOCR(**kwargs)
            self._available = True
        except ImportError:
            self.logger.info("PaddleOCR not installed; local OCR service stays inactive.")
            self._ocr = None
            self._available = False
        except TypeError:
            try:
                from paddleocr import PaddleOCR  # type: ignore

                self._ocr = PaddleOCR(lang=self.language, use_angle_cls=False, show_log=False)
                self._available = True
            except Exception as exc:  # noqa: BLE001
                self.logger.warning("Failed to initialize legacy PaddleOCR: %s", exc)
                self._ocr = None
                self._available = False
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Failed to initialize local OCR: %s", exc)
            self._ocr = None
            self._available = False

    @property
    def available(self) -> bool:
        return self._available and self._ocr is not None

    def recognize(self, image: np.ndarray) -> Optional[OcrRecognition]:
        """Recognize the best single character from a preprocessed ROI."""

        if not self.available:
            return None

        prepared = self._prepare_image(image)
        try:
            with self._infer_lock:
                result = self._run_ocr(prepared)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Local OCR inference failed: %s", exc)
            return None

        detections = self._parse_result(result, prepared.shape[:2])
        if not detections:
            return None

        best = max(detections, key=lambda item: item["rank_score"])
        if best["confidence"] < self.min_confidence:
            return None

        return OcrRecognition(
            character=best["character"],
            confidence=float(best["confidence"]),
            bbox=best.get("bbox"),
        )

    def _run_ocr(self, prepared: np.ndarray):
        if hasattr(self._ocr, "predict"):
            return self._ocr.predict(prepared)
        return self._ocr.ocr(prepared, cls=False)

    def _prepare_image(self, image: np.ndarray) -> np.ndarray:
        if image is None:
            raise ValueError("image is required")

        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        normalized = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
        if float(np.mean(normalized)) < 127:
            normalized = 255 - normalized

        h, w = normalized.shape[:2]
        canvas_size = max(320, h, w)
        canvas = np.full((canvas_size, canvas_size), 255, dtype=np.uint8)
        y = (canvas_size - h) // 2
        x = (canvas_size - w) // 2
        canvas[y : y + h, x : x + w] = normalized
        canvas = cv2.resize(canvas, (max(320, canvas_size), max(320, canvas_size)), interpolation=cv2.INTER_CUBIC)
        return cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)

    def _parse_result(self, result, shape: Sequence[int]) -> list[dict]:
        if not result:
            return []

        height, width = int(shape[0]), int(shape[1])
        parsed: list[dict] = []

        # PaddleOCR 3.x payload
        if result and not (isinstance(result[0], list) and result[0] and isinstance(result[0][0], list)):
            for page in result:
                payload = getattr(page, "json", None)
                if not isinstance(payload, dict):
                    continue
                res = payload.get("res") or {}
                texts = res.get("rec_texts") or []
                scores = res.get("rec_scores") or []
                polys = res.get("dt_polys") or []
                for index, text in enumerate(texts):
                    item = self._build_candidate(
                        text=text,
                        score=scores[index] if index < len(scores) else 0.0,
                        poly=polys[index] if index < len(polys) else None,
                        width=width,
                        height=height,
                    )
                    if item:
                        parsed.append(item)
            return parsed

        # PaddleOCR 2.x payload
        for line in result:
            if not isinstance(line, list):
                continue
            for item in line:
                if not item or len(item) < 2:
                    continue
                poly = item[0]
                text, score = item[1]
                candidate = self._build_candidate(text, score, poly, width=width, height=height)
                if candidate:
                    parsed.append(candidate)
        return parsed

    def _build_candidate(
        self,
        text,
        score,
        poly,
        width: int,
        height: int,
    ) -> dict | None:
        character = self._normalize_text(text)
        if not character:
            return None

        confidence = float(score or 0.0)
        bbox = self._poly_to_bbox(poly, width, height)
        center_x = (bbox[0] + bbox[2]) / 2.0
        center_y = (bbox[1] + bbox[3]) / 2.0
        normalized_dx = (center_x - width / 2.0) / max(1.0, width / 2.0)
        normalized_dy = (center_y - height / 2.0) / max(1.0, height / 2.0)
        center_distance = float(np.hypot(normalized_dx, normalized_dy))
        area_share = max(
            0.0,
            min(1.0, ((bbox[2] - bbox[0]) * (bbox[3] - bbox[1])) / max(1.0, width * height)),
        )
        rank_score = confidence * (0.55 + np.clip(area_share / 0.28, 0.0, 1.0) * 0.25 + (1.0 - center_distance) * 0.20)
        return {
            "character": character,
            "confidence": confidence,
            "bbox": bbox,
            "rank_score": float(rank_score),
        }

    def _normalize_text(self, text) -> str | None:
        text = str(text or "").strip()
        if not text:
            return None
        if len(text) == 1:
            return text

        chinese_chars = [char for char in text if self._looks_like_character(char)]
        if len(chinese_chars) == 1:
            return chinese_chars[0]
        return None

    @staticmethod
    def _looks_like_character(char: str) -> bool:
        code = ord(char)
        return 0x4E00 <= code <= 0x9FFF or 0x3400 <= code <= 0x4DBF

    @staticmethod
    def _poly_to_bbox(poly, width: int, height: int) -> tuple[float, float, float, float]:
        if poly is None:
            return (0.0, 0.0, float(width), float(height))
        points = np.asarray(poly, dtype=np.float32).reshape(-1, 2)
        x0 = float(np.clip(np.min(points[:, 0]), 0, width))
        y0 = float(np.clip(np.min(points[:, 1]), 0, height))
        x1 = float(np.clip(np.max(points[:, 0]), 0, width))
        y1 = float(np.clip(np.max(points[:, 1]), 0, height))
        if x1 <= x0 or y1 <= y0:
            return (0.0, 0.0, float(width), float(height))
        return (x0, y0, x1, y1)


local_ocr_service = LocalOcrService()
