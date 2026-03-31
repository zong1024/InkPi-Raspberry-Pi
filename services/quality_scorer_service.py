"""Single-image ONNX quality scorer for InkPi."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path

import cv2
import numpy as np
try:
    import onnxruntime as ort
    _ORT_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # noqa: BLE001
    ort = None  # type: ignore[assignment]
    _ORT_IMPORT_ERROR = exc

from config import QUALITY_SCORER_CONFIG


@dataclass
class QualityScore:
    """Scoring output returned by the ONNX quality model."""

    total_score: int
    quality_level: str
    quality_confidence: float
    probabilities: dict[str, float]


class QualityScorerService:
    """Load and run the new single-chain ONNX scoring model."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.config = QUALITY_SCORER_CONFIG
        self.model_path = Path(self.config["onnx_path"])
        self.input_size = int(self.config.get("input_size", 32))
        self.labels = list(self.config.get("labels", ["bad", "medium", "good"]))
        self.score_scale = float(self.config.get("score_scale", 100.0))
        self.default_level = str(self.config.get("default_level", "medium"))
        self._session = None
        self._input_names: list[str] = []
        self._input_shapes: dict[str, list[int | str | None]] = {}
        self._output_names: list[str] = []
        self._load_session()

    def _load_session(self) -> None:
        if ort is None:
            self.logger.warning("onnxruntime is unavailable on this device: %s", _ORT_IMPORT_ERROR)
            return
        if not self.model_path.exists():
            self.logger.warning("Quality scorer model is missing: %s", self.model_path)
            return

        options = ort.SessionOptions()
        options.intra_op_num_threads = int(self.config.get("num_threads", 2))
        options.inter_op_num_threads = 1
        try:
            self._session = ort.InferenceSession(
                str(self.model_path),
                sess_options=options,
                providers=["CPUExecutionProvider"],
            )
            self._input_names = [item.name for item in self._session.get_inputs()]
            self._input_shapes = {item.name: list(item.shape) for item in self._session.get_inputs()}
            self._output_names = [item.name for item in self._session.get_outputs()]
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Failed to load quality scorer ONNX: %s", exc)
            self._session = None
            self._input_names = []
            self._input_shapes = {}
            self._output_names = []

    @property
    def available(self) -> bool:
        return self._session is not None

    def score(self, image: np.ndarray, character: str, ocr_confidence: float | None = None) -> QualityScore:
        """Run the ONNX scorer and return a stable total score and level."""

        if not self.available or self._session is None:
            raise RuntimeError(f"Quality scorer ONNX model missing: {self.model_path}")

        roi = self._prepare_image(image)
        char_code = np.asarray([[self._encode_character(character)]], dtype=np.float32)
        ocr_conf = np.asarray([[float(ocr_confidence or 0.0)]], dtype=np.float32)

        feed = self._build_feed(image, roi, char_code, ocr_conf)

        outputs = self._session.run(None, feed)
        by_name = dict(zip(self._output_names, outputs))

        raw_score = None
        probabilities = None
        logits = None
        for name, value in by_name.items():
            lowered = name.lower()
            if lowered in {"score", "score_value", "total_score"}:
                raw_score = np.asarray(value, dtype=np.float32).reshape(-1)[0]
            elif lowered in {"quality_probs", "probabilities", "quality_probabilities"}:
                probabilities = np.asarray(value, dtype=np.float32).reshape(-1)
            elif lowered in {"quality_logits", "logits"}:
                logits = np.asarray(value, dtype=np.float32).reshape(-1)

        if probabilities is None and logits is not None:
            probabilities = self._softmax(logits)

        if probabilities is None:
            probabilities = np.asarray([0.2, 0.6, 0.2], dtype=np.float32)

        probabilities = probabilities[: len(self.labels)]
        if probabilities.sum() <= 0:
            probabilities = np.asarray([0.2, 0.6, 0.2], dtype=np.float32)
        probabilities = probabilities / probabilities.sum()

        best_index = int(np.argmax(probabilities))
        quality_level = self.labels[best_index] if best_index < len(self.labels) else self.default_level
        extras = self._extract_quality_features(image).reshape(-1)

        if raw_score is None:
            total_score = self._calibrate_total_score(
                probabilities=probabilities,
                quality_level=quality_level,
                extras=extras,
                ocr_confidence=float(ocr_confidence or 0.0),
            )
        elif raw_score <= 1.0:
            calibrated = self._calibrate_total_score(
                probabilities=probabilities,
                quality_level=quality_level,
                extras=extras,
                ocr_confidence=float(ocr_confidence or 0.0),
            )
            total_score = int(np.clip(round((raw_score * self.score_scale) * 0.35 + calibrated * 0.65), 0, 100))
        else:
            total_score = int(np.clip(round(raw_score), 0, 100))

        return QualityScore(
            total_score=total_score,
            quality_level=quality_level,
            quality_confidence=float(probabilities[best_index]),
            probabilities={
                label: float(probabilities[index]) for index, label in enumerate(self.labels[: len(probabilities)])
            },
        )

    def _build_feed(
        self,
        image: np.ndarray,
        roi: np.ndarray,
        char_code: np.ndarray,
        ocr_conf: np.ndarray,
    ) -> dict[str, np.ndarray]:
        if len(self._input_names) == 1:
            name = self._input_names[0]
            shape = self._input_shapes.get(name, [])
            if len(shape) == 2:
                flat = roi.reshape(1, -1)
                extras = self._extract_quality_features(image)
                feature_width = shape[1] if len(shape) > 1 and isinstance(shape[1], int) else None
                features = [flat]
                current_width = flat.shape[1]
                if feature_width is None or feature_width >= current_width + char_code.shape[1]:
                    features.append(char_code)
                    current_width += char_code.shape[1]
                if feature_width is None or feature_width >= current_width + extras.shape[1]:
                    features.append(extras)
                    current_width += extras.shape[1]
                if feature_width is None or feature_width >= current_width + ocr_conf.shape[1]:
                    features.append(ocr_conf)
                return {name: np.concatenate(features, axis=1).astype(np.float32)}

        feed = {}
        for name in self._input_names:
            lowered = name.lower()
            if lowered in {"roi", "image", "input", "input_image"}:
                feed[name] = roi
            elif lowered in {"char_code", "character", "character_id", "char_id"}:
                feed[name] = char_code
            elif lowered in {"ocr_confidence", "ocr_conf", "confidence"}:
                feed[name] = ocr_conf
        return feed

    def _prepare_image(self, image: np.ndarray) -> np.ndarray:
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        resized = cv2.resize(gray, (self.input_size, self.input_size), interpolation=cv2.INTER_AREA)
        normalized = resized.astype(np.float32) / 255.0
        return normalized[np.newaxis, np.newaxis, :, :]

    def _extract_quality_features(self, image: np.ndarray) -> np.ndarray:
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        resized = cv2.resize(gray, (self.input_size, self.input_size), interpolation=cv2.INTER_AREA)
        normalized = cv2.normalize(resized, None, 0, 255, cv2.NORM_MINMAX)
        if float(np.mean(normalized)) < 127:
            normalized = 255 - normalized

        _, binary = cv2.threshold(normalized, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        points = cv2.findNonZero(binary)
        h_img, w_img = binary.shape
        if points is None:
            return np.zeros((1, 6), dtype=np.float32)

        x, y, w, h = cv2.boundingRect(points)
        bbox_area = max(1.0, float(w * h))
        image_area = max(1.0, float(h_img * w_img))
        fg_ratio = float(np.mean(binary > 0))
        bbox_ratio = bbox_area / image_area

        moments = cv2.moments(binary)
        if moments["m00"] > 0:
            cx = moments["m10"] / moments["m00"]
            cy = moments["m01"] / moments["m00"]
        else:
            cx = w_img / 2.0
            cy = h_img / 2.0
        center_distance = float(
            np.hypot((cx - w_img / 2.0) / max(1.0, w_img / 2.0), (cy - h_img / 2.0) / max(1.0, h_img / 2.0))
        )

        component_count = max(0, cv2.connectedComponents(binary)[0] - 1)
        edge_touch = float(
            np.mean(binary[0, :] > 0)
            + np.mean(binary[-1, :] > 0)
            + np.mean(binary[:, 0] > 0)
            + np.mean(binary[:, -1] > 0)
        ) / 4.0

        features = np.asarray(
            [
                fg_ratio,
                bbox_ratio,
                max(0.0, 1.0 - center_distance),
                min(component_count / 24.0, 1.0),
                edge_touch,
                float(np.std(normalized.astype(np.float32) / 255.0)),
            ],
            dtype=np.float32,
        )
        return features.reshape(1, -1)

    def _calibrate_total_score(
        self,
        probabilities: np.ndarray,
        quality_level: str,
        extras: np.ndarray,
        ocr_confidence: float,
    ) -> int:
        fg_ratio, _bbox_ratio, center_quality, component_norm, edge_touch, texture_std = [float(x) for x in extras[:6]]
        prob_values = np.asarray(probabilities, dtype=np.float32).reshape(-1)
        if prob_values.size == 0:
            prob_values = np.asarray([0.2, 0.6, 0.2], dtype=np.float32)

        best = float(np.max(prob_values))
        if prob_values.size > 1:
            second = float(np.partition(prob_values, -2)[-2])
        else:
            second = 0.0
        margin = max(0.0, best - second)

        feature_quality = (
            0.28 * self._target_band_score(fg_ratio, target=0.46, tolerance=0.24)
            + 0.24 * self._normalize_band(center_quality, low=0.72, high=0.99)
            + 0.16 * self._target_band_score(component_norm, target=0.58, tolerance=0.50)
            + 0.16 * self._target_band_score(edge_touch, target=0.48, tolerance=0.30)
            + 0.16 * self._target_band_score(texture_std, target=0.145, tolerance=0.055)
        )
        confidence_quality = (
            0.60 * self._normalize_band(best, low=0.55, high=0.995)
            + 0.25 * self._normalize_band(margin, low=0.10, high=0.90)
            + 0.15 * self._normalize_band(ocr_confidence, low=0.45, high=0.99)
        )
        signal = float(np.clip(0.72 * feature_quality + 0.28 * confidence_quality, 0.0, 1.0))

        ranges = {
            "bad": (44.0, 68.0),
            "medium": (66.0, 84.0),
            "good": (82.0, 98.0),
        }
        low, high = ranges.get(quality_level, ranges["medium"])
        score = low + (high - low) * signal
        return int(np.clip(round(score), 0, 100))

    @staticmethod
    def _target_band_score(value: float, target: float, tolerance: float) -> float:
        if tolerance <= 0:
            return 0.0
        return float(np.clip(1.0 - abs(value - target) / tolerance, 0.0, 1.0))

    @staticmethod
    def _normalize_band(value: float, low: float, high: float) -> float:
        if high <= low:
            return 0.0
        return float(np.clip((value - low) / (high - low), 0.0, 1.0))

    @staticmethod
    def _encode_character(character: str) -> float:
        if not character:
            return 0.0
        return min(float(ord(character[0])) / 65535.0, 1.0)

    @staticmethod
    def _softmax(values: np.ndarray) -> np.ndarray:
        shifted = values - np.max(values)
        exps = np.exp(shifted)
        return exps / np.sum(exps)


quality_scorer_service = QualityScorerService()
