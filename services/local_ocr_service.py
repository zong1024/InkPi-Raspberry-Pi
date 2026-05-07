"""Local OCR service backed by the official PaddleOCR recognizer."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
from typing import Optional, Sequence

import cv2
import numpy as np
import requests

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
        self.remote_backend_url = str(os.environ.get("INKPI_CLOUD_BACKEND_URL", "")).rstrip("/")
        self.remote_device_key = str(os.environ.get("INKPI_CLOUD_DEVICE_KEY", "")).strip()
        self.remote_timeout = float(os.environ.get("INKPI_REMOTE_OCR_TIMEOUT", "4.0"))
        self.enable_tesseract_fallback = os.environ.get("INKPI_ENABLE_TESSERACT_FALLBACK", "0").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.tesseract_cmd = str(os.environ.get("INKPI_TESSERACT_CMD", "tesseract"))
        self.tesseract_language = str(os.environ.get("INKPI_TESSERACT_LANG", "chi_sim"))
        self.tesseract_psm_modes = self._parse_psm_modes(os.environ.get("INKPI_TESSERACT_PSM", "10,13,6"))
        self._ocr = None
        self._available = False
        self._tesseract_available = False
        self._infer_lock = threading.RLock()
        self._init_ocr()
        if self.enable_tesseract_fallback:
            self._init_tesseract()

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

    def _init_tesseract(self) -> None:
        if shutil.which(self.tesseract_cmd):
            self._tesseract_available = True
            return
        self.logger.info("Tesseract OCR command not found; tesseract fallback stays inactive.")
        self._tesseract_available = False

    @property
    def available(self) -> bool:
        return (self._available and self._ocr is not None) or (
            self.enable_tesseract_fallback and self._tesseract_available
        ) or self.remote_available

    @property
    def remote_available(self) -> bool:
        return bool(self.remote_backend_url) and bool(self.remote_device_key)

    def recognize(self, image: np.ndarray) -> Optional[OcrRecognition]:
        """Recognize the best single character from a preprocessed ROI."""

        if self._available and self._ocr is not None:
            recognition = self._recognize_local(image)
            if recognition is not None:
                return recognition

        if self.enable_tesseract_fallback and self._tesseract_available:
            recognition = self._recognize_tesseract(image)
            if recognition is not None:
                return recognition

        if self.remote_available:
            return self._recognize_remote(image)

        return None

    def _recognize_local(self, image: np.ndarray) -> Optional[OcrRecognition]:
        """Run the local OCR engine."""

        if not (self._available and self._ocr is not None):
            return None

        prepared = self._prepare_image(image)
        try:
            with self._infer_lock:
                result = self._run_ocr(prepared)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Local OCR inference failed: %s", exc)
            result = self._retry_after_failure(prepared)
            if result is None:
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

    def _recognize_remote(self, image: np.ndarray) -> Optional[OcrRecognition]:
        """Fallback to the server-side OCR endpoint for desktop testing environments."""

        try:
            ok, encoded = cv2.imencode(".jpg", image)
            if not ok:
                return None
            response = requests.post(
                f"{self.remote_backend_url}/api/device/ocr",
                headers={"X-Device-Key": self.remote_device_key},
                files={"image": ("ocr.jpg", encoded.tobytes(), "image/jpeg")},
                timeout=self.remote_timeout,
            )
            if response.status_code != 200:
                self.logger.warning("Remote OCR request failed: %s %s", response.status_code, response.text[:200])
                return None
            payload = response.json()
            if not payload.get("ok"):
                return None
            item = payload.get("item") or {}
            character = str(item.get("character", "")).strip()
            if not character:
                return None
            bbox = item.get("bbox")
            return OcrRecognition(
                character=character,
                confidence=float(item.get("confidence", 0.0) or 0.0),
                source=str(item.get("source", "remote-ocr")),
                bbox=tuple(float(x) for x in bbox) if isinstance(bbox, list) and len(bbox) == 4 else None,
            )
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Remote OCR request failed: %s", exc)
            return None

    def _recognize_tesseract(self, image: np.ndarray) -> Optional[OcrRecognition]:
        """Run a lightweight OCR fallback available from Raspberry Pi apt packages."""

        if not self._tesseract_available:
            return None

        prepared = self._prepare_image(image)
        best: dict | None = None
        for psm in self.tesseract_psm_modes:
            candidate = self._run_tesseract(prepared, psm=psm)
            if candidate and (best is None or candidate["confidence"] > best["confidence"]):
                best = candidate

        if not best:
            return None

        confidence = float(best["confidence"])
        if confidence < self.min_confidence:
            return None

        return OcrRecognition(
            character=str(best["character"]),
            confidence=confidence,
            source="tesseract",
            bbox=best.get("bbox"),
        )

    def _run_tesseract(self, image: np.ndarray, psm: int) -> dict | None:
        temp_path = ""
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
                temp_path = temp_file.name
            if not cv2.imwrite(temp_path, image):
                return None

            command = [
                self.tesseract_cmd,
                temp_path,
                "stdout",
                "-l",
                self.tesseract_language,
                "--psm",
                str(psm),
                "tsv",
            ]
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=float(os.environ.get("INKPI_TESSERACT_TIMEOUT", "6.0")),
            )
            if completed.returncode != 0:
                self.logger.warning("Tesseract OCR failed: %s", completed.stderr.strip()[:200])
                return None
            return self._parse_tesseract_tsv(completed.stdout, image.shape[:2])
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Tesseract OCR failed: %s", exc)
            return None
        finally:
            if temp_path:
                try:
                    Path(temp_path).unlink(missing_ok=True)
                except OSError:
                    pass

    def _parse_tesseract_tsv(self, tsv: str, shape: Sequence[int]) -> dict | None:
        lines = [line for line in tsv.splitlines() if line.strip()]
        if len(lines) < 2:
            return None

        height, width = int(shape[0]), int(shape[1])
        header = lines[0].split("\t")
        best: dict | None = None
        for line in lines[1:]:
            columns = line.split("\t")
            if len(columns) != len(header):
                continue
            row = dict(zip(header, columns))
            character = self._normalize_text(row.get("text", ""))
            if not character:
                continue
            try:
                confidence = float(row.get("conf", "0")) / 100.0
                left = float(row.get("left", "0"))
                top = float(row.get("top", "0"))
                box_width = float(row.get("width", "0"))
                box_height = float(row.get("height", "0"))
            except ValueError:
                continue
            if confidence < 0:
                continue
            bbox = (
                float(np.clip(left, 0, width)),
                float(np.clip(top, 0, height)),
                float(np.clip(left + box_width, 0, width)),
                float(np.clip(top + box_height, 0, height)),
            )
            item = {
                "character": character,
                "confidence": float(np.clip(confidence, 0.0, 1.0)),
                "bbox": bbox,
            }
            if best is None or item["confidence"] > best["confidence"]:
                best = item
        return best

    def _retry_after_failure(self, prepared: np.ndarray):
        try:
            with self._infer_lock:
                self._init_ocr()
                if not self.available:
                    return None
                return self._run_ocr(prepared)
        except Exception as retry_exc:  # noqa: BLE001
            self.logger.warning("Local OCR retry failed: %s", retry_exc)
            return None

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
            return text if self._looks_like_character(text) else None

        chinese_chars = [char for char in text if self._looks_like_character(char)]
        if len(chinese_chars) == 1:
            return chinese_chars[0]
        return None

    @staticmethod
    def _parse_psm_modes(value: str) -> list[int]:
        modes: list[int] = []
        for item in str(value or "").split(","):
            item = item.strip()
            if not item:
                continue
            try:
                modes.append(int(item))
            except ValueError:
                continue
        return modes or [10, 13, 6]

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
