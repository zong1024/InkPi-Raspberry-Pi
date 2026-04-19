"""Source-backed rubric scoring built on top of existing geometry and quality features."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

import cv2
import numpy as np

from models.evaluation_framework import build_rubric_items, get_rubric_definition, normalize_script
from services.character_geometry_service import character_geometry_service
from services.quality_scorer_service import QualityScorerService


@dataclass
class DimensionScore:
    """Rubric scores plus geometry snapshot."""

    rubric_family: str
    rubric_scores: dict[str, int]
    rubric_items: list[dict[str, Any]]
    geometry_features: dict[str, float]
    rubric_preview_total: float | None


class DimensionScorerService:
    """Build source-backed rubric scores for regular and running script."""

    SCRIPT_PROFILES = {
        "regular": {
            "jieti_bbox_ratio": (0.42, 0.22),
            "jieti_bbox_fill": (0.46, 0.24),
            "bifa_texture_std": (0.145, 0.055),
            "bifa_orientation": (0.14, 0.34),
            "bifa_ink_ratio": (0.46, 0.24),
            "bifa_component_norm": (0.58, 0.50),
            "zhangfa_fill": (0.45, 0.22),
            "zhangfa_projection": (0.68, 0.98),
            "zhangfa_dominant": (0.62, 0.98),
            "mofa_ink_ratio": (0.46, 0.26),
            "mofa_texture": (0.145, 0.060),
        },
        "running": {
            "qushi_bbox_ratio": (0.36, 0.28),
            "qushi_projection": (0.62, 0.96),
            "qushi_dominant": (0.56, 0.96),
            "xianzhi_texture_std": (0.162, 0.075),
            "xianzhi_orientation": (0.10, 0.42),
            "xianzhi_ink_ratio": (0.42, 0.26),
            "jiezou_component_norm": (0.48, 0.50),
            "jiezou_orientation": (0.12, 0.46),
            "moqi_ink_ratio": (0.42, 0.28),
            "moqi_texture": (0.162, 0.075),
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
        normalized_script = normalize_script(script)
        geometry_features = self.extract_geometry_features(image)
        rubric_scores = self.compute_rubric_scores(
            probabilities=probabilities,
            quality_features=quality_features,
            geometry_features=geometry_features,
            calibration=calibration,
            ocr_confidence=ocr_confidence,
            script=normalized_script,
        )
        rubric_items = build_rubric_items(rubric_scores, script=normalized_script)
        return DimensionScore(
            rubric_family=get_rubric_definition(normalized_script)["rubric_family"],
            rubric_scores=rubric_scores,
            rubric_items=rubric_items,
            geometry_features=geometry_features,
            rubric_preview_total=self._build_preview_total(rubric_items),
        )

    def compute_rubric_scores(
        self,
        probabilities: dict[str, float],
        quality_features: dict[str, float],
        geometry_features: dict[str, float],
        calibration: dict[str, Any],
        ocr_confidence: float | None = None,
        script: str | None = None,
    ) -> dict[str, int]:
        normalized_script = normalize_script(script)
        profile = self.SCRIPT_PROFILES[normalized_script]

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
        component_count = float(geometry_features.get("component_count", 0.0))

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

        if normalized_script == "regular":
            raw_scores = {
                "bifa_dianhua": (
                    0.32
                    * self._target_band_score(
                        texture_std,
                        target=profile["bifa_texture_std"][0],
                        tolerance=profile["bifa_texture_std"][1],
                    )
                    + 0.24
                    * self._normalize_band(
                        orientation_concentration,
                        low=profile["bifa_orientation"][0],
                        high=profile["bifa_orientation"][1],
                    )
                    + 0.24
                    * self._target_band_score(
                        fg_ratio,
                        target=profile["bifa_ink_ratio"][0],
                        tolerance=profile["bifa_ink_ratio"][1],
                    )
                    + 0.20
                    * self._target_band_score(
                        component_norm,
                        target=profile["bifa_component_norm"][0],
                        tolerance=profile["bifa_component_norm"][1],
                    )
                ),
                "jieti_zifa": (
                    0.34 * center_quality
                    + 0.26
                    * self._target_band_score(
                        bbox_ratio,
                        target=profile["jieti_bbox_ratio"][0],
                        tolerance=profile["jieti_bbox_ratio"][1],
                    )
                    + 0.20 * projection_balance
                    + 0.20
                    * self._target_band_score(
                        bbox_fill,
                        target=profile["jieti_bbox_fill"][0],
                        tolerance=profile["jieti_bbox_fill"][1],
                    )
                ),
                "bubai_zhangfa": (
                    0.35
                    * self._normalize_band(
                        projection_balance,
                        low=profile["zhangfa_projection"][0],
                        high=profile["zhangfa_projection"][1],
                    )
                    + 0.25
                    * self._target_band_score(
                        bbox_fill,
                        target=profile["zhangfa_fill"][0],
                        tolerance=profile["zhangfa_fill"][1],
                    )
                    + 0.20
                    * self._normalize_band(
                        dominant_share,
                        low=profile["zhangfa_dominant"][0],
                        high=profile["zhangfa_dominant"][1],
                    )
                    + 0.20 * subject_edge_safe
                ),
                "mofa_bili": (
                    0.28
                    * self._target_band_score(
                        fg_ratio,
                        target=profile["mofa_ink_ratio"][0],
                        tolerance=profile["mofa_ink_ratio"][1],
                    )
                    + 0.24
                    * self._target_band_score(
                        texture_std,
                        target=profile["mofa_texture"][0],
                        tolerance=profile["mofa_texture"][1],
                    )
                    + 0.24 * feature_quality
                    + 0.24 * quality_confidence_norm
                ),
                "guifan_wanzheng": (
                    0.34 * ocr_confidence_norm
                    + 0.22 * self._normalize_band(dominant_share, low=0.45, high=0.98)
                    + 0.18 * (1.0 - edge_touch)
                    + 0.16 * subject_edge_safe
                    + 0.10 * score_range_fit
                ),
            }
        else:
            component_flow = self._target_band_score(
                component_norm,
                target=profile["jiezou_component_norm"][0],
                tolerance=profile["jiezou_component_norm"][1],
            )
            raw_scores = {
                "yongbi_xianzhi": (
                    0.32
                    * self._target_band_score(
                        texture_std,
                        target=profile["xianzhi_texture_std"][0],
                        tolerance=profile["xianzhi_texture_std"][1],
                    )
                    + 0.28
                    * self._normalize_band(
                        orientation_concentration,
                        low=profile["xianzhi_orientation"][0],
                        high=profile["xianzhi_orientation"][1],
                    )
                    + 0.20
                    * self._target_band_score(
                        fg_ratio,
                        target=profile["xianzhi_ink_ratio"][0],
                        tolerance=profile["xianzhi_ink_ratio"][1],
                    )
                    + 0.20 * quality_confidence_norm
                ),
                "jieti_qushi": (
                    0.32 * center_quality
                    + 0.24
                    * self._target_band_score(
                        bbox_ratio,
                        target=profile["qushi_bbox_ratio"][0],
                        tolerance=profile["qushi_bbox_ratio"][1],
                    )
                    + 0.24
                    * self._normalize_band(
                        projection_balance,
                        low=profile["qushi_projection"][0],
                        high=profile["qushi_projection"][1],
                    )
                    + 0.20
                    * self._normalize_band(
                        dominant_share,
                        low=profile["qushi_dominant"][0],
                        high=profile["qushi_dominant"][1],
                    )
                ),
                "liandai_jiezou": (
                    0.30 * component_flow
                    + 0.28
                    * self._normalize_band(
                        orientation_concentration,
                        low=profile["jiezou_orientation"][0],
                        high=profile["jiezou_orientation"][1],
                    )
                    + 0.20 * self._normalize_band(dominant_share, low=0.45, high=0.98)
                    + 0.12 * probability_margin_norm
                    + 0.10 * self._normalize_band(component_count, low=1.0, high=4.0)
                ),
                "moqi_bili": (
                    0.28
                    * self._target_band_score(
                        fg_ratio,
                        target=profile["moqi_ink_ratio"][0],
                        tolerance=profile["moqi_ink_ratio"][1],
                    )
                    + 0.24
                    * self._target_band_score(
                        texture_std,
                        target=profile["moqi_texture"][0],
                        tolerance=profile["moqi_texture"][1],
                    )
                    + 0.24 * feature_quality
                    + 0.24 * quality_confidence_norm
                ),
                "guifan_shibie": (
                    0.36 * ocr_confidence_norm
                    + 0.20 * (1.0 - edge_touch)
                    + 0.20 * subject_edge_safe
                    + 0.14 * probability_margin_norm
                    + 0.10 * score_range_fit
                ),
            }

        return {
            key: self._anchor_score(value)
            for key, value in raw_scores.items()
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
    def _build_preview_total(rubric_items: list[dict[str, Any]]) -> float | None:
        if not rubric_items:
            return None
        total_weight = sum(int(item.get("weight", 0)) for item in rubric_items)
        if total_weight <= 0:
            return None
        weighted = sum(int(item["score"]) * int(item["weight"]) for item in rubric_items)
        return round(weighted / total_weight, 1)

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
    def _anchor_score(value: float) -> int:
        score = float(np.clip(value, 0.0, 1.0))
        if score < 0.20:
            return 20
        if score < 0.40:
            return 40
        if score < 0.60:
            return 60
        if score < 0.80:
            return 80
        return 100

    @staticmethod
    def _target_band_score(value: float, target: float, tolerance: float) -> float:
        return QualityScorerService._target_band_score(value, target=target, tolerance=tolerance)

    @staticmethod
    def _normalize_band(value: float, low: float, high: float) -> float:
        return QualityScorerService._normalize_band(value, low=low, high=high)


dimension_scorer_service = DimensionScorerService()
