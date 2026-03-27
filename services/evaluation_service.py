"""Recognition-aware evaluation service for InkPi."""

from __future__ import annotations

from datetime import datetime
import logging
import random
import sys
from pathlib import Path
from typing import Dict, Tuple

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import EVALUATION_CONFIG, FEEDBACK_TEMPLATES
from models.evaluation_result import EvaluationResult
from services.evaluation_service_v3 import hybrid_evaluation_service
from services.recognition_flow_service import recognition_flow_service
from services.siamese_engine import siamese_engine


class EvaluationService:
    """Recognition-aware calligraphy scoring service."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config = EVALUATION_CONFIG
        self.dimensions = ["结构", "笔画", "平衡", "韵律"]
        self.score_range = self.config["score_range"]

    def evaluate(
        self,
        processed_image: np.ndarray,
        original_image_path: str = None,
        processed_image_path: str = None,
        character_name: str = None,
        enable_recognition: bool = True,
        texture_image: np.ndarray = None,
        template_style: str = "楷书",
        prefer_hybrid: bool = True,
    ) -> EvaluationResult:
        """Run template-based scoring when possible, otherwise fall back to generic scoring."""
        self.logger.info("开始毛笔字评测分析...")

        recognition_info = None
        final_character = character_name
        recognition_confidence = 1.0 if character_name else 0.0
        effective_style = template_style or "楷书"
        style_confidence = 1.0 if template_style else None
        score_mode = "template"
        score_explanation = "已使用本地模板和结构对比模型评分。"

        if enable_recognition or character_name is not None:
            recognition_input = texture_image if texture_image is not None else processed_image
            recognition_info = recognition_flow_service.analyze(
                recognition_input,
                requested_character=character_name,
                requested_style=template_style,
            )
            final_character = recognition_info.character_name
            recognition_confidence = recognition_info.recognition_confidence
            effective_style = recognition_info.style or effective_style
            style_confidence = recognition_info.style_confidence
            if not recognition_info.template_ready:
                score_mode = "generic"
                score_explanation = recognition_info.message or "当前字暂无本地模板，已切换到通用评分。"
            self.logger.info(
                "识别流水线完成: 字符=%s 置信度=%.2f 风格=%s 来源=%s 状态=%s",
                final_character,
                recognition_confidence,
                effective_style,
                recognition_info.recognition_source or "n/a",
                recognition_info.status,
            )

        use_template_scoring = (
            prefer_hybrid
            and siamese_engine.is_model_loaded()
            and (recognition_info is None or recognition_info.template_ready)
        )

        if use_template_scoring:
            texture_input = self._prepare_texture_image(
                texture_image if texture_image is not None else processed_image,
                processed_image.shape[:2],
            )
            result = hybrid_evaluation_service.evaluate(
                binary_image=processed_image,
                texture_image=texture_input,
                original_image_path=original_image_path,
                character_name=final_character,
                template_style=effective_style,
            )
            result.processed_image_path = processed_image_path
            result.style = effective_style
            result.style_confidence = style_confidence
            result.recognition_status = recognition_info.status if recognition_info else "matched"
            result.recognition_confidence = recognition_confidence
            result.score_mode = score_mode
            result.score_explanation = score_explanation
            result.feedback = self._decorate_feedback(
                base_feedback=result.feedback,
                character_name=result.character_name,
                recognition_confidence=recognition_confidence,
                recognition_info=recognition_info,
            )
            self.logger.info("模板评分完成: 总分=%s", result.total_score)
            return result

        detail_scores = self._calculate_scores(processed_image)
        total_score = int(round(sum(detail_scores.values()) / len(detail_scores)))
        feedback = self._generate_feedback(total_score, detail_scores)
        feedback = self._decorate_feedback(
            base_feedback=feedback,
            character_name=final_character,
            recognition_confidence=recognition_confidence,
            recognition_info=recognition_info,
        )

        result = EvaluationResult(
            total_score=total_score,
            detail_scores=detail_scores,
            feedback=feedback,
            timestamp=datetime.now(),
            image_path=original_image_path,
            processed_image_path=processed_image_path,
            character_name=final_character,
            style=effective_style,
            style_confidence=style_confidence,
            recognition_status=recognition_info.status if recognition_info else "matched",
            recognition_confidence=recognition_confidence,
            score_mode=score_mode,
            score_explanation=score_explanation,
        )
        self.logger.info("通用评分完成: 总分=%s", result.total_score)
        return result

    def _prepare_texture_image(self, image: np.ndarray, target_shape: Tuple[int, int]) -> np.ndarray:
        """Prepare a grayscale texture image for hybrid scoring."""
        if image is None:
            return np.ones(target_shape, dtype=np.uint8) * 255

        if len(image.shape) == 3:
            texture = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            texture = image.copy()

        target_h, target_w = target_shape
        if texture.shape[:2] != (target_h, target_w):
            texture = cv2.resize(texture, (target_w, target_h), interpolation=cv2.INTER_AREA)
        return texture

    def _calculate_scores(self, image: np.ndarray) -> Dict[str, int]:
        """Generic quality scoring for recognized characters without templates."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if np.mean(binary) < 127:
            binary = 255 - binary

        ink_mask = binary == 0
        if np.sum(ink_mask) == 0:
            return {label: 0 for label in self.dimensions}

        structure = self._score_structure(binary, ink_mask)
        stroke = self._score_stroke(gray, binary, ink_mask)
        balance = self._score_balance(ink_mask)
        rhythm = self._score_rhythm(binary, ink_mask)
        return {
            "结构": structure,
            "笔画": stroke,
            "平衡": balance,
            "韵律": rhythm,
        }

    def _score_structure(self, binary: np.ndarray, ink_mask: np.ndarray) -> int:
        ys, xs = np.where(ink_mask)
        x0, x1 = int(xs.min()), int(xs.max())
        y0, y1 = int(ys.min()), int(ys.max())
        box_w = max(1, x1 - x0 + 1)
        box_h = max(1, y1 - y0 + 1)
        box_area = box_w * box_h
        fill_ratio = np.sum(ink_mask) / max(1, box_area)
        image_ratio = np.sum(ink_mask) / max(1, binary.size)
        left = ink_mask[:, : ink_mask.shape[1] // 2]
        right = np.fliplr(ink_mask[:, ink_mask.shape[1] - left.shape[1] :])
        symmetry = 1.0 - np.mean(np.abs(left.astype(np.float32) - right.astype(np.float32)))
        aspect = box_w / max(1.0, box_h)
        aspect_score = 1.0 - min(abs(aspect - 1.0), 1.0)
        fill_score = 1.0 - min(abs(fill_ratio - 0.36) / 0.36, 1.0)
        density_score = 1.0 - min(abs(image_ratio - 0.16) / 0.16, 1.0)
        score = symmetry * 0.38 + aspect_score * 0.26 + fill_score * 0.20 + density_score * 0.16
        return int(np.clip(round(score * 100), 0, 100))

    def _score_stroke(self, gray: np.ndarray, binary: np.ndarray, ink_mask: np.ndarray) -> int:
        dist = cv2.distanceTransform((255 - binary).astype(np.uint8), cv2.DIST_L2, 5)
        stroke_values = dist[dist > 0]
        if stroke_values.size == 0:
            return 0
        mean_width = float(np.mean(stroke_values))
        width_cv = float(np.std(stroke_values) / max(mean_width, 1e-6))
        width_score = 1.0 - min(abs(width_cv - 0.55) / 0.55, 1.0)
        edges = cv2.Canny(gray, 50, 150)
        edge_density = float(np.sum(edges > 0) / max(1, gray.size))
        edge_score = 1.0 - min(abs(edge_density - 0.11) / 0.11, 1.0)
        ink_values = gray[ink_mask]
        ink_var = float(np.var(ink_values)) if ink_values.size else 0.0
        ink_score = min(ink_var / 1400.0, 1.0)
        score = width_score * 0.45 + edge_score * 0.30 + ink_score * 0.25
        return int(np.clip(round(score * 100), 0, 100))

    def _score_balance(self, ink_mask: np.ndarray) -> int:
        ys, xs = np.where(ink_mask)
        h, w = ink_mask.shape
        centroid_x = float(np.mean(xs) / max(1, w))
        centroid_y = float(np.mean(ys) / max(1, h))
        center_distance = np.hypot(centroid_x - 0.5, centroid_y - 0.5)
        center_score = 1.0 - min(center_distance / 0.28, 1.0)
        left_ratio = np.sum(ink_mask[:, : w // 2]) / max(1, np.sum(ink_mask))
        top_ratio = np.sum(ink_mask[: h // 2, :]) / max(1, np.sum(ink_mask))
        horizontal_score = 1.0 - min(abs(left_ratio - 0.5) / 0.28, 1.0)
        vertical_score = 1.0 - min(abs(top_ratio - 0.5) / 0.28, 1.0)
        score = center_score * 0.5 + horizontal_score * 0.25 + vertical_score * 0.25
        return int(np.clip(round(score * 100), 0, 100))

    def _score_rhythm(self, binary: np.ndarray, ink_mask: np.ndarray) -> int:
        num_labels, _, stats, _ = cv2.connectedComponentsWithStats((255 - binary).astype(np.uint8), 8)
        component_count = max(0, num_labels - 1)
        if component_count <= 1:
            component_score = 1.0
        elif component_count <= 3:
            component_score = 0.9
        elif component_count <= 6:
            component_score = 0.72
        else:
            component_score = max(0.25, 1.0 - component_count * 0.06)

        projection = np.sum(ink_mask, axis=1).astype(np.float32)
        if projection.size <= 1:
            flow_score = 0.5
        else:
            normalized = projection / max(1.0, projection.max())
            flow_score = 1.0 - min(float(np.mean(np.abs(np.diff(normalized)))) / 0.25, 1.0)

        areas = stats[1:, cv2.CC_STAT_AREA] if num_labels > 1 else np.array([])
        dominance = float(np.max(areas) / max(1, np.sum(areas))) if areas.size else 0.0
        dominance_score = min(max((dominance - 0.45) / 0.45, 0.0), 1.0)
        score = component_score * 0.4 + flow_score * 0.35 + dominance_score * 0.25
        return int(np.clip(round(score * 100), 0, 100))

    def _generate_feedback(self, total_score: int, detail_scores: Dict[str, int]) -> str:
        """Generate readable feedback text."""
        templates = FEEDBACK_TEMPLATES
        excellent_threshold = self.config["excellent_threshold"]
        good_threshold = self.config["good_threshold"]

        if total_score >= excellent_threshold:
            return random.choice(templates["excellent"])

        weakest_dimension = min(detail_scores, key=detail_scores.get)
        if total_score >= good_threshold:
            return f"良好。{templates['good'].get(weakest_dimension, '继续保持。')}"

        return random.choice(templates["needs_work"])

    def _decorate_feedback(
        self,
        base_feedback: str,
        character_name: str | None,
        recognition_confidence: float,
        recognition_info,
    ) -> str:
        """Add recognition/scoring context to the user-facing feedback."""
        if not character_name or recognition_confidence < 0.35:
            return base_feedback

        if recognition_info and recognition_info.status == "untemplated":
            prefix = (
                f"【全字识别】已识别为 {character_name}。"
                "当前字暂无本地模板，已切换到通用评分。"
            )
            return f"{prefix}\n{base_feedback}"

        if recognition_info and recognition_info.recognition_source == "user":
            return f"【锁定评测字】{character_name}\n{base_feedback}"

        return f"【识别结果】{character_name}\n{base_feedback}"


evaluation_service = EvaluationService()
