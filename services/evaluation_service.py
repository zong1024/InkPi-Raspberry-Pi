"""
InkPi 书法评测系统 - 评测服务

四维度评分：
- 结构：字形匀称程度、留白分布
- 笔画：起收笔到位程度、边缘平滑度
- 平衡：重心稳定性、中轴线偏移量
- 韵律：行笔流畅度、连贯性
"""
import numpy as np
import cv2
from typing import Dict, List, Tuple
import random
import logging
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import EVALUATION_CONFIG, FEEDBACK_TEMPLATES
from models.evaluation_result import EvaluationResult


class EvaluationService:
    """评测服务"""
    
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
        character_name: str = None
    ) -> EvaluationResult:
        """
        执行评测分析
        
        Args:
            processed_image: 预处理后的图像
            original_image_path: 原始图像路径
            processed_image_path: 处理后图像路径
            character_name: 字符名称
            
        Returns:
            EvaluationResult 评测结果
        """
        self.logger.info("开始评测分析...")
        
        # 计算四维评分
        detail_scores = self._calculate_scores(processed_image)
        
        # 计算总分
        total_score = sum(detail_scores.values()) // len(detail_scores)
        
        # 生成反馈
        feedback = self._generate_feedback(total_score, detail_scores)
        
        # 创建评测结果
        result = EvaluationResult(
            total_score=total_score,
            detail_scores=detail_scores,
            feedback=feedback,
            timestamp=datetime.now(),
            image_path=original_image_path,
            processed_image_path=processed_image_path,
            character_name=character_name
        )
        
        self.logger.info(f"评测完成: 总分={total_score}")
        return result
    
    def _calculate_scores(self, image: np.ndarray) -> Dict[str, int]:
        """
        计算四维评分
        
        Args:
            image: 预处理后的图像
            
        Returns:
            四维评分字典
        """
        min_score, max_score = self.score_range
        
        # 基于图像特征的启发式评分
        # 在真实AI模型集成前，使用模拟评分
        scores = {}
        
        # 分析图像特征
        features = self._extract_features(image)
        
        # 根据特征计算各维度分数
        # 结构：基于字形分布分析
        scores["结构"] = self._score_structure(features)
        
        # 笔画：基于边缘分析
        scores["笔画"] = self._score_stroke(features)
        
        # 平衡：基于重心分析
        scores["平衡"] = self._score_balance(features)
        
        # 韵律：基于连通性分析
        scores["韵律"] = self._score_rhythm(features)
        
        return scores
    
    def _extract_features(self, image: np.ndarray) -> Dict[str, float]:
        """
        提取图像特征
        
        Args:
            image: 预处理后的图像
            
        Returns:
            特征字典
        """
        # 确保是灰度图
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
            
        # 二值化（如果还不是）
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        
        # 墨迹像素
        ink_mask = binary == 0
        ink_count = np.sum(ink_mask)
        total_count = binary.size
        
        features = {}
        
        # 1. 墨迹占比
        features["ink_ratio"] = ink_count / total_count
        
        # 2. 边缘密度（Canny边缘检测）
        edges = cv2.Canny(binary, 50, 150)
        features["edge_density"] = np.sum(edges > 0) / total_count
        
        # 3. 重心位置
        if ink_count > 0:
            y_coords, x_coords = np.where(ink_mask)
            features["center_x"] = np.mean(x_coords) / binary.shape[1]
            features["center_y"] = np.mean(y_coords) / binary.shape[0]
        else:
            features["center_x"] = 0.5
            features["center_y"] = 0.5
            
        # 4. 中心偏移量
        features["center_offset"] = np.sqrt(
            (features["center_x"] - 0.5) ** 2 + 
            (features["center_y"] - 0.5) ** 2
        )
        
        # 5. 连通分量分析
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
            255 - binary, connectivity=8
        )
        features["num_components"] = num_labels - 1  # 排除背景
        
        # 6. 最大连通分量占比
        if num_labels > 1:
            component_areas = stats[1:, cv2.CC_STAT_AREA]
            features["max_component_ratio"] = np.max(component_areas) / ink_count
        else:
            features["max_component_ratio"] = 0
            
        # 7. 水平/垂直投影分布
        h_projection = np.sum(ink_mask, axis=1)  # 水平投影
        v_projection = np.sum(ink_mask, axis=0)  # 垂直投影
        
        # 投影的标准差（衡量分布均匀性）
        features["h_proj_std"] = np.std(h_projection) / (np.mean(h_projection) + 1e-6)
        features["v_proj_std"] = np.std(v_projection) / (np.mean(v_projection) + 1e-6)
        
        return features
    
    def _score_structure(self, features: Dict[str, float]) -> int:
        """评分：结构（字形匀称、留白分布）"""
        min_score, max_score = self.score_range
        
        # 基于投影分布均匀性
        uniformity = 1 - (features["h_proj_std"] + features["v_proj_std"]) / 4
        uniformity = max(0, min(1, uniformity))
        
        # 基于墨迹占比合理性
        ink_ratio = features["ink_ratio"]
        ideal_ratio = 0.15  # 理想墨迹占比
        ratio_score = 1 - abs(ink_ratio - ideal_ratio) / ideal_ratio
        ratio_score = max(0, min(1, ratio_score))
        
        # 综合评分
        score = (uniformity * 0.6 + ratio_score * 0.4) * (max_score - min_score) + min_score
        return int(score)
    
    def _score_stroke(self, features: Dict[str, float]) -> int:
        """评分：笔画（起收笔、边缘平滑度）"""
        min_score, max_score = self.score_range
        
        # 基于边缘密度（笔画复杂度）
        edge_density = features["edge_density"]
        ideal_density = 0.08
        density_score = 1 - abs(edge_density - ideal_density) / ideal_density
        density_score = max(0, min(1, density_score))
        
        # 基于连通性（笔画连贯性）
        components = features["num_components"]
        if components <= 1:
            connectivity_score = 1.0
        elif components <= 3:
            connectivity_score = 0.8
        elif components <= 5:
            connectivity_score = 0.6
        else:
            connectivity_score = 0.4
            
        # 综合评分
        score = (density_score * 0.5 + connectivity_score * 0.5) * (max_score - min_score) + min_score
        return int(score)
    
    def _score_balance(self, features: Dict[str, float]) -> int:
        """评分：平衡（重心稳定性、中轴线偏移）"""
        min_score, max_score = self.score_range
        
        # 基于重心偏移量
        center_offset = features["center_offset"]
        balance_score = 1 - center_offset * 4  # 放大偏移影响
        balance_score = max(0, min(1, balance_score))
        
        # 综合评分
        score = balance_score * (max_score - min_score) + min_score
        return int(score)
    
    def _score_rhythm(self, features: Dict[str, float]) -> int:
        """评分：韵律（行笔流畅度、连贯性）"""
        min_score, max_score = self.score_range
        
        # 基于最大连通分量占比
        max_component = features["max_component_ratio"]
        rhythm_score = max_component
        
        # 基于连通分量数量
        components = features["num_components"]
        if components <= 2:
            flow_score = 1.0
        elif components <= 4:
            flow_score = 0.8
        elif components <= 6:
            flow_score = 0.6
        else:
            flow_score = 0.4
            
        # 综合评分
        score = (rhythm_score * 0.5 + flow_score * 0.5) * (max_score - min_score) + min_score
        return int(score)
    
    def _generate_feedback(self, total_score: int, detail_scores: Dict[str, int]) -> str:
        """
        生成反馈文案
        
        Args:
            total_score: 总分
            detail_scores: 四维评分
            
        Returns:
            反馈文本
        """
        templates = FEEDBACK_TEMPLATES
        excellent_threshold = self.config["excellent_threshold"]
        good_threshold = self.config["good_threshold"]
        
        if total_score >= excellent_threshold:
            # 优秀评价
            feedback = random.choice(templates["excellent"])
        elif total_score >= good_threshold:
            # 良好评价 + 改进建议
            # 找出最低分维度
            min_dim = min(detail_scores, key=detail_scores.get)
            suggestion = templates["good"].get(min_dim, "继续练习，保持进步！")
            feedback = f"良好！{suggestion}"
        else:
            # 需加强练习
            feedback = random.choice(templates["needs_work"])
            
        return feedback


# 创建全局服务实例
evaluation_service = EvaluationService()