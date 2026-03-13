"""
InkPi 书法评测系统 - 混合评测服务 v3.0

混合架构核心：
- 孪生网络负责：结构分 + 平衡分
- OpenCV物理特征负责：笔画分 + 韵律分
- 融合打分器：输出最终四维分数

设计理念：
书法评测的本质是"对比问题"，不是"绝对评分问题"
"""
import numpy as np
import cv2
from typing import Dict, Tuple, Optional, List
import logging
import time
import gc
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import EVALUATION_CONFIG, FEEDBACK_TEMPLATES
from models.evaluation_result import EvaluationResult
from services.siamese_engine import siamese_engine
from services.template_manager import template_manager


class HybridEvaluationService:
    """
    混合评测服务 v3.0
    
    架构：
    ┌────────────────────────────────────────────────┐
    │                  双轨预处理                      │
    │                        ↓                        │
    │    ┌──────────────────┴──────────────────┐     │
    │    ↓                                     ↓     │
    │  Binary_Img                          Texture   │
    │    ↓                                     ↓     │
    │  [孪生网络]                        [OpenCV]   │
    │  结构分+平衡分                     笔画分+韵律  │
    │    ↓                                     ↓     │
    │    └──────────────────┬──────────────────┘     │
    │                        ↓                        │
    │                  融合打分器                     │
    └────────────────────────────────────────────────┘
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config = EVALUATION_CONFIG
        self.dimensions = self.config["dimensions"]
        self.score_range = self.config["score_range"]
    
    def evaluate(
        self,
        binary_image: np.ndarray,
        texture_image: np.ndarray,
        original_image_path: str = None,
        character_name: str = None,
        template_style: str = "楷书"
    ) -> EvaluationResult:
        """
        执行混合评测
        
        Args:
            binary_image: 二值化图像（用于孪生网络）
            texture_image: 灰度纹理图像（用于OpenCV特征）
            original_image_path: 原始图像路径
            character_name: 字符名称
            template_style: 字帖风格
            
        Returns:
            EvaluationResult 评测结果
        """
        self.logger.info("开始混合评测 (v3.0 Hybrid)...")
        total_start = time.perf_counter()
        
        # ============ 阶段1: 孪生网络评分 ============
        stage1_start = time.perf_counter()
        
        structure_score, balance_score = self._siamese_evaluate(
            binary_image, character_name, template_style
        )
        
        stage1_time = (time.perf_counter() - stage1_start) * 1000
        self.logger.info(f"[阶段1] 孪生网络评分: 结构={structure_score:.1f}, 平衡={balance_score:.1f} ({stage1_time:.1f}ms)")
        
        # ============ 阶段2: OpenCV物理特征评分 ============
        stage2_start = time.perf_counter()
        
        stroke_score, rhythm_score = self._opencv_evaluate(texture_image, binary_image)
        
        stage2_time = (time.perf_counter() - stage2_start) * 1000
        self.logger.info(f"[阶段2] OpenCV特征评分: 笔画={stroke_score:.1f}, 韵律={rhythm_score:.1f} ({stage2_time:.1f}ms)")
        
        # ============ 阶段3: 融合打分 ============
        detail_scores = {
            "结构": int(structure_score),
            "笔画": int(stroke_score),
            "平衡": int(balance_score),
            "韵律": int(rhythm_score)
        }
        
        # 总分计算
        total_score = sum(detail_scores.values()) // 4
        
        # 生成反馈
        feedback = self._generate_feedback(total_score, detail_scores)
        
        total_time = (time.perf_counter() - total_start) * 1000
        self.logger.info(f"[完成] 总分={total_score}, 耗时={total_time:.1f}ms")
        
        # 显式释放内存（树莓派优化）
        del binary_image, texture_image
        gc.collect()
        
        return EvaluationResult(
            total_score=total_score,
            detail_scores=detail_scores,
            feedback=feedback,
            timestamp=datetime.now(),
            image_path=original_image_path,
            processed_image_path=None,
            character_name=character_name,
            style=template_style,
            style_confidence=None
        )
    
    def _siamese_evaluate(
        self,
        binary_image: np.ndarray,
        character_name: str,
        template_style: str
    ) -> Tuple[float, float]:
        """
        孪生网络评分
        
        Args:
            binary_image: 二值化图像
            character_name: 字符名称
            template_style: 字帖风格
            
        Returns:
            Tuple[结构分, 平衡分]
        """
        # 获取对应字帖
        if character_name:
            template = template_manager.get_template(character_name, template_style)
        else:
            # 无字符名时，使用通用占位符
            template = template_manager._generate_default_template("字")
        
        # 孪生网络对比
        structure_score, balance_score = siamese_engine.compare_structure(
            binary_image, template
        )
        
        # 确保分数在有效范围内
        structure_score = max(0, min(100, structure_score))
        balance_score = max(0, min(100, balance_score))
        
        return structure_score, balance_score
    
    def _opencv_evaluate(
        self,
        texture_image: np.ndarray,
        binary_image: np.ndarray
    ) -> Tuple[float, float]:
        """
        OpenCV 物理特征评分
        
        Args:
            texture_image: 灰度纹理图像
            binary_image: 二值化图像
            
        Returns:
            Tuple[笔画分, 韵律分]
        """
        # 提取毛笔字专属特征
        features = self._extract_brush_features(texture_image, binary_image)
        
        # 计算笔画分
        stroke_score = self._score_stroke(features)
        
        # 计算韵律分
        rhythm_score = self._score_rhythm(features)
        
        # 确保分数在有效范围内
        min_score, max_score = self.score_range
        stroke_score = max(min_score, min(max_score, stroke_score))
        rhythm_score = max(min_score, min(max_score, rhythm_score))
        
        return stroke_score, rhythm_score
    
    def _extract_brush_features(
        self,
        texture_image: np.ndarray,
        binary_image: np.ndarray
    ) -> Dict[str, float]:
        """
        提取毛笔字物理特征
        
        Args:
            texture_image: 灰度纹理图像
            binary_image: 二值化图像
            
        Returns:
            特征字典
        """
        features = {}
        
        # 确保图像尺寸一致
        if texture_image.shape != binary_image.shape:
            texture_image = cv2.resize(texture_image, (binary_image.shape[1], binary_image.shape[0]))
        
        h, w = binary_image.shape
        total_pixels = binary_image.size
        
        # 墨迹掩码
        ink_mask = binary_image == 0
        ink_count = np.sum(ink_mask)
        features["ink_ratio"] = ink_count / total_pixels
        
        # ============ 笔画特征 ============
        
        # 1. 笔画粗细变化率（距离变换）
        dist_transform = cv2.distanceTransform(
            (255 - binary_image).astype(np.uint8),
            cv2.DIST_L2, 5
        )
        
        # 骨架提取
        skeleton = self._extract_skeleton(binary_image)
        skel_points = np.where(skeleton > 0)
        
        if len(skel_points[0]) > 0:
            widths = []
            for y, x in zip(skel_points[0], skel_points[1]):
                if 0 <= y < dist_transform.shape[0] and 0 <= x < dist_transform.shape[1]:
                    radius = dist_transform[y, x]
                    if radius > 0:
                        widths.append(radius * 2)
            
            if len(widths) > 0:
                features["stroke_width_variance"] = np.var(widths)
                features["mean_stroke_width"] = np.mean(widths)
                features["stroke_width_cv"] = np.std(widths) / (np.mean(widths) + 1e-6)
            else:
                features["stroke_width_variance"] = 0
                features["mean_stroke_width"] = 0
                features["stroke_width_cv"] = 0
        else:
            features["stroke_width_variance"] = 0
            features["mean_stroke_width"] = 0
            features["stroke_width_cv"] = 0
        
        # 2. 飞白检测（墨迹内部灰度方差）
        if ink_count > 100:
            ink_values = texture_image[ink_mask]
            features["flying_white_density"] = np.var(ink_values) / 1000
            features["ink_intensity_mean"] = np.mean(ink_values)
        else:
            features["flying_white_density"] = 0
            features["ink_intensity_mean"] = 0
        
        # 3. 墨色梯度（Sobel）
        grad_x = cv2.Sobel(texture_image, cv2.CV_64F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(texture_image, cv2.CV_64F, 0, 1, ksize=3)
        gradient_magnitude = np.sqrt(grad_x**2 + grad_y**2)
        
        if ink_count > 0:
            ink_gradient = gradient_magnitude[ink_mask]
            features["ink_gradient"] = np.mean(ink_gradient) if len(ink_gradient) > 0 else 0
        else:
            features["ink_gradient"] = 0
        
        # 4. 边缘分析
        edges = cv2.Canny(binary_image, 50, 150)
        features["edge_density"] = np.sum(edges > 0) / total_pixels
        
        # ============ 韵律特征 ============
        
        # 5. 连通分量分析
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
            255 - binary_image, connectivity=8
        )
        features["num_components"] = num_labels - 1
        
        if num_labels > 1:
            component_areas = stats[1:, cv2.CC_STAT_AREA]
            features["max_component_ratio"] = np.max(component_areas) / max(ink_count, 1)
        else:
            features["max_component_ratio"] = 0
        
        # 6. 骨架端点数量
        end_points = self._detect_end_points(skeleton)
        features["end_point_count"] = len(end_points)
        
        # 7. 骨架分支点数量
        branch_points = self._detect_branch_points(skeleton)
        features["branch_point_count"] = len(branch_points)
        features["skeleton_length"] = np.sum(skeleton > 0)
        
        return features
    
    def _extract_skeleton(self, binary: np.ndarray) -> np.ndarray:
        """骨架提取"""
        if np.mean(binary) > 127:
            img = (255 - binary) // 255
        else:
            img = binary // 255
        
        skeleton = np.zeros(img.shape, dtype=np.uint8)
        temp = np.zeros(img.shape, dtype=np.uint8)
        element = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
        
        for _ in range(100):  # 最多迭代100次
            eroded = cv2.erode(img, element)
            dilated = cv2.dilate(eroded, element)
            temp = cv2.subtract(img, dilated)
            skeleton = cv2.bitwise_or(skeleton, temp)
            img = eroded.copy()
            
            if cv2.countNonZero(img) == 0:
                break
        
        return skeleton * 255
    
    def _detect_end_points(self, skeleton: np.ndarray) -> List[Tuple[int, int]]:
        """检测骨架端点"""
        end_points = []
        h, w = skeleton.shape
        skel = (skeleton > 0).astype(np.uint8)
        
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                if skel[y, x] == 1:
                    neighbors = np.sum(skel[y-1:y+2, x-1:x+2]) - 1
                    if neighbors == 1:
                        end_points.append((x, y))
        
        return end_points
    
    def _detect_branch_points(self, skeleton: np.ndarray) -> List[Tuple[int, int]]:
        """检测骨架分支点"""
        branch_points = []
        h, w = skeleton.shape
        skel = (skeleton > 0).astype(np.uint8)
        
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                if skel[y, x] == 1:
                    neighbors = np.sum(skel[y-1:y+2, x-1:x+2]) - 1
                    if neighbors >= 3:
                        branch_points.append((x, y))
        
        return branch_points
    
    def _score_stroke(self, features: Dict[str, float]) -> float:
        """
        评分：笔画（毛笔字专项）
        
        评估内容：
        - 笔画粗细变化率（提按效果）
        - 飞白质量
        - 边缘复杂度
        """
        min_score, max_score = self.score_range
        score_range = max_score - min_score
        
        # 1. 笔画粗细变化率
        stroke_cv = features.get("stroke_width_cv", 0)
        ideal_cv = 0.3
        cv_score = 1 - abs(stroke_cv - ideal_cv) / (ideal_cv * 2)
        cv_score = max(0, min(1, cv_score))
        
        # 2. 飞白质量
        flying_white = features.get("flying_white_density", 0)
        if flying_white < 0.2:
            fw_score = 0.6
        elif flying_white < 0.5:
            fw_score = 0.9
        else:
            fw_score = max(0.5, 1 - (flying_white - 0.5) * 2)
        
        # 3. 边缘密度
        edge_density = features.get("edge_density", 0.05)
        ideal_density = 0.10
        density_score = 1 - abs(edge_density - ideal_density) / ideal_density
        density_score = max(0, min(1, density_score))
        
        # 4. 墨色梯度
        ink_gradient = features.get("ink_gradient", 0)
        gradient_score = min(1, ink_gradient / 30)
        
        # 加权融合
        weights = {
            "cv": 0.30,
            "flying_white": 0.25,
            "density": 0.25,
            "gradient": 0.20
        }
        
        final_score = (
            cv_score * weights["cv"] +
            fw_score * weights["flying_white"] +
            density_score * weights["density"] +
            gradient_score * weights["gradient"]
        )
        
        return final_score * score_range + min_score
    
    def _score_rhythm(self, features: Dict[str, float]) -> float:
        """
        评分：韵律（毛笔字专项）
        
        评估内容：
        - 连通性
        - 骨架流畅度
        - 墨色变化
        """
        min_score, max_score = self.score_range
        score_range = max_score - min_score
        
        # 1. 连通性
        max_component = features.get("max_component_ratio", 0.5)
        rhythm_score = min(1, max_component)
        
        # 2. 流畅度
        components = features.get("num_components", 10)
        if components <= 1:
            flow_score = 1.0
        elif components <= 2:
            flow_score = 0.9
        elif components <= 4:
            flow_score = 0.75
        else:
            flow_score = 0.5
        
        # 3. 端点数量
        end_points = features.get("end_point_count", 0)
        if 2 <= end_points <= 10:
            endpoint_score = 1.0
        elif end_points < 2:
            endpoint_score = 0.8
        else:
            endpoint_score = max(0.5, 1 - (end_points - 10) * 0.03)
        
        # 4. 骨架流畅度
        skeleton_length = features.get("skeleton_length", 0)
        branch_points = features.get("branch_point_count", 0)
        
        if skeleton_length > 0 and branch_points > 0:
            smoothness = min(1, skeleton_length / (branch_points * 40 + 80))
        else:
            smoothness = 0.5
        
        # 加权融合
        weights = {
            "max_component": 0.25,
            "flow": 0.25,
            "endpoint": 0.25,
            "smoothness": 0.25
        }
        
        final_score = (
            rhythm_score * weights["max_component"] +
            flow_score * weights["flow"] +
            endpoint_score * weights["endpoint"] +
            smoothness * weights["smoothness"]
        )
        
        return final_score * score_range + min_score
    
    def _generate_feedback(self, total_score: int, detail_scores: Dict[str, int]) -> str:
        """生成反馈文案"""
        templates = FEEDBACK_TEMPLATES
        excellent_threshold = self.config["excellent_threshold"]
        good_threshold = self.config["good_threshold"]
        
        # 找出最弱的维度
        min_dim = min(detail_scores, key=detail_scores.get)
        min_score = detail_scores[min_dim]
        
        # 基于最弱维度生成针对性建议
        suggestions = {
            "结构": "建议练习字形结构，注意笔画的相对位置和整体布局",
            "笔画": "建议加强笔画练习，注意起笔、行笔、收笔的力度变化",
            "平衡": "建议注意字的重心分布，保持左右、上下的平衡感",
            "韵律": "建议练习行笔的连贯性，注意笔画之间的呼应关系"
        }
        
        if total_score >= excellent_threshold:
            feedback = f"优秀！{random_choice(templates['excellent'])}"
        elif total_score >= good_threshold:
            suggestion = suggestions.get(min_dim, "继续练习，保持进步！")
            feedback = f"良好！{suggestion}"
        else:
            suggestion = suggestions.get(min_dim, "继续练习")
            feedback = f"需加强练习。{suggestion}"
        
        return feedback


def random_choice(options):
    """随机选择"""
    import random
    return random.choice(options)


# 创建全局服务实例
hybrid_evaluation_service = HybridEvaluationService()