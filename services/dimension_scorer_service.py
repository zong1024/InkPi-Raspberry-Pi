"""Four-dimension explanatory scoring for single-character evaluations."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

import cv2
import numpy as np

from models.evaluation_framework import normalize_script
from services.character_geometry_service import character_geometry_service
from services.quality_scorer_service import QualityScorerService


@dataclass
class DimensionScore:
    """Explanatory dimension scores plus geometry snapshot."""

    dimension_scores: dict[str, int]
    geometry_features: dict[str, float]


class DimensionScorerService:
    """Build user-facing structure/stroke/integrity/stability scores."""

    SCRIPT_PROFILES = {
        "regular": {
            "structure_bbox_ratio": (0.42, 0.22),
            "structure_bbox_fill": (0.46, 0.24),
            "stroke_texture_std": (0.145, 0.055),
            "stroke_orientation": (0.14, 0.34),
            "stroke_ink_ratio": (0.46, 0.24),
            "stroke_component_norm": (0.58, 0.50),
        },
        "running": {
            "structure_bbox_ratio": (0.36, 0.28),
            "structure_bbox_fill": (0.41, 0.30),
            "stroke_texture_std": (0.162, 0.075),
            "stroke_orientation": (0.10, 0.42),
            "stroke_ink_ratio": (0.42, 0.26),
            "stroke_component_norm": (0.48, 0.50),
        },
    }

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    def score(
        self,
        image: np.ndarray,
        probabilities: dict[str, float],
        quality_features: dict[str, float],
        calibration: dict[str, Any],
        ocr_confidence: float | None = None,
        script: str | None = None,
    ) -> DimensionScore:
        geometry_features = self.extract_geometry_features(image)
        dimension_scores = self.compute_dimension_scores(
            probabilities=probabilities,
            quality_features=quality_features,
            geometry_features=geometry_features,
            calibration=calibration,
            ocr_confidence=ocr_confidence,
            script=script,
        )
        return DimensionScore(
            dimension_scores=dimension_scores,
            geometry_features=geometry_features,
        )

    def compute_dimension_scores(
        self,
        probabilities: dict[str, float],
        quality_features: dict[str, float],
        geometry_features: dict[str, float],
        calibration: dict[str, Any],
        ocr_confidence: float | None = None,
        script: str | None = None,
    ) -> dict[str, int]:
        profile = self.SCRIPT_PROFILES[normalize_script(script)]
        center_quality = float(quality_features.get("center_quality", 0.0))
        bbox_ratio = float(quality_features.get("bbox_ratio", 0.0))
        texture_std = float(quality_features.get("texture_std", 0.0))
        fg_ratio = float(quality_features.get("fg_ratio", 0.0))
        component_norm = float(quality_features.get("component_norm", 0.0))
        edge_touch = float(quality_features.get("edge_touch", 0.0))

        projection_balance = float(geometry_features.get("projection_balance", 0.0))
        dominant_share = float(geometry_features.get("dominant_share", 0.0))
        bbox_fill = float(geometry_features.get("bbox_fill", 0.0))
        orientation_concentration = float(geometry_features.get("orientation_concentration", 0.0))
        subject_edge_safe = float(geometry_features.get("subject_edge_safe", 0.0))

        ocr_confidence_value = float(ocr_confidence or 0.0)
        ocr_confidence_norm = self._normalize_band(ocr_confidence_value, low=0.45, high=0.99)

        probabilities = probabilities or {}
        sorted_probs = sorted((float(value) for value in probabilities.values()), reverse=True)
        best_probability = sorted_probs[0] if sorted_probs else float(calibration.get("best_probability", 0.0) or 0.0)
        second_probability = sorted_probs[1] if len(sorted_probs) > 1 else float(
            calibration.get("second_probability", 0.0) or 0.0
        )
        probability_margin = max(0.0, best_probability - second_probability)
        probability_margin_norm = float(
            calibration.get("probability_margin_norm", self._normalize_band(probability_margin, low=0.10, high=0.90))
            or 0.0
        )
        quality_confidence_norm = float(
            calibration.get("quality_confidence_norm", self._normalize_band(best_probability, low=0.55, high=0.995))
            or 0.0
        )
        feature_quality = float(calibration.get("feature_quality", 0.0) or 0.0)
        score_range_fit = float(calibration.get("score_range_fit", 0.0) or 0.0)

        structure = (
            0.35 * center_quality
            + 0.25
            * self._target_band_score(
                bbox_ratio,
                target=profile["structure_bbox_ratio"][0],
                tolerance=profile["structure_bbox_ratio"][1],
            )
            + 0.20 * projection_balance
            + 0.20
            * self._target_band_score(
                bbox_fill,
                target=profile["structure_bbox_fill"][0],
                tolerance=profile["structure_bbox_fill"][1],
            )
        )
        stroke = (
            0.30
            * self._target_band_score(
                texture_std,
                target=profile["stroke_texture_std"][0],
                tolerance=profile["stroke_texture_std"][1],
            )
            + 0.25
            * self._normalize_band(
                orientation_concentration,
                low=profile["stroke_orientation"][0],
                high=profile["stroke_orientation"][1],
            )
            + 0.25
            * self._target_band_score(
                fg_ratio,
                target=profile["stroke_ink_ratio"][0],
                tolerance=profile["stroke_ink_ratio"][1],
            )
            + 0.20
            * self._target_band_score(
                component_norm,
                target=profile["stroke_component_norm"][0],
                tolerance=profile["stroke_component_norm"][1],
            )
        )
        integrity = (
            0.35 * ocr_confidence_norm
            + 0.25 * self._normalize_band(dominant_share, low=0.45, high=0.98)
            + 0.20 * (1.0 - edge_touch)
            + 0.20 * subject_edge_safe
        )
        stability = (
            0.40 * quality_confidence_norm
            + 0.25 * probability_margin_norm
            + 0.20 * feature_quality
            + 0.15 * score_range_fit
        )

        return {
            "structure": self._to_score(structure),
            "stroke": self._to_score(stroke),
            "integrity": self._to_score(integrity),
            "stability": self._to_score(stability),
        }

    def extract_geometry_features(self, image: np.ndarray) -> dict[str, float]:
        binary = character_geometry_service.prepare_binary(image)
        subject = character_geometry_service.extract_subject_from_binary(binary)

        if subject is not None:
            normalized = subject.binary
            component_count = float(subject.component_count)
            dominant_share = float(subject.dominant_share)
            touches_edge = 1.0 if subject.touches_edge else 0.0
            ink_ratio = float(subject.ink_ratio)
            signature = subject.signature
        else:
            normalized = character_geometry_service._ensure_binary(binary)  # type: ignore[attr-defined]
            mask = (normalized == 0).astype(np.uint8)
            signature = character_geometry_service.build_signature(normalized)
            component_count = float(max(0, cv2.connectedComponents(mask)[0] - 1))
            component_areas = self._component_areas(mask)
            dominant_share = float(component_areas.max() / component_areas.sum()) if component_areas.size else 0.0
            touches_edge = 1.0 if self._touches_edge(mask) else 0.0
            ink_ratio = float(np.mean(mask))

        topology = signature.topology
        orientation_hist = np.asarray(signature.orientation_hist, dtype=np.float32).reshape(-1)
        projection_balance = self._projection_balance(signature.projection_x, signature.projection_y)
        orientation_concentration = float(np.max(orientation_hist)) if orientation_hist.size else 0.0

        return {
            "projection_balance": float(projection_balance),
            "dominant_share": float(dominant_share or topology.get("dominant_share", 0.0)),
            "bbox_fill": float(topology.get("bbox_fill", 0.0)),
            "touches_edge": float(touches_edge),
            "subject_edge_safe": float(1.0 - touches_edge),
            "component_count": float(component_count or topology.get("component_count", 0.0)),
            "orientation_concentration": float(orientation_concentration),
            "ink_ratio": float(ink_ratio or topology.get("ink_ratio", 0.0)),
        }

    @staticmethod
    def _projection_balance(projection_x: np.ndarray, projection_y: np.ndarray) -> float:
        def balance(values: np.ndarray) -> float:
            values = np.asarray(values, dtype=np.float32).reshape(-1)
            if values.size == 0:
                return 0.0
            midpoint = values.size // 2
            left = float(np.sum(values[:midpoint]))
            right = float(np.sum(values[midpoint:]))
            total = max(left + right, 1e-6)
            return float(np.clip(1.0 - abs(left - right) / total, 0.0, 1.0))

        return (balance(projection_x) + balance(projection_y)) / 2.0

    @staticmethod
    def _component_areas(mask: np.ndarray) -> np.ndarray:
        num_labels, _labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
        if num_labels <= 1:
            return np.asarray([], dtype=np.float32)
        return stats[1:, cv2.CC_STAT_AREA].astype(np.float32)

    @staticmethod
    def _touches_edge(mask: np.ndarray) -> bool:
        return bool(
            np.any(mask[0, :] > 0)
            or np.any(mask[-1, :] > 0)
            or np.any(mask[:, 0] > 0)
            or np.any(mask[:, -1] > 0)
        )

    @staticmethod
    def _to_score(value: float) -> int:
        return int(np.clip(round(float(value) * 100.0), 0, 100))

    @staticmethod
    def _target_band_score(value: float, target: float, tolerance: float) -> float:
        return QualityScorerService._target_band_score(value, target=target, tolerance=tolerance)

    @staticmethod
    def _normalize_band(value: float, low: float, high: float) -> float:
        return QualityScorerService._normalize_band(value, low=low, high=high)


dimension_scorer_service = DimensionScorerService()
