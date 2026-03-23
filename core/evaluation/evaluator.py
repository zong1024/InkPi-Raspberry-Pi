"""
InkPi 书法评测系统 - 评测服务

四维度评分（针对毛笔字优化）：
- 结构：字形匀称程度、凸包矩形度、留白分布
- 笔画：骨架提取分析、边缘复杂度、笔画粗细变化（提按效果）
- 平衡：精确重心计算、中轴线偏移量
- 韵律：行笔流畅度、连通性分析、飞白效果
"""
import numpy as np
import cv2
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """评测结果数据类"""
    total_score: int
    detail_scores: Dict[str, int]
    feedback: str
    timestamp: datetime = None
    image_path: str = None
    character_name: str = None
    style: str = None
    style_confidence: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def to_dict(self) -> dict:
        return {
            "total_score": self.total_score,
            "detail_scores": self.detail_scores,
            "feedback": self.feedback,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "image_path": self.image_path,
            "character_name": self.character_name,
            "style": self.style,
            "style_confidence": self.style_confidence,
        }


class EvaluationService:
    """评测服务 - 毛笔字专项优化版"""
    
    # 评分维度
    DIMENSIONS = ["结构", "笔画", "平衡", "韵律"]
    
    # 评分范围
    SCORE_RANGE = (0, 100)
    
    # 质量等级阈值
    QUALITY_TARGETS = {
        "good": 1.0,
        "medium": 0.3,
        "poor": -1.0,
    }
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.min_score, self.max_score = self.SCORE_RANGE
    
    def evaluate(
        self,
        image: np.ndarray,
        character_name: str = None,
    ) -> EvaluationResult:
        """
        执行评测分析
        
        Args:
            image: 预处理后的图像 (灰度图或BGR)
            character_name: 字符名称 (可选)
            
        Returns:
            EvaluationResult 评测结果
        """
        self.logger.info("开始毛笔字评测分析...")
        
        # 计算四维评分
        detail_scores = self._calculate_scores(image)
        
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
            character_name=character_name,
        )
        
        self.logger.info(f"评测完成: 总分={total_score}")
        return result
    
    def _calculate_scores(self, image: np.ndarray) -> Dict[str, int]:
        """计算四维评分"""
        # 确保是灰度图
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # 二值化
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        
        # 提取墨迹掩码
        ink_mask = binary == 0
        
        # 提取特征
        features = self._extract_features(binary, ink_mask, gray)
        
        # 计算各维度分数
        scores = {
            "结构": self._score_structure(features),
            "笔画": self._score_stroke(features, binary),
            "平衡": self._score_balance(features),
            "韵律": self._score_rhythm(features),
        }
        
        return scores
    
    def _extract_features(self, binary: np.ndarray, ink_mask: np.ndarray, gray: np.ndarray) -> Dict[str, float]:
        """提取图像特征"""
        h, w = binary.shape
        total_pixels = binary.size
        ink_count = np.sum(ink_mask)
        
        features = {}
        
        # 基础特征
        features["ink_ratio"] = ink_count / total_pixels
        features["image_width"] = w
        features["image_height"] = h
        
        # 重心计算
        if ink_count > 0:
            y_coords, x_coords = np.where(ink_mask)
            features["center_x"] = np.mean(x_coords) / w
            features["center_y"] = np.mean(y_coords) / h
        else:
            features["center_x"] = 0.5
            features["center_y"] = 0.5
        
        features["center_offset"] = np.sqrt(
            (features["center_x"] - 0.5) ** 2 + 
            (features["center_y"] - 0.5) ** 2
        )
        
        # 凸包分析
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
                min_rect = cv2.minAreaRect(convex_hull)
                rect_perimeter = 2 * (min_rect[1][0] + min_rect[1][1])
                
                if rect_perimeter > 0:
                    features["convex_rectangularity"] = hull_perimeter / rect_perimeter
                else:
                    features["convex_rectangularity"] = 0.5
            else:
                features["convex_rectangularity"] = 0.5
        else:
            features["convex_rectangularity"] = 0.5
        
        # 网格留白分析
        grid_size = 3
        cell_h, cell_w = h // grid_size, w // grid_size
        whitespace_ratios = []
        
        for i in range(grid_size):
            for j in range(grid_size):
                y1, y2 = i * cell_h, (i + 1) * cell_h
                x1, x2 = j * cell_w, (j + 1) * cell_w
                cell = ink_mask[y1:y2, x1:x2]
                whitespace_ratio = 1 - (np.sum(cell) / cell.size)
                whitespace_ratios.append(whitespace_ratio)
        
        features["whitespace_variance"] = np.var(whitespace_ratios)
        
        # 骨架提取
        skeleton = self._extract_skeleton(binary)
        features["skeleton_length"] = np.sum(skeleton > 0)
        features["branch_point_count"] = len(self._detect_branch_points(skeleton))
        features["end_point_count"] = len(self._detect_end_points(skeleton))
        
        # 连通分量分析
        num_labels, _, stats, _ = cv2.connectedComponentsWithStats(
            255 - binary, connectivity=8
        )
        features["num_components"] = num_labels - 1
        
        # 边缘分析
        edges = cv2.Canny(binary, 50, 150)
        features["edge_density"] = np.sum(edges > 0) / total_pixels
        
        # 投影分布
        h_projection = np.sum(ink_mask, axis=1)
        v_projection = np.sum(ink_mask, axis=0)
        
        features["h_proj_std"] = np.std(h_projection) / (np.mean(h_projection) + 1e-6)
        features["v_proj_std"] = np.std(v_projection) / (np.mean(v_projection) + 1e-6)
        
        # 对称性
        h_proj_norm = h_projection / (np.max(h_projection) + 1e-6)
        v_proj_norm = v_projection / (np.max(v_projection) + 1e-6)
        features["h_symmetry"] = 1 - np.mean(np.abs(h_proj_norm - np.flip(h_proj_norm)))
        features["v_symmetry"] = 1 - np.mean(np.abs(v_proj_norm - np.flip(v_proj_norm)))
        
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
    
    def _score_structure(self, features: Dict[str, float]) -> int:
        """评分：结构"""
        score_range = self.max_score - self.min_score
        
        # 凸包矩形度
        rect_score = features.get("convex_rectangularity", 0.5)
        rect_deviation = abs(rect_score - 0.8)
        rect_normalized = max(0, 1 - rect_deviation * 2)
        
        # 留白均匀性
        whitespace_var = features.get("whitespace_variance", 0.1)
        whitespace_score = max(0, 1 - whitespace_var * 4)
        
        # 墨迹占比
        ink_ratio = features.get("ink_ratio", 0.25)
        ideal_ratio = 0.28
        ratio_score = 1 - abs(ink_ratio - ideal_ratio) / (ideal_ratio * 1.5)
        ratio_score = max(0, min(1, ratio_score))
        
        final_score = (
            rect_normalized * 0.3 +
            whitespace_score * 0.4 +
            ratio_score * 0.3
        )
        
        return int(final_score * score_range + self.min_score)
    
    def _score_stroke(self, features: Dict[str, float], binary: np.ndarray) -> int:
        """评分：笔画"""
        score_range = self.max_score - self.min_score
        
        # 边缘复杂度
        edge_density = features.get("edge_density", 0.05)
        ideal_density = 0.10
        density_score = 1 - abs(edge_density - ideal_density) / ideal_density
        density_score = max(0, min(1, density_score))
        
        # 骨架分析
        skeleton_length = features.get("skeleton_length", 0)
        ink_count = np.sum(binary == 0)
        
        if ink_count > 0:
            skeleton_ratio = skeleton_length / ink_count
            ideal_skeleton_ratio = 0.12
            skeleton_score = 1 - abs(skeleton_ratio - ideal_skeleton_ratio) / ideal_skeleton_ratio
            skeleton_score = max(0, min(1, skeleton_score))
        else:
            skeleton_score = 0.5
        
        # 连通性
        components = features.get("num_components", 1)
        if components <= 1:
            connectivity_score = 1.0
        elif components <= 3:
            connectivity_score = 0.8
        elif components <= 5:
            connectivity_score = 0.6
        else:
            connectivity_score = 0.4
        
        final_score = (
            density_score * 0.35 +
            skeleton_score * 0.35 +
            connectivity_score * 0.30
        )
        
        return int(final_score * score_range + self.min_score)
    
    def _score_balance(self, features: Dict[str, float]) -> int:
        """评分：平衡"""
        score_range = self.max_score - self.min_score
        
        # 重心偏移
        center_offset = features.get("center_offset", 0)
        balance_score = 1 - center_offset * 2.5
        balance_score = max(0, min(1, balance_score))
        
        # 对称性
        h_symmetry = features.get("h_symmetry", 0.5)
        v_symmetry = features.get("v_symmetry", 0.5)
        
        final_score = (
            balance_score * 0.5 +
            h_symmetry * 0.25 +
            v_symmetry * 0.25
        )
        
        return int(final_score * score_range + self.min_score)
    
    def _score_rhythm(self, features: Dict[str, float]) -> int:
        """评分：韵律"""
        score_range = self.max_score - self.min_score
        
        # 连通性
        components = features.get("num_components", 10)
        if components <= 1:
            flow_score = 1.0
        elif components <= 3:
            flow_score = 0.85
        elif components <= 5:
            flow_score = 0.7
        else:
            flow_score = 0.5
        
        # 端点数量
        end_points = features.get("end_point_count", 0)
        if 2 <= end_points <= 10:
            endpoint_score = 1.0
        elif end_points < 2:
            endpoint_score = 0.8
        else:
            endpoint_score = max(0.5, 1 - (end_points - 10) * 0.03)
        
        # 骨架流畅度
        skeleton_length = features.get("skeleton_length", 0)
        branch_points = features.get("branch_point_count", 0)
        
        if skeleton_length > 0 and branch_points > 0:
            smoothness = min(1, skeleton_length / (branch_points * 40 + 80))
        else:
            smoothness = 0.5
        
        final_score = (
            flow_score * 0.4 +
            endpoint_score * 0.3 +
            smoothness * 0.3
        )
        
        return int(final_score * score_range + self.min_score)
    
    def _generate_feedback(self, total_score: int, detail_scores: Dict[str, int]) -> str:
        """生成反馈文案"""
        if total_score >= 85:
            feedback = "优秀！书法功底扎实，笔画流畅有力！"
        elif total_score >= 70:
            min_dim = min(detail_scores, key=detail_scores.get)
            suggestions = {
                "结构": "注意字形的匀称和留白分布",
                "笔画": "加强笔画的连贯性和粗细变化",
                "平衡": "注意字的重心位置",
                "韵律": "提高行笔的流畅度",
            }
            feedback = f"良好！{suggestions.get(min_dim, '继续练习')}"
        else:
            feedback = "继续练习，建议多临摹字帖，注意笔法和结构"
        
        return feedback


def evaluate_image(image: np.ndarray, character_name: str = None) -> EvaluationResult:
    """
    便捷函数：评测单张图像
    
    Args:
        image: 输入图像
        character_name: 字符名称
        
    Returns:
        EvaluationResult 评测结果
    """
    service = EvaluationService()
    return service.evaluate(image, character_name)