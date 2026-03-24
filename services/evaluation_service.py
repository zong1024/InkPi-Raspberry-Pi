"""
InkPi 书法评测系统 - 评测服务

四维度评分（针对毛笔字优化）：
- 结构：字形匀称程度、凸包矩形度、留白分布
- 笔画：骨架提取分析、边缘复杂度、笔画粗细变化（提按效果）
- 平衡：精确重心计算、中轴线偏移量
- 韵律：行笔流畅度、连通性分析、飞白效果

毛笔字专属特征：
- 笔画粗细变化率（Stroke Width Variance）- 反映提按
- 笔锋锐度（Brush Tip Sharpness）- 起收笔形态
- 飞白密度（Flying White Density）- 干笔效果
- 墨色渐变（Ink Gradient）- 浓淡变化
"""
import numpy as np
import cv2
from typing import Dict, List, Tuple, Optional
import random
import logging
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import EVALUATION_CONFIG, FEEDBACK_TEMPLATES
from models.evaluation_result import EvaluationResult
from services.recognition_service import recognition_service
from services.style_classification_service import style_classification_service
from services.siamese_engine import siamese_engine
from services.evaluation_service_v3 import hybrid_evaluation_service


class EvaluationService:
    """评测服务 - 毛笔字专项优化版"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config = EVALUATION_CONFIG
        self.dimensions = self.config["dimensions"]
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
        """
        执行评测分析
        
        Args:
            processed_image: 预处理后的图像
            original_image_path: 原始图像路径
            processed_image_path: 处理后图像路径
            character_name: 字符名称
            enable_recognition: 是否启用汉字识别
            
        Returns:
            EvaluationResult 评测结果
        """
        self.logger.info("开始毛笔字评测分析...")
        
        # 汉字识别（如果启用且未提供字符名称）
        recognized_char = None
        recognition_confidence = 0.0
        if (
            enable_recognition
            and character_name is None
            and recognition_service.is_model_loaded()
        ):
            try:
                recognition_result = recognition_service.recognize(processed_image)
                recognized_char = recognition_result.character
                recognition_confidence = recognition_result.confidence
                self.logger.info(f"汉字识别: {recognized_char} (置信度: {recognition_confidence:.2%})")
            except Exception as e:
                self.logger.warning(f"汉字识别失败: {e}")
        
        # 使用识别结果或提供的字符名称
        final_character = character_name or (
            recognized_char if recognition_confidence >= 0.5 else None
        )
        
        # 书法风格分类
        style = None
        style_confidence = None
        if style_classification_service.is_model_loaded():
            try:
                style, confidence, _ = style_classification_service.classify(processed_image)
                style_confidence = confidence
                self.logger.info(f"风格分类: {style} (置信度: {confidence:.2%})")
            except Exception as e:
                self.logger.warning(f"风格分类失败: {e}")

        effective_style = style or template_style

        if prefer_hybrid and siamese_engine.is_model_loaded():
            texture_input = self._prepare_texture_image(
                texture_image if texture_image is not None else processed_image,
                processed_image.shape[:2]
            )
            result = hybrid_evaluation_service.evaluate(
                binary_image=processed_image,
                texture_image=texture_input,
                original_image_path=original_image_path,
                character_name=final_character,
                template_style=effective_style,
            )
            result.processed_image_path = processed_image_path
            result.style = style
            result.style_confidence = style_confidence

            if result.character_name and recognition_confidence >= 0.5:
                result.feedback = f"【识别结果: {result.character_name}】\n{result.feedback}"

            self.logger.info(f"混合评测完成: 总分={result.total_score}")
            return result
        
        # 计算四维评分
        detail_scores = self._calculate_scores(processed_image)
        
        # 计算总分
        total_score = sum(detail_scores.values()) // len(detail_scores)
        
        # 生成反馈
        feedback = self._generate_feedback(total_score, detail_scores)
        
        # 如果识别成功，添加到反馈中
        if final_character and recognition_confidence > 0.5:
            feedback = f"【识别结果: {final_character}】\n{feedback}"
        
        # 创建评测结果
        result = EvaluationResult(
            total_score=total_score,
            detail_scores=detail_scores,
            feedback=feedback,
            timestamp=datetime.now(),
            image_path=original_image_path,
            processed_image_path=processed_image_path,
            character_name=final_character,
            style=style,
            style_confidence=style_confidence
        )
        
        self.logger.info(f"评测完成: 总分={total_score}")
        return result

    def _prepare_texture_image(self, image: np.ndarray, target_shape: Tuple[int, int]) -> np.ndarray:
        """准备混合评测所需的灰度纹理图。"""
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
        """
        计算四维评分
        
        Args:
            image: 预处理后的图像
            
        Returns:
            四维评分字典
        """
        # 确保是灰度图
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
            
        # 二值化（如果还不是）
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        
        # 提取墨迹掩码
        ink_mask = binary == 0
        
        # 提取高级特征（包含毛笔字专属特征）
        features = self._extract_advanced_features(binary, ink_mask, gray)
        
        # 根据特征计算各维度分数
        scores = {}
        
        # 结构：基于凸包矩形度 + 弹性网格留白分析
        scores["结构"] = self._score_structure_advanced(features)
        
        # 笔画：基于骨架分析 + 边缘复杂度 + 毛笔字专属特征
        scores["笔画"] = self._score_stroke_brush(features, binary)
        
        # 平衡：基于精确重心公式
        scores["平衡"] = self._score_balance_advanced(features)
        
        # 韵律：基于连通性 + 行笔流畅度 + 飞白效果
        scores["韵律"] = self._score_rhythm_brush(features)
        
        return scores
    
    def _extract_advanced_features(self, binary: np.ndarray, ink_mask: np.ndarray, gray: np.ndarray = None) -> Dict[str, float]:
        """
        提取高级图像特征（针对毛笔字优化）
        
        Args:
            binary: 二值化图像
            ink_mask: 墨迹掩码
            gray: 原始灰度图（用于墨色分析）
            
        Returns:
            特征字典
        """
        h, w = binary.shape
        total_pixels = binary.size
        ink_count = np.sum(ink_mask)
        
        features = {}
        
        # ============ 基础特征 ============
        features["ink_ratio"] = ink_count / total_pixels
        features["image_width"] = w
        features["image_height"] = h
        
        # ============ 1. 精确重心计算 ============
        if ink_count > 0:
            y_coords, x_coords = np.where(ink_mask)
            
            features["center_x"] = np.mean(x_coords) / w
            features["center_y"] = np.mean(y_coords) / h
            features["weighted_center_x"] = np.average(x_coords, weights=np.ones(len(x_coords))) / w
            features["weighted_center_y"] = np.average(y_coords, weights=np.ones(len(y_coords))) / h
        else:
            features["center_x"] = 0.5
            features["center_y"] = 0.5
            features["weighted_center_x"] = 0.5
            features["weighted_center_y"] = 0.5
        
        features["center_offset"] = np.sqrt(
            (features["center_x"] - 0.5) ** 2 + 
            (features["center_y"] - 0.5) ** 2
        )
        
        # ============ 2. 凸包矩形度分析 ============
        if ink_count > 0:
            contours, _ = cv2.findContours(
                (255 - binary).astype(np.uint8), 
                cv2.RETR_EXTERNAL, 
                cv2.CHAIN_APPROX_SIMPLE
            )
            
            if contours:
                all_points = np.vstack(contours)
                convex_hull = cv2.convexHull(all_points)
                hull_perimeter = cv2.arcLength(convex_hull, True)
                hull_area = cv2.contourArea(convex_hull)
                
                min_rect = cv2.minAreaRect(convex_hull)
                rect_perimeter = 2 * (min_rect[1][0] + min_rect[1][1])
                
                if rect_perimeter > 0:
                    features["convex_rectangularity"] = hull_perimeter / rect_perimeter
                else:
                    features["convex_rectangularity"] = 0.5
                    
                if ink_count > 0:
                    features["hull_area_ratio"] = hull_area / ink_count
                else:
                    features["hull_area_ratio"] = 1.0
            else:
                features["convex_rectangularity"] = 0.5
                features["hull_area_ratio"] = 1.0
        else:
            features["convex_rectangularity"] = 0.5
            features["hull_area_ratio"] = 1.0
        
        # ============ 3. 弹性网格留白分析 ============
        grid_size = 3
        cell_h, cell_w = h // grid_size, w // grid_size
        whitespace_ratios = []
        
        for i in range(grid_size):
            for j in range(grid_size):
                y1, y2 = i * cell_h, (i + 1) * cell_h
                x1, x2 = j * cell_w, (j + 1) * cell_w
                
                cell = ink_mask[y1:y2, x1:x2]
                cell_area = cell.size
                whitespace_ratio = 1 - (np.sum(cell) / cell_area)
                whitespace_ratios.append(whitespace_ratio)
        
        features["whitespace_variance"] = np.var(whitespace_ratios)
        features["whitespace_std"] = np.std(whitespace_ratios)
        
        # ============ 4. 骨架提取 ============
        skeleton = self._extract_skeleton(binary)
        features["skeleton_length"] = np.sum(skeleton > 0)
        
        branch_points = self._detect_branch_points(skeleton)
        features["branch_point_count"] = len(branch_points)
        
        end_points = self._detect_end_points(skeleton)
        features["end_point_count"] = len(end_points)
        
        # ============ 5. 连通分量分析 ============
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
            255 - binary, connectivity=8
        )
        features["num_components"] = num_labels - 1
        
        if num_labels > 1:
            component_areas = stats[1:, cv2.CC_STAT_AREA]
            features["max_component_ratio"] = np.max(component_areas) / max(ink_count, 1)
            features["component_area_std"] = np.std(component_areas)
        else:
            features["max_component_ratio"] = 0
            features["component_area_std"] = 0
        
        # ============ 6. 边缘分析 ============
        edges = cv2.Canny(binary, 50, 150)
        features["edge_density"] = np.sum(edges > 0) / total_pixels
        
        # ============ 7. 投影分布 ============
        h_projection = np.sum(ink_mask, axis=1)
        v_projection = np.sum(ink_mask, axis=0)
        
        h_mean = np.mean(h_projection) + 1e-6
        v_mean = np.mean(v_projection) + 1e-6
        
        features["h_proj_std"] = np.std(h_projection) / h_mean
        features["v_proj_std"] = np.std(v_projection) / v_mean
        
        h_proj_norm = h_projection / (np.max(h_projection) + 1e-6)
        v_proj_norm = v_projection / (np.max(v_projection) + 1e-6)
        
        h_flipped = np.flip(h_proj_norm)
        features["h_symmetry"] = 1 - np.mean(np.abs(h_proj_norm - h_flipped))
        
        v_flipped = np.flip(v_proj_norm)
        features["v_symmetry"] = 1 - np.mean(np.abs(v_proj_norm - v_flipped))
        
        # ============ 8. 毛笔字专属特征 ============
        brush_features = self._extract_brush_features(binary, ink_mask, skeleton, gray)
        features.update(brush_features)
        
        self.logger.debug(f"特征提取完成: 重心=({features['center_x']:.3f}, {features['center_y']:.3f}), "
                         f"笔画粗细方差={features.get('stroke_width_variance', 0):.4f}, "
                         f"飞白密度={features.get('flying_white_density', 0):.4f}")
        
        return features
    
    def _extract_brush_features(self, binary: np.ndarray, ink_mask: np.ndarray, 
                                 skeleton: np.ndarray, gray: np.ndarray = None) -> Dict[str, float]:
        """
        提取毛笔字专属特征
        
        Args:
            binary: 二值化图像
            ink_mask: 墨迹掩码
            skeleton: 骨架图像
            gray: 原始灰度图
            
        Returns:
            毛笔字专属特征字典
        """
        features = {}
        h, w = binary.shape
        ink_count = np.sum(ink_mask)
        
        # ============ 8.1 笔画粗细变化率（Stroke Width Variance） ============
        # 毛笔字特点：提按产生粗细变化，变化率反映控笔能力
        stroke_widths = self._measure_stroke_widths(binary, ink_mask, skeleton)
        
        if len(stroke_widths) > 0:
            # 粗细方差 - 反映提按效果
            features["stroke_width_variance"] = np.var(stroke_widths)
            # 粗细范围 - 最大最小差
            features["stroke_width_range"] = np.max(stroke_widths) - np.min(stroke_widths)
            # 粗细变化系数
            mean_width = np.mean(stroke_widths)
            features["stroke_width_cv"] = np.std(stroke_widths) / (mean_width + 1e-6)
            features["mean_stroke_width"] = mean_width
        else:
            features["stroke_width_variance"] = 0
            features["stroke_width_range"] = 0
            features["stroke_width_cv"] = 0
            features["mean_stroke_width"] = 0
        
        # ============ 8.2 笔锋检测（Brush Tip Detection） ============
        # 检测起笔和收笔的锐度
        tip_sharpness = self._detect_brush_tip_sharpness(binary, ink_mask, skeleton)
        features["tip_sharpness"] = tip_sharpness
        
        # ============ 8.3 飞白检测（Flying White Detection） ============
        # 飞白是快速运笔产生的干笔效果，表现为笔画内部的细小白点
        flying_white = self._detect_flying_white(binary, ink_mask, gray)
        features["flying_white_density"] = flying_white["density"]
        features["flying_white_quality"] = flying_white["quality"]
        
        # ============ 8.4 墨色分析（Ink Gradient） ============
        if gray is not None:
            ink_values = gray[ink_mask]
            if len(ink_values) > 0:
                # 墨色均值（越低越浓）
                features["ink_intensity_mean"] = np.mean(ink_values)
                # 墨色方差（变化程度）
                features["ink_intensity_variance"] = np.var(ink_values)
                # 墨色梯度（浓淡变化）
                features["ink_gradient"] = self._calculate_ink_gradient(gray, ink_mask)
            else:
                features["ink_intensity_mean"] = 0
                features["ink_intensity_variance"] = 0
                features["ink_gradient"] = 0
        else:
            features["ink_intensity_mean"] = 0
            features["ink_intensity_variance"] = 0
            features["ink_gradient"] = 0
        
        # ============ 8.5 边缘毛刺分析 ============
        # 毛笔字边缘自然有毛刺，区分"好的毛刺"和"差的锯齿"
        edge_quality = self._analyze_brush_edge_quality(binary, ink_mask)
        features["edge_roughness"] = edge_quality["roughness"]
        features["edge_smoothness"] = edge_quality["smoothness"]
        
        return features
    
    def _measure_stroke_widths(self, binary: np.ndarray, ink_mask: np.ndarray, 
                                skeleton: np.ndarray) -> List[float]:
        """
        测量笔画粗细（使用距离变换）
        
        Args:
            binary: 二值化图像
            ink_mask: 墨迹掩码
            skeleton: 骨架图像
            
        Returns:
            笔画宽度列表
        """
        # 使用距离变换测量到边缘的距离
        dist_transform = cv2.distanceTransform(
            (255 - binary).astype(np.uint8), 
            cv2.DIST_L2, 
            5
        )
        
        # 在骨架位置采样笔画宽度
        skel_points = np.where(skeleton > 0)
        
        if len(skel_points[0]) == 0:
            return []
        
        # 采样骨架点上的距离值（即笔画半径）
        widths = []
        for y, x in zip(skel_points[0], skel_points[1]):
            if 0 <= y < dist_transform.shape[0] and 0 <= x < dist_transform.shape[1]:
                radius = dist_transform[y, x]
                if radius > 0:
                    widths.append(radius * 2)  # 直径 = 半径 * 2
        
        return widths
    
    def _detect_brush_tip_sharpness(self, binary: np.ndarray, ink_mask: np.ndarray,
                                     skeleton: np.ndarray) -> float:
        """
        检测笔锋锐度（起收笔形态）
        
        毛笔字特点：
        - 起笔有"藏锋"或"露锋"
        - 收笔有"回锋"或"出锋"
        - 笔锋应该锐利而不是圆钝
        
        Args:
            binary: 二值化图像
            ink_mask: 墨迹掩码
            skeleton: 骨架图像
            
        Returns:
            笔锋锐度评分 (0-1)
        """
        # 找到骨架端点（笔锋位置）
        end_points = self._detect_end_points(skeleton)
        
        if len(end_points) < 2:
            return 0.5
        
        sharpness_scores = []
        
        for x, y in end_points[:8]:  # 最多分析8个端点
            if not (0 <= y < binary.shape[0] and 0 <= x < binary.shape[1]):
                continue
            
            # 在端点附近分析形态
            radius = 10
            y1, y2 = max(0, y - radius), min(binary.shape[0], y + radius)
            x1, x2 = max(0, x - radius), min(binary.shape[1], x + radius)
            
            local_region = ink_mask[y1:y2, x1:x2]
            
            if local_region.size == 0:
                continue
            
            # 计算端点处的"尖锐度"
            # 锐利的笔锋应该有渐变收窄的形态
            local_ink_ratio = np.sum(local_region) / local_region.size
            
            # 笔锋区域应该较小且边缘锐利
            if local_ink_ratio < 0.5:
                sharpness_scores.append(1 - local_ink_ratio)
            else:
                sharpness_scores.append(0.3)  # 钝笔锋
        
        if len(sharpness_scores) > 0:
            return np.mean(sharpness_scores)
        return 0.5
    
    def _detect_flying_white(self, binary: np.ndarray, ink_mask: np.ndarray,
                              gray: np.ndarray = None) -> Dict[str, float]:
        """
        检测飞白效果
        
        飞白特征：
        - 笔画内部的小白点
        - 通常出现在快速运笔的区域
        - 是毛笔字的特殊艺术效果
        
        Args:
            binary: 二值化图像
            ink_mask: 墨迹掩码
            gray: 原始灰度图
            
        Returns:
            飞白特征字典
        """
        result = {"density": 0, "quality": 0.5}
        
        if gray is None:
            return result
        
        # 在墨迹区域内检测灰度变化
        ink_pixels = gray[ink_mask]
        
        if len(ink_pixels) < 100:
            return result
        
        # 飞白表现为墨迹内部的高灰度点
        mean_ink = np.mean(ink_pixels)
        std_ink = np.std(ink_pixels)
        
        # 检测"内部白点"（灰度明显高于周围墨迹）
        # 使用形态学操作找到笔画内部
        kernel = np.ones((5, 5), np.uint8)
        eroded = cv2.erode((ink_mask.astype(np.uint8) * 255), kernel, iterations=2)
        interior_mask = eroded > 0
        
        if np.sum(interior_mask) > 50:
            interior_gray = gray[interior_mask]
            # 内部灰度方差大表示有飞白
            interior_var = np.var(interior_gray)
            
            # 归一化飞白密度
            result["density"] = min(1, interior_var / 1000)
            
            # 飞白质量：适度的飞白是好的，过多或过少都不好
            optimal_density = 0.3
            result["quality"] = 1 - abs(result["density"] - optimal_density) / optimal_density
            result["quality"] = max(0, min(1, result["quality"]))
        
        return result
    
    def _calculate_ink_gradient(self, gray: np.ndarray, ink_mask: np.ndarray) -> float:
        """
        计算墨色梯度（浓淡变化）
        
        Args:
            gray: 灰度图像
            ink_mask: 墨迹掩码
            
        Returns:
            墨色梯度值
        """
        # 使用Sobel算子计算梯度
        grad_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        gradient_magnitude = np.sqrt(grad_x**2 + grad_y**2)
        
        # 只统计墨迹区域的梯度
        ink_gradient = gradient_magnitude[ink_mask]
        
        if len(ink_gradient) > 0:
            return np.mean(ink_gradient)
        return 0
    
    def _analyze_brush_edge_quality(self, binary: np.ndarray, ink_mask: np.ndarray) -> Dict[str, float]:
        """
        分析毛笔字边缘质量
        
        毛笔字边缘特点：
        - 自然有毛刺（与硬笔不同）
        - 好的边缘：毛刺有规律，体现笔锋
        - 差的边缘：锯齿严重，抖动明显
        
        Args:
            binary: 二值化图像
            ink_mask: 墨迹掩码
            
        Returns:
            边缘质量字典
        """
        result = {"roughness": 0, "smoothness": 0.5}
        
        # 计算边缘
        edges = cv2.Canny(binary, 50, 150)
        
        # 在墨迹边缘附近分析
        kernel = np.ones((3, 3), np.uint8)
        dilated_ink = cv2.dilate(ink_mask.astype(np.uint8), kernel, iterations=2)
        edge_region = dilated_ink & (~ink_mask.astype(np.uint8) | edges > 0)
        
        edge_pixels = np.sum(edge_region > 0)
        if edge_pixels > 0:
            # 边缘粗糙度：边缘像素与墨迹面积比
            result["roughness"] = edge_pixels / (np.sum(ink_mask) + 1)
            
            # 平滑度：粗糙度的倒数
            result["smoothness"] = 1 / (1 + result["roughness"] * 5)
        
        return result
    
    def _extract_skeleton(self, binary: np.ndarray) -> np.ndarray:
        """骨架提取 - 使用形态学细化算法"""
        if np.mean(binary) > 127:
            img = (255 - binary) // 255
        else:
            img = binary // 255
        
        skeleton = np.zeros(img.shape, dtype=np.uint8)
        temp = np.zeros(img.shape, dtype=np.uint8)
        element = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
        
        while True:
            eroded = cv2.erode(img, element)
            dilated = cv2.dilate(eroded, element)
            temp = cv2.subtract(img, dilated)
            skeleton = cv2.bitwise_or(skeleton, temp)
            img = eroded.copy()
            
            if cv2.countNonZero(img) == 0:
                break
        
        return skeleton * 255
    
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
    
    def _score_structure_advanced(self, features: Dict[str, float]) -> int:
        """评分：结构（字形匀称、凸包矩形度、留白分布）"""
        min_score, max_score = self.score_range
        score_range = max_score - min_score
        
        # 1. 凸包矩形度评分
        rect_score = features.get("convex_rectangularity", 0.5)
        rect_deviation = abs(rect_score - 0.8)
        rect_normalized = max(0, 1 - rect_deviation * 2)
        
        # 2. 留白均匀性评分（毛笔字留白可以更灵活）
        whitespace_var = features.get("whitespace_variance", 0.1)
        whitespace_score = max(0, 1 - whitespace_var * 4)  # 放宽容忍度
        
        # 3. 投影分布均匀性
        h_proj_std = features.get("h_proj_std", 1)
        v_proj_std = features.get("v_proj_std", 1)
        proj_uniformity = 1 - (h_proj_std + v_proj_std) / 5  # 放宽容忍度
        proj_uniformity = max(0, min(1, proj_uniformity))
        
        # 4. 墨迹占比合理性（毛笔字）
        ink_ratio = features.get("ink_ratio", 0.25)
        ideal_ratio = 0.28
        ratio_score = 1 - abs(ink_ratio - ideal_ratio) / (ideal_ratio * 1.5)
        ratio_score = max(0, min(1, ratio_score))
        
        weights = {
            "rect": 0.2,
            "whitespace": 0.3,
            "projection": 0.3,
            "ratio": 0.2
        }
        
        final_score = (
            rect_normalized * weights["rect"] +
            whitespace_score * weights["whitespace"] +
            proj_uniformity * weights["projection"] +
            ratio_score * weights["ratio"]
        )
        
        return int(final_score * score_range + min_score)
    
    def _score_stroke_brush(self, features: Dict[str, float], binary: np.ndarray) -> int:
        """
        评分：笔画（毛笔字专项）
        
        评估内容：
        - 传统：边缘复杂度、骨架分析
        - 毛笔专属：笔画粗细变化、笔锋锐度、飞白效果
        """
        min_score, max_score = self.score_range
        score_range = max_score - min_score
        
        # 1. 边缘复杂度
        edge_density = features.get("edge_density", 0.05)
        ideal_density = 0.10  # 毛笔字边缘更丰富
        density_score = 1 - abs(edge_density - ideal_density) / ideal_density
        density_score = max(0, min(1, density_score))
        
        # 2. 骨架分析
        skeleton_length = features.get("skeleton_length", 0)
        ink_count = np.sum(binary == 0)
        
        if ink_count > 0:
            skeleton_ratio = skeleton_length / ink_count
            ideal_skeleton_ratio = 0.12  # 毛笔字笔画更粗
            skeleton_score = 1 - abs(skeleton_ratio - ideal_skeleton_ratio) / ideal_skeleton_ratio
            skeleton_score = max(0, min(1, skeleton_score))
        else:
            skeleton_score = 0.5
        
        # 3. 笔画粗细变化率（毛笔字提按效果）
        stroke_width_cv = features.get("stroke_width_cv", 0)
        # 适度的变化是好的，表示有提按
        ideal_cv = 0.3
        cv_score = 1 - abs(stroke_width_cv - ideal_cv) / (ideal_cv * 2)
        cv_score = max(0, min(1, cv_score))
        
        # 4. 笔锋锐度
        tip_sharpness = features.get("tip_sharpness", 0.5)
        
        # 5. 飞白质量
        flying_white_quality = features.get("flying_white_quality", 0.5)
        
        # 6. 连通性评分
        components = features.get("num_components", 1)
        if components <= 1:
            connectivity_score = 1.0
        elif components <= 2:
            connectivity_score = 0.9
        elif components <= 4:
            connectivity_score = 0.75
        elif components <= 6:
            connectivity_score = 0.6
        else:
            connectivity_score = 0.4
        
        # 毛笔字专项权重
        weights = {
            "density": 0.15,
            "skeleton": 0.15,
            "stroke_cv": 0.20,      # 毛笔专属
            "tip_sharpness": 0.15,  # 毛笔专属
            "flying_white": 0.10,   # 毛笔专属
            "connectivity": 0.25
        }
        
        final_score = (
            density_score * weights["density"] +
            skeleton_score * weights["skeleton"] +
            cv_score * weights["stroke_cv"] +
            tip_sharpness * weights["tip_sharpness"] +
            flying_white_quality * weights["flying_white"] +
            connectivity_score * weights["connectivity"]
        )
        
        return int(final_score * score_range + min_score)
    
    def _score_balance_advanced(self, features: Dict[str, float]) -> int:
        """评分：平衡（精确重心计算、中轴线偏移）"""
        min_score, max_score = self.score_range
        score_range = max_score - min_score
        
        # 1. 重心偏移量（毛笔字可以更灵活）
        center_offset = features.get("center_offset", 0)
        balance_score = 1 - center_offset * 2.5  # 放宽容忍度
        balance_score = max(0, min(1, balance_score))
        
        # 2. 水平对称性
        h_symmetry = features.get("h_symmetry", 0.5)
        
        # 3. 垂直对称性
        v_symmetry = features.get("v_symmetry", 0.5)
        
        # 4. 重心坐标细分分析
        center_x = features.get("center_x", 0.5)
        center_y = features.get("center_y", 0.5)
        
        x_deviation = abs(center_x - 0.5)
        x_balance = 1 - x_deviation * 1.5
        
        y_deviation = abs(center_y - 0.5)
        y_balance = 1 - y_deviation * 1.5
        
        weights = {
            "center_offset": 0.35,
            "h_symmetry": 0.15,
            "v_symmetry": 0.15,
            "x_balance": 0.175,
            "y_balance": 0.175
        }
        
        final_score = (
            balance_score * weights["center_offset"] +
            h_symmetry * weights["h_symmetry"] +
            v_symmetry * weights["v_symmetry"] +
            x_balance * weights["x_balance"] +
            y_balance * weights["y_balance"]
        )
        
        return int(final_score * score_range + min_score)
    
    def _score_rhythm_brush(self, features: Dict[str, float]) -> int:
        """
        评分：韵律（毛笔字专项）
        
        评估内容：
        - 传统：连通性、流畅度
        - 毛笔专属：墨色变化、飞白效果
        """
        min_score, max_score = self.score_range
        score_range = max_score - min_score
        
        # 1. 最大连通分量占比
        max_component = features.get("max_component_ratio", 0.5)
        rhythm_score = min(1, max_component)
        
        # 2. 连通分量数量
        components = features.get("num_components", 10)
        if components <= 1:
            flow_score = 1.0
        elif components <= 2:
            flow_score = 0.9
        elif components <= 4:
            flow_score = 0.75
        elif components <= 6:
            flow_score = 0.6
        else:
            flow_score = 0.4
        
        # 3. 端点数量
        end_points = features.get("end_point_count", 0)
        if end_points >= 2 and end_points <= 10:
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
        
        # 5. 墨色变化（毛笔字韵律的重要体现）
        ink_gradient = features.get("ink_gradient", 0)
        # 适度的墨色变化体现韵律
        gradient_score = min(1, ink_gradient / 30)
        
        # 6. 飞白密度（体现运笔速度变化）
        flying_white_density = features.get("flying_white_density", 0)
        # 适度飞白是好的
        if flying_white_density < 0.2:
            fw_score = 0.6
        elif flying_white_density < 0.5:
            fw_score = 0.9
        else:
            fw_score = max(0.5, 1 - (flying_white_density - 0.5) * 2)
        
        # 毛笔字韵律专项权重
        weights = {
            "max_component": 0.20,
            "flow": 0.20,
            "endpoint": 0.15,
            "smoothness": 0.15,
            "ink_gradient": 0.15,    # 毛笔专属
            "flying_white": 0.15     # 毛笔专属
        }
        
        final_score = (
            rhythm_score * weights["max_component"] +
            flow_score * weights["flow"] +
            endpoint_score * weights["endpoint"] +
            smoothness * weights["smoothness"] +
            gradient_score * weights["ink_gradient"] +
            fw_score * weights["flying_white"]
        )
        
        return int(final_score * score_range + min_score)
    
    def _generate_feedback(self, total_score: int, detail_scores: Dict[str, int]) -> str:
        """生成反馈文案"""
        templates = FEEDBACK_TEMPLATES
        excellent_threshold = self.config["excellent_threshold"]
        good_threshold = self.config["good_threshold"]
        
        if total_score >= excellent_threshold:
            feedback = random.choice(templates["excellent"])
        elif total_score >= good_threshold:
            min_dim = min(detail_scores, key=detail_scores.get)
            suggestion = templates["good"].get(min_dim, "继续练习，保持进步！")
            feedback = f"良好！{suggestion}"
        else:
            feedback = random.choice(templates["needs_work"])
            
        return feedback


# 创建全局服务实例
evaluation_service = EvaluationService()
