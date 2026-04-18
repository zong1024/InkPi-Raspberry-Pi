"""Dual-script ONNX quality scorer for InkPi."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any

import cv2
import numpy as np
try:
    import onnxruntime as ort
    _ORT_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # noqa: BLE001
    ort = None  # type: ignore[assignment]
    _ORT_IMPORT_ERROR = exc

from config import QUALITY_SCORER_CONFIG, SCRIPT_CONFIG
from models.evaluation_framework import get_script_label, normalize_script


DEFAULT_SCRIPT = str(SCRIPT_CONFIG["default"])


@dataclass
class QualityScore:
    """Scoring output returned by the ONNX quality model."""

    total_score: int
    quality_level: str
    quality_confidence: float
    probabilities: dict[str, float]
    quality_features: dict[str, float] | None = None
    calibration: dict[str, float | str] | None = None


class QualityScorerService:
    """Load and run dual-script ONNX scoring models."""

    QUALITY_FEATURE_NAMES = (
        "fg_ratio",
        "bbox_ratio",
        "center_quality",
        "component_norm",
        "edge_touch",
        "texture_std",
    )

    SCRIPT_SCORE_RANGES = {
        "regular": {
            "bad": (44.0, 68.0),
            "medium": (66.0, 84.0),
            "good": (82.0, 98.0),
        },
        "running": {
            "bad": (42.0, 68.0),
            "medium": (64.0, 84.0),
            "good": (80.0, 97.0),
        },
    }

    SCRIPT_DIMENSION_TARGETS = {
        "regular": {
            "fg_ratio": (0.46, 0.24),
            "center_quality": (0.72, 0.99),
            "component_norm": (0.58, 0.50),
            "edge_touch": (0.48, 0.30),
            "texture_std": (0.145, 0.055),
        },
        "running": {
            "fg_ratio": (0.42, 0.26),
            "center_quality": (0.66, 0.98),
            "component_norm": (0.48, 0.50),
            "edge_touch": (0.42, 0.36),
            "texture_std": (0.162, 0.075),
        },
    }

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.config = QUALITY_SCORER_CONFIG
        self.input_size = int(self.config.get("input_size", 32))
        self.labels = list(self.config.get("labels", ["bad", "medium", "good"]))
        self.score_scale = float(self.config.get("score_scale", 100.0))
        self.default_level = str(self.config.get("default_level", "medium"))
        self.default_script = normalize_script(self.config.get("default_script", DEFAULT_SCRIPT))
        self.script_configs = {
            normalize_script(script): dict(config)
            for script, config in dict(self.config.get("scripts", {})).items()
        }
        self._sessions: dict[str, Any] = {}
        self._input_names: dict[str, list[str]] = {}
        self._input_shapes: dict[str, dict[str, list[int | str | None]]] = {}
        self._output_names: dict[str, list[str]] = {}
        self._load_sessions()

    def _load_sessions(self) -> None:
        if ort is None:
            self.logger.warning("onnxruntime is unavailable on this device: %s", _ORT_IMPORT_ERROR)
            return

        for script, config in self.script_configs.items():
            model_path = Path(config["onnx_path"])
            if not model_path.exists():
                self.logger.warning("Quality scorer model is missing for %s: %s", script, model_path)
                continue

            options = ort.SessionOptions()
            options.intra_op_num_threads = int(self.config.get("num_threads", 2))
            options.inter_op_num_threads = 1
            try:
                session = ort.InferenceSession(
                    str(model_path),
                    sess_options=options,
                    providers=["CPUExecutionProvider"],
                )
                self._sessions[script] = session
                self._input_names[script] = [item.name for item in session.get_inputs()]
                self._input_shapes[script] = {
                    item.name: list(item.shape) for item in session.get_inputs()
                }
                self._output_names[script] = [item.name for item in session.get_outputs()]
            except Exception as exc:  # noqa: BLE001
                self.logger.warning("Failed to load quality scorer ONNX for %s: %s", script, exc)

    @property
    def available(self) -> bool:
        return bool(self._sessions)

    @property
    def model_path(self) -> Path:
        return self.get_model_path(self.default_script)

    def get_model_path(self, script: str | None) -> Path:
        normalized_script = normalize_script(script)
        config = self.script_configs.get(normalized_script) or self.script_configs[self.default_script]
        return Path(config["onnx_path"])

    def get_metrics_path(self, script: str | None) -> Path:
        normalized_script = normalize_script(script)
        config = self.script_configs.get(normalized_script) or self.script_configs[self.default_script]
        return Path(config["metrics_path"])

    def is_script_available(self, script: str | None) -> bool:
        return normalize_script(script) in self._sessions

    def get_model_status(self) -> dict[str, dict[str, Any]]:
        status = {}
        for script, config in self.script_configs.items():
            status[script] = {
                "script": script,
                "script_label": get_script_label(script),
                "ready": script in self._sessions,
                "model_path": str(config["onnx_path"]),
                "metrics_path": str(config["metrics_path"]),
                "input_size": self.input_size,
                "labels": list(self.labels),
            }
        return status

    def score(
        self,
        image: np.ndarray,
        character: str,
        *,
        script: str | None = None,
        ocr_confidence: float | None = None,
    ) -> QualityScore:
        """Run the ONNX scorer and return a stable total score and level."""

        normalized_script = normalize_script(script)
        session = self._sessions.get(normalized_script)
        if session is None:
            raise RuntimeError(
                f"script_model_unavailable:{normalized_script}:{self.get_model_path(normalized_script)}"
            )

        roi = self._prepare_image(image)
        char_code = np.asarray([[self._encode_character(character)]], dtype=np.float32)
        ocr_conf = np.asarray([[float(ocr_confidence or 0.0)]], dtype=np.float32)

        feed = self._build_feed(normalized_script, image, roi, char_code, ocr_conf)

        outputs = session.run(None, feed)
        by_name = dict(zip(self._output_names[normalized_script], outputs))

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
        quality_features = self._extract_quality_feature_map(image)
        extras = self._features_to_array(quality_features)
        calibration = self._build_calibration_snapshot(
            probabilities=probabilities,
            quality_level=quality_level,
            extras=extras,
            ocr_confidence=float(ocr_confidence or 0.0),
            script=normalized_script,
        )

        if raw_score is None:
            total_score = int(calibration["calibrated_score"])
            calibration["score_source"] = "calibrated"
        elif raw_score <= 1.0:
            calibrated = int(calibration["calibrated_score"])
            total_score = int(np.clip(round((raw_score * self.score_scale) * 0.35 + calibrated * 0.65), 0, 100))
            calibration["score_source"] = "blended"
            calibration["raw_score"] = float(raw_score)
        else:
            total_score = int(np.clip(round(raw_score), 0, 100))
            calibration["score_source"] = "raw"
            calibration["raw_score"] = float(raw_score)

        calibration["final_score"] = float(total_score)
        calibration["score_range_fit"] = self._score_range_fit(total_score, quality_level, script=normalized_script)

        return QualityScore(
            total_score=total_score,
            quality_level=quality_level,
            quality_confidence=float(probabilities[best_index]),
            probabilities={
                label: float(probabilities[index]) for index, label in enumerate(self.labels[: len(probabilities)])
            },
            quality_features=quality_features,
            calibration={
                key: float(value) if isinstance(value, (int, float, np.floating)) else str(value)
                for key, value in calibration.items()
            },
        )

    def _build_feed(
        self,
        script: str,
        image: np.ndarray,
        roi: np.ndarray,
        char_code: np.ndarray,
        ocr_conf: np.ndarray,
    ) -> dict[str, np.ndarray]:
        input_names = self._input_names[script]
        input_shapes = self._input_shapes[script]
        if len(input_names) == 1:
            name = input_names[0]
            shape = input_shapes.get(name, [])
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
        for name in input_names:
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
        return self._features_to_array(self._extract_quality_feature_map(image))

    def _extract_quality_feature_map(self, image: np.ndarray) -> dict[str, float]:
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
            return {name: 0.0 for name in self.QUALITY_FEATURE_NAMES}

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

        return {
            "fg_ratio": float(fg_ratio),
            "bbox_ratio": float(bbox_ratio),
            "center_quality": float(max(0.0, 1.0 - center_distance)),
            "component_norm": float(min(component_count / 24.0, 1.0)),
            "edge_touch": float(edge_touch),
            "texture_std": float(np.std(normalized.astype(np.float32) / 255.0)),
        }

    def _calibrate_total_score(
        self,
        probabilities: np.ndarray,
        quality_level: str,
        extras: np.ndarray,
        ocr_confidence: float,
        *,
        script: str | None = None,
    ) -> int:
        details = self._build_calibration_snapshot(
            probabilities=probabilities,
            quality_level=quality_level,
            extras=extras,
            ocr_confidence=ocr_confidence,
            script=normalize_script(script),
        )
        return int(details["calibrated_score"])

    def _build_calibration_snapshot(
        self,
        probabilities: np.ndarray,
        quality_level: str,
        extras: np.ndarray,
        ocr_confidence: float,
        *,
        script: str,
    ) -> dict[str, float | str]:
        normalized_script = normalize_script(script)
        targets = self.SCRIPT_DIMENSION_TARGETS[normalized_script]
        extras = np.asarray(extras, dtype=np.float32).reshape(-1)
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
            0.28 * self._target_band_score(fg_ratio, target=targets["fg_ratio"][0], tolerance=targets["fg_ratio"][1])
            + 0.24 * self._normalize_band(
                center_quality,
                low=targets["center_quality"][0],
                high=targets["center_quality"][1],
            )
            + 0.16
            * self._target_band_score(
                component_norm,
                target=targets["component_norm"][0],
                tolerance=targets["component_norm"][1],
            )
            + 0.16
            * self._target_band_score(
                edge_touch,
                target=targets["edge_touch"][0],
                tolerance=targets["edge_touch"][1],
            )
            + 0.16
            * self._target_band_score(
                texture_std,
                target=targets["texture_std"][0],
                tolerance=targets["texture_std"][1],
            )
        )
        confidence_quality = (
            0.60 * self._normalize_band(best, low=0.55, high=0.995)
            + 0.25 * self._normalize_band(margin, low=0.10, high=0.90)
            + 0.15 * self._normalize_band(ocr_confidence, low=0.45, high=0.99)
        )
        signal = float(np.clip(0.72 * feature_quality + 0.28 * confidence_quality, 0.0, 1.0))
        low, high = self.SCRIPT_SCORE_RANGES[normalized_script].get(
            quality_level,
            self.SCRIPT_SCORE_RANGES[normalized_script]["medium"],
        )
        score = low + (high - low) * signal
        return {
            "script": normalized_script,
            "script_label": get_script_label(normalized_script),
            "best_probability": float(best),
            "second_probability": float(second),
            "probability_margin": float(margin),
            "probability_margin_norm": float(self._normalize_band(margin, low=0.10, high=0.90)),
            "ocr_confidence_norm": float(self._normalize_band(ocr_confidence, low=0.45, high=0.99)),
            "quality_confidence_norm": float(self._normalize_band(best, low=0.55, high=0.995)),
            "feature_quality": float(feature_quality),
            "confidence_quality": float(confidence_quality),
            "signal": float(signal),
            "quality_range_low": float(low),
            "quality_range_high": float(high),
            "calibrated_score": float(np.clip(round(score), 0, 100)),
        }

    def _score_range_fit(self, total_score: int, quality_level: str, *, script: str) -> float:
        normalized_script = normalize_script(script)
        low, high = self.SCRIPT_SCORE_RANGES[normalized_script].get(
            quality_level,
            self.SCRIPT_SCORE_RANGES[normalized_script]["medium"],
        )
        target = (low + high) / 2.0
        tolerance = max((high - low) / 2.0, 1.0)
        return float(self._target_band_score(float(total_score), target=target, tolerance=tolerance))

    def _features_to_array(self, feature_map: dict[str, float]) -> np.ndarray:
        values = [float(feature_map.get(name, 0.0)) for name in self.QUALITY_FEATURE_NAMES]
        return np.asarray(values, dtype=np.float32).reshape(1, -1)

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
