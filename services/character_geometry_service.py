"""Recognition-focused character ROI extraction and geometric signatures."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

import cv2
import numpy as np

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.preprocessing_service import preprocessing_service


@dataclass
class CharacterSignature:
    """Compact geometric description of a normalized single-character subject."""

    zoning: np.ndarray
    projection_x: np.ndarray
    projection_y: np.ndarray
    hu_moments: np.ndarray
    orientation_hist: np.ndarray
    topology: Dict[str, float]


@dataclass
class CharacterSubject:
    """Normalized character crop used by recognition and open-set rejection."""

    binary: np.ndarray
    bbox: Tuple[int, int, int, int]
    ink_ratio: float
    component_count: int
    dominant_share: float
    touches_edge: bool
    signature: CharacterSignature


class CharacterGeometryService:
    """Extract the dominant single-character ROI and compare its geometry."""

    def __init__(self, target_size: Tuple[int, int] = (224, 224)) -> None:
        self.logger = logging.getLogger(__name__)
        self.target_size = target_size

    def extract_subject(self, image: np.ndarray) -> Optional[CharacterSubject]:
        """Extract a normalized single-character subject from an input image."""
        binary = self.prepare_binary(image)
        return self.extract_subject_from_binary(binary)

    def extract_subject_from_binary(self, binary: np.ndarray) -> Optional[CharacterSubject]:
        """Extract a normalized single-character subject from a binary image."""
        binary = self._ensure_binary(binary)
        foreground = (binary == 0).astype(np.uint8)
        total_ink = int(np.sum(foreground))
        if total_ink <= max(36, int(binary.size * 0.008)):
            return None

        min_area = max(20, int(binary.size * 0.00016))
        original_labels, original_components = self._extract_components(foreground, binary.shape, min_area)
        if not original_components:
            return None

        score_mask = self._build_core_mask(foreground)
        if int(np.sum(score_mask)) > max(20, int(binary.size * 0.001)):
            core_labels, core_components = self._extract_components(score_mask, binary.shape, min_area)
        else:
            core_labels, core_components = original_labels, original_components

        if not core_components:
            return None

        core_anchor = max(core_components, key=lambda item: item["score"])
        selected_core = self._collect_subject_components(core_components, core_anchor, binary.shape)
        if not selected_core:
            selected_core = [core_anchor]

        support_bbox = self._union_bbox(selected_core)
        selected_original = self._collect_components_in_region(original_components, binary.shape, support_bbox)
        if not selected_original:
            selected_original = self._collect_subject_components(original_components, max(original_components, key=lambda item: item["score"]), binary.shape)
        if not selected_original:
            return None

        original_anchor = max(selected_original, key=lambda item: item["score"])
        subject_binary = self._render_selected_binary(binary.shape, original_labels, selected_original)
        content_bbox = self._content_bbox(subject_binary)
        if content_bbox is None:
            return None

        union_bbox = content_bbox
        normalized = self._normalize_subject(subject_binary, union_bbox)
        normalized = self._ensure_binary(normalized)

        ink_ratio = float(np.mean(normalized == 0))
        if ink_ratio < 0.01 or ink_ratio > 0.52:
            return None

        signature = self.build_signature(normalized)
        return CharacterSubject(
            binary=normalized,
            bbox=union_bbox,
            ink_ratio=ink_ratio,
            component_count=len(selected_original),
            dominant_share=float(original_anchor["area_share"]),
            touches_edge=bool(original_anchor["touches_edge"]),
            signature=signature,
        )

    def prepare_binary(self, image: np.ndarray) -> np.ndarray:
        """Build a clean binary image specifically for recognition."""
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            source = image
        else:
            gray = image.copy()
            source = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

        binary_like = self._is_binary_like(gray)
        if binary_like:
            binary = gray.copy()
        else:
            binary = preprocessing_service._build_precheck_binary(source)

        return self._ensure_binary(binary)

    def build_signature(self, binary: np.ndarray) -> CharacterSignature:
        """Create a geometric signature for a normalized binary image."""
        binary = self._ensure_binary(binary)
        mask = (binary == 0).astype(np.uint8)

        zoning = self._compute_zoning(mask, grid=5)
        projection_x = self._downsample_projection(np.mean(mask, axis=0), length=16)
        projection_y = self._downsample_projection(np.mean(mask, axis=1), length=16)
        hu_moments = self._compute_hu_moments(mask)
        orientation_hist = self._compute_orientation_histogram(binary, bins=8)
        topology = self._compute_topology(binary, mask)

        return CharacterSignature(
            zoning=zoning,
            projection_x=projection_x,
            projection_y=projection_y,
            hu_moments=hu_moments,
            orientation_hist=orientation_hist,
            topology=topology,
        )

    def compare_signature(self, left: CharacterSignature, right: CharacterSignature) -> Dict[str, float]:
        """Compare two signatures and return normalized similarities."""
        zoning_score = self._vector_similarity(left.zoning, right.zoning)
        projection_score = (
            self._vector_similarity(left.projection_x, right.projection_x)
            + self._vector_similarity(left.projection_y, right.projection_y)
        ) / 2.0
        hu_score = self._hu_similarity(left.hu_moments, right.hu_moments)
        orientation_score = self._vector_similarity(left.orientation_hist, right.orientation_hist)
        topology_score = self._topology_similarity(left.topology, right.topology)
        signature_score = (
            zoning_score * 0.35
            + projection_score * 0.25
            + hu_score * 0.20
            + orientation_score * 0.20
        )
        return {
            "signature": float(signature_score),
            "zoning": float(zoning_score),
            "projection": float(projection_score),
            "hu": float(hu_score),
            "orientation": float(orientation_score),
            "topology": float(topology_score),
        }

    def contour_similarity(self, image_a: np.ndarray, image_b: np.ndarray) -> float:
        """Contour-shape similarity in [0, 1]."""
        binary_a = self._ensure_binary(image_a)
        binary_b = self._ensure_binary(image_b)
        contours_a, _ = cv2.findContours(255 - binary_a, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours_b, _ = cv2.findContours(255 - binary_b, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours_a or not contours_b:
            return 0.0
        contour_a = max(contours_a, key=cv2.contourArea)
        contour_b = max(contours_b, key=cv2.contourArea)
        distance = cv2.matchShapes(contour_a, contour_b, cv2.CONTOURS_MATCH_I1, 0.0)
        return float(1.0 / (1.0 + max(distance, 0.0) * 6.0))

    def coverage_similarity(self, left: CharacterSubject, right: CharacterSubject) -> float:
        """Similarity of subject coverage/topology stats in [0, 1]."""
        topo_a = left.signature.topology
        topo_b = right.signature.topology
        ink = min(1.0, abs(topo_a["ink_ratio"] - topo_b["ink_ratio"]) / 0.30)
        fill = min(1.0, abs(topo_a["bbox_fill"] - topo_b["bbox_fill"]) / 0.45)
        dominant = min(1.0, abs(left.dominant_share - right.dominant_share) / 0.60)
        diff = ink * 0.40 + fill * 0.35 + dominant * 0.25
        return float(max(0.0, 1.0 - diff))

    def _collect_subject_components(self, components, anchor, shape):
        image_h, image_w = shape
        margin = int(max(anchor["w"], anchor["h"]) * 0.48)
        x0 = max(0, anchor["x"] - margin)
        y0 = max(0, anchor["y"] - margin)
        x1 = min(image_w, anchor["x"] + anchor["w"] + margin)
        y1 = min(image_h, anchor["y"] + anchor["h"] + margin)

        selected = []
        for component in components:
            box = (
                component["x"],
                component["y"],
                component["x"] + component["w"],
                component["y"] + component["h"],
            )
            overlaps = not (box[2] < x0 or box[0] > x1 or box[3] < y0 or box[1] > y1)
            center_inside = x0 <= component["cx"] <= x1 and y0 <= component["cy"] <= y1
            sizeable = component["area"] >= max(18, int(anchor["area"] * 0.05))
            score_near_anchor = component["score"] >= anchor["score"] * 0.60
            keep = component["label"] == anchor["label"] or ((overlaps or center_inside) and sizeable)
            if keep and score_near_anchor and not component["touches_edge"]:
                selected.append(component)

        if selected:
            selected = sorted(selected, key=lambda item: item["score"], reverse=True)[:6]
        return selected

    def _collect_components_in_region(self, components, shape, region_bbox):
        image_h, image_w = shape
        x, y, w, h = region_bbox
        margin = int(max(w, h) * 0.42)
        x0 = max(0, x - margin)
        y0 = max(0, y - margin)
        x1 = min(image_w, x + w + margin)
        y1 = min(image_h, y + h + margin)
        overlapping = []
        for component in components:
            box = (
                component["x"],
                component["y"],
                component["x"] + component["w"],
                component["y"] + component["h"],
            )
            overlaps = not (box[2] < x0 or box[0] > x1 or box[3] < y0 or box[1] > y1)
            center_inside = x0 <= component["cx"] <= x1 and y0 <= component["cy"] <= y1
            if (overlaps or center_inside) and not component["touches_edge"]:
                overlapping.append(component)

        if not overlapping:
            return []

        anchor = max(overlapping, key=lambda item: item["score"])
        threshold = anchor["score"] * 0.60
        min_area = max(18, int(anchor["area"] * 0.05))
        selected = [
            component
            for component in overlapping
            if component["score"] >= threshold and component["area"] >= min_area
        ]
        return sorted(selected, key=lambda item: item["score"], reverse=True)[:6]

    def _render_selected_binary(self, shape, labels, components):
        canvas = np.ones(shape, dtype=np.uint8) * 255
        label_ids = {component["label"] for component in components}
        selection = np.isin(labels, list(label_ids))
        canvas[selection] = 0
        return canvas

    def _normalize_subject(self, binary: np.ndarray, bbox: Tuple[int, int, int, int]) -> np.ndarray:
        x, y, w, h = bbox
        pad = max(10, int(max(w, h) * 0.14))
        x0 = max(0, x - pad)
        y0 = max(0, y - pad)
        x1 = min(binary.shape[1], x + w + pad)
        y1 = min(binary.shape[0], y + h + pad)
        crop = binary[y0:y1, x0:x1]

        content_bbox = self._content_bbox(crop)
        if content_bbox is not None:
            cx, cy, cw, ch = content_bbox
            crop = crop[cy : cy + ch, cx : cx + cw]

        target_h, target_w = self.target_size
        margin = 18
        scale = min((target_w - margin * 2) / max(1, crop.shape[1]), (target_h - margin * 2) / max(1, crop.shape[0]))
        resized_w = max(1, int(round(crop.shape[1] * scale)))
        resized_h = max(1, int(round(crop.shape[0] * scale)))
        resized = cv2.resize(crop, (resized_w, resized_h), interpolation=cv2.INTER_NEAREST)

        canvas = np.ones((target_h, target_w), dtype=np.uint8) * 255
        offset_x = (target_w - resized_w) // 2
        offset_y = (target_h - resized_h) // 2
        canvas[offset_y : offset_y + resized_h, offset_x : offset_x + resized_w] = resized
        return canvas

    def _content_bbox(self, binary: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        ys, xs = np.where(binary == 0)
        if len(xs) == 0:
            return None
        x0 = int(xs.min())
        y0 = int(ys.min())
        x1 = int(xs.max()) + 1
        y1 = int(ys.max()) + 1
        return x0, y0, x1 - x0, y1 - y0

    def _union_bbox(self, components) -> Tuple[int, int, int, int]:
        x0 = min(component["x"] for component in components)
        y0 = min(component["y"] for component in components)
        x1 = max(component["x"] + component["w"] for component in components)
        y1 = max(component["y"] + component["h"] for component in components)
        return x0, y0, x1 - x0, y1 - y0

    def _compute_zoning(self, mask: np.ndarray, grid: int) -> np.ndarray:
        zones = []
        h, w = mask.shape
        for row in range(grid):
            y0 = int(round(row * h / grid))
            y1 = int(round((row + 1) * h / grid))
            for col in range(grid):
                x0 = int(round(col * w / grid))
                x1 = int(round((col + 1) * w / grid))
                cell = mask[y0:y1, x0:x1]
                zones.append(float(np.mean(cell)) if cell.size else 0.0)
        return np.asarray(zones, dtype=np.float32)

    def _downsample_projection(self, projection: np.ndarray, length: int) -> np.ndarray:
        if projection.size == length:
            return projection.astype(np.float32)
        resized = cv2.resize(projection.astype(np.float32).reshape(1, -1), (length, 1), interpolation=cv2.INTER_AREA)
        return resized.flatten().astype(np.float32)

    def _compute_hu_moments(self, mask: np.ndarray) -> np.ndarray:
        moments = cv2.moments(mask)
        hu = cv2.HuMoments(moments).flatten()
        hu = np.sign(hu) * np.log1p(np.abs(hu))
        return hu.astype(np.float32)

    def _compute_orientation_histogram(self, binary: np.ndarray, bins: int) -> np.ndarray:
        edges = cv2.Canny(binary, 40, 120)
        if np.count_nonzero(edges) == 0:
            return np.zeros(bins, dtype=np.float32)

        grad_x = cv2.Sobel(binary, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(binary, cv2.CV_32F, 0, 1, ksize=3)
        magnitude, angle = cv2.cartToPolar(grad_x, grad_y, angleInDegrees=True)
        mask = edges > 0
        hist, _ = np.histogram(angle[mask], bins=bins, range=(0.0, 360.0), weights=magnitude[mask])
        hist = hist.astype(np.float32)
        norm = float(np.sum(hist))
        if norm > 0:
            hist /= norm
        return hist

    def _compute_topology(self, binary: np.ndarray, mask: np.ndarray) -> Dict[str, float]:
        ys, xs = np.where(mask > 0)
        bbox_fill = 0.0
        aspect_ratio = 1.0
        centroid_x = 0.5
        centroid_y = 0.5
        if len(xs) > 0:
            x0 = int(xs.min())
            y0 = int(ys.min())
            x1 = int(xs.max()) + 1
            y1 = int(ys.max()) + 1
            bbox_area = max(1, (x1 - x0) * (y1 - y0))
            bbox_fill = float(np.mean(mask[y0:y1, x0:x1]))
            aspect_ratio = float((x1 - x0) / max(1, (y1 - y0)))
            centroid_x = float(np.mean(xs) / binary.shape[1])
            centroid_y = float(np.mean(ys) / binary.shape[0])

        num_labels, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        component_areas = stats[1:, cv2.CC_STAT_AREA] if num_labels > 1 else np.array([], dtype=np.int32)
        component_count = int(len(component_areas))
        dominant_share = float(component_areas.max() / max(1, np.sum(component_areas))) if component_areas.size else 0.0

        holes = self._count_holes(mask)
        skeleton = self._extract_skeleton(binary)
        end_points = len(self._detect_end_points(skeleton))
        branch_points = len(self._detect_branch_points(skeleton))

        return {
            "ink_ratio": float(np.mean(mask)),
            "bbox_fill": float(bbox_fill),
            "aspect_ratio": float(aspect_ratio),
            "centroid_x": float(centroid_x),
            "centroid_y": float(centroid_y),
            "component_count": float(component_count),
            "dominant_share": float(dominant_share),
            "holes": float(holes),
            "end_points": float(end_points),
            "branch_points": float(branch_points),
        }

    def _count_holes(self, mask: np.ndarray) -> int:
        contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        if hierarchy is None:
            return 0
        count = 0
        for idx in range(len(contours)):
            parent = hierarchy[0][idx][3]
            if parent >= 0 and cv2.contourArea(contours[idx]) >= 8:
                count += 1
        return count

    def _extract_skeleton(self, binary: np.ndarray) -> np.ndarray:
        image = ((255 - binary) > 0).astype(np.uint8)
        skeleton = np.zeros(image.shape, dtype=np.uint8)
        element = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
        working = image.copy()
        for _ in range(96):
            eroded = cv2.erode(working, element)
            dilated = cv2.dilate(eroded, element)
            temp = cv2.subtract(working, dilated)
            skeleton = cv2.bitwise_or(skeleton, temp)
            working = eroded
            if cv2.countNonZero(working) == 0:
                break
        return skeleton * 255

    def _detect_end_points(self, skeleton: np.ndarray):
        result = []
        skel = (skeleton > 0).astype(np.uint8)
        h, w = skel.shape
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                if skel[y, x]:
                    neighbors = int(np.sum(skel[y - 1 : y + 2, x - 1 : x + 2]) - 1)
                    if neighbors == 1:
                        result.append((x, y))
        return result

    def _detect_branch_points(self, skeleton: np.ndarray):
        result = []
        skel = (skeleton > 0).astype(np.uint8)
        h, w = skel.shape
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                if skel[y, x]:
                    neighbors = int(np.sum(skel[y - 1 : y + 2, x - 1 : x + 2]) - 1)
                    if neighbors >= 3:
                        result.append((x, y))
        return result

    def _vector_similarity(self, left: np.ndarray, right: np.ndarray) -> float:
        if left.size == 0 or right.size == 0:
            return 0.0
        diff = float(np.mean(np.abs(left - right)))
        return max(0.0, min(1.0, 1.0 - diff))

    def _hu_similarity(self, left: np.ndarray, right: np.ndarray) -> float:
        diff = float(np.mean(np.abs(left - right)))
        return max(0.0, min(1.0, 1.0 / (1.0 + diff * 1.8)))

    def _topology_similarity(self, left: Dict[str, float], right: Dict[str, float]) -> float:
        def bounded(diff: float, scale: float) -> float:
            return min(1.0, abs(diff) / scale)

        log_aspect = 0.0
        if left["aspect_ratio"] > 0 and right["aspect_ratio"] > 0:
            log_aspect = min(1.0, abs(np.log(left["aspect_ratio"] / right["aspect_ratio"])) / np.log(2.6))

        penalties = {
            "aspect": log_aspect,
            "components": bounded(left["component_count"] - right["component_count"], 6.0),
            "end_points": bounded(left["end_points"] - right["end_points"], 8.0),
            "branch_points": bounded(left["branch_points"] - right["branch_points"], 6.0),
            "holes": bounded(left["holes"] - right["holes"], 3.0),
            "centroid_x": bounded(left["centroid_x"] - right["centroid_x"], 0.32),
            "centroid_y": bounded(left["centroid_y"] - right["centroid_y"], 0.32),
            "bbox_fill": bounded(left["bbox_fill"] - right["bbox_fill"], 0.45),
            "dominant_share": bounded(left["dominant_share"] - right["dominant_share"], 0.55),
        }
        weights = {
            "aspect": 1.1,
            "components": 0.7,
            "end_points": 0.9,
            "branch_points": 0.9,
            "holes": 0.8,
            "centroid_x": 0.7,
            "centroid_y": 0.7,
            "bbox_fill": 0.9,
            "dominant_share": 0.6,
        }
        total = sum(weights.values())
        penalty = sum(weights[key] * penalties[key] for key in penalties) / total
        return float(max(0.0, min(1.0, 1.0 - penalty)))

    def _ensure_binary(self, image: np.ndarray) -> np.ndarray:
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if np.mean(binary == 0) > 0.55:
            binary = 255 - binary
        return binary.astype(np.uint8)

    def _is_binary_like(self, image: np.ndarray) -> bool:
        unique = np.unique(image)
        return len(unique) <= 3 and set(int(value) for value in unique.tolist()).issubset({0, 1, 254, 255})

    def _build_core_mask(self, foreground: np.ndarray) -> np.ndarray:
        """Keep only thick brush-stroke cores for component scoring."""
        kernels = [(5, 5), (3, 3)]
        for size in kernels:
            eroded = cv2.erode(foreground, np.ones(size, dtype=np.uint8), iterations=1)
            if int(np.sum(eroded)) > max(20, int(foreground.size * 0.001)):
                return eroded
        return foreground

    def _extract_components(self, mask: np.ndarray, shape, min_area: int):
        image_h, image_w = shape
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
        if num_labels <= 1:
            return labels, []

        valid_areas = stats[1:, cv2.CC_STAT_AREA]
        valid_areas = valid_areas[valid_areas >= min_area]
        valid_total = float(np.sum(valid_areas)) if valid_areas.size else 0.0
        if valid_total <= 0:
            return labels, []

        components = []
        for label in range(1, num_labels):
            area = int(stats[label, cv2.CC_STAT_AREA])
            if area < min_area:
                continue
            x = int(stats[label, cv2.CC_STAT_LEFT])
            y = int(stats[label, cv2.CC_STAT_TOP])
            w = int(stats[label, cv2.CC_STAT_WIDTH])
            h = int(stats[label, cv2.CC_STAT_HEIGHT])
            cx = float(centroids[label][0])
            cy = float(centroids[label][1])
            touches_edge = x <= 1 or y <= 1 or (x + w) >= image_w - 1 or (y + h) >= image_h - 1
            if touches_edge and (w >= image_w * 0.65 or h >= image_h * 0.65):
                continue

            center_dx = (cx - image_w / 2.0) / max(1.0, image_w / 2.0)
            center_dy = (cy - image_h / 2.0) / max(1.0, image_h / 2.0)
            center_distance = float(np.hypot(center_dx, center_dy))
            bbox_fill = area / max(1, w * h)
            area_share = area / valid_total
            score = area_share * 0.62 + (1.0 - center_distance) * 0.28 + min(0.10, bbox_fill * 0.10)
            if touches_edge:
                score -= 0.20
                if area_share < 0.30:
                    score -= 0.10

            components.append(
                {
                    "label": label,
                    "area": area,
                    "x": x,
                    "y": y,
                    "w": w,
                    "h": h,
                    "cx": cx,
                    "cy": cy,
                    "area_share": area_share,
                    "center_distance": center_distance,
                    "bbox_fill": bbox_fill,
                    "touches_edge": touches_edge,
                    "score": score,
                }
            )

        return labels, components


character_geometry_service = CharacterGeometryService()
