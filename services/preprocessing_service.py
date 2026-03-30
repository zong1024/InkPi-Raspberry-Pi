"""
InkPi 书法评测系统 - 图像预处理服务

处理流程：
原始图像 → 透视校正 → 缩放(512px) → HSV米字格滤除 → 灰度化 → 自适应二值化 → 中值滤波降噪 → 锐化增强 → 输出

基于 PDF 算法研究文档实现：
1. Canny边缘检测 + 霍夫变换透视校正
2. HSV色彩空间米字格滤除
"""
import cv2
import numpy as np
from typing import Tuple, Optional, List
from pathlib import Path
import logging

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import IMAGE_CONFIG, PRECHECK_CONFIG, PROCESSED_DIR


class PreprocessingError(Exception):
    """预处理异常"""
    def __init__(self, message: str, error_type: str = "unknown"):
        super().__init__(message)
        self.error_type = error_type


class PreprocessingService:
    """图像预处理服务"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config = IMAGE_CONFIG
        self.precheck_config = PRECHECK_CONFIG
        
    def preprocess(self, image: np.ndarray, save_processed: bool = True) -> Tuple[np.ndarray, Optional[str]]:
        """
        完整预处理流程
        
        Args:
            image: 输入图像 (BGR格式)
            save_processed: 是否保存处理后的图像
            
        Returns:
            Tuple[处理后的图像, 保存路径(如果保存)]
        """
        self.logger.info("开始图像预处理...")
        
        # 1. 图像预检
        self._precheck(image)
        
        # 2. 透视校正（尝试检测纸张四角并校正）
        corrected, perspective_applied = self._perspective_correction(image)
        if perspective_applied:
            self.logger.info("透视校正成功")
        
        # 3. 缩放
        resized = self._resize(corrected)
        
        # 4. HSV米字格滤除
        grid_removed, grid_filter_applied = self._remove_red_grid(resized)
        if grid_filter_applied:
            self.logger.info("米字格滤除成功")
        
        # 5. 灰度化
        gray = self._to_grayscale(grid_removed)
        
        # 6. 自适应二值化
        binary = self._adaptive_threshold(gray)
        
        # 7. 中值滤波降噪
        denoised = self._median_blur(binary)
        
        # 8. 锐化增强
        sharpened = self._sharpen(denoised)
        focused = self._extract_primary_subject(sharpened)
        
        # 保存处理后的图像
        processed_path = None
        if save_processed:
            processed_path = self._save_image(focused)
            
        self.logger.info("图像预处理完成")
        return focused, processed_path
    
    def prepare_ocr_image(self, image: np.ndarray) -> np.ndarray:
        """Build a lighter OCR crop from the original image."""
        corrected, _ = self._perspective_correction(image)
        resized = self._resize(corrected)
        grid_removed, _ = self._remove_red_grid(resized)
        gray = self._to_grayscale(grid_removed)
        binary = self._adaptive_threshold(gray)
        binary = self._median_blur(binary)
        sharpened = self._sharpen(binary)
        focused = self._extract_primary_subject(sharpened)
        return self._extract_ocr_subject(gray, focused)

    def _precheck(self, image: np.ndarray) -> None:
        """
        图像预检与异常拦截 (Fail-Fast 机制)
        增强版：添加书法特征检测
        
        Args:
            image: 输入图像
            
        Raises:
            PreprocessingError: 如果图像不符合要求
        """
        self.logger.debug("执行图像预检...")
        
        # 转灰度计算亮度
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
            
        # 1. 光照异常检测
        mean_brightness = np.mean(gray)
        std_contrast = np.std(gray)
        
        self.logger.debug(f"平均亮度: {mean_brightness:.2f}, 对比度(标准差): {std_contrast:.2f}")
        
        if mean_brightness < self.precheck_config["min_brightness"]:
            raise PreprocessingError(
                "光线不足，请改善照明后重试",
                error_type="too_dark"
            )
            
        if mean_brightness > self.precheck_config["max_brightness"]:
            raise PreprocessingError(
                "光线过曝，请调整照明后重试",
                error_type="too_bright"
            )
            
        if std_contrast < self.precheck_config["min_contrast_std"]:
            raise PreprocessingError(
                "对比度不足，请确保书写清晰",
                error_type="low_contrast"
            )
            
        # 2. 空拍与非书法内容检测 (使用 Otsu 快速二值化)
        _, otsu_binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        ink_pixels = np.sum(otsu_binary == 0)  # 黑色像素（墨迹）
        total_pixels = otsu_binary.size
        ink_ratio = ink_pixels / total_pixels
        
        self.logger.debug(f"墨迹占比: {ink_ratio*100:.2f}%")
        
        if ink_ratio < self.precheck_config["min_ink_ratio"]:
            raise PreprocessingError(
                "未检测到有效书写内容，请移开杂物并对准作品",
                error_type="empty_shot"
            )
            
        if ink_ratio > self.precheck_config["max_ink_ratio"]:
            raise PreprocessingError(
                "检测到遮挡或杂物，请移开后重试",
                error_type="obstruction"
            )
        
        # 3. 增强版：书法特征验证
        precheck_binary = self._build_precheck_binary(image)
        precheck_ink_ratio = np.mean(precheck_binary == 0)
        try:
            self._validate_calligraphy_features(precheck_binary, precheck_ink_ratio)
        except PreprocessingError as exc:
            if exc.error_type in {"not_calligraphy", "too_fragmented", "scattered_content"}:
                self.logger.debug("Clean precheck fallback to Otsu validation: %s", exc)
                self._validate_calligraphy_features(otsu_binary, ink_ratio)
            else:
                raise
        
        self.logger.debug("图像预检通过")

    def _build_precheck_binary(self, image: np.ndarray) -> np.ndarray:
        """Build a lightweight cleaned binary for precheck validation."""
        if len(image.shape) == 2:
            working = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        else:
            working = image.copy()

        resized = self._resize(working)
        grid_removed, _ = self._remove_red_grid(resized)
        gray = self._to_grayscale(grid_removed)
        binary = self._adaptive_threshold(gray)
        binary = self._median_blur(binary)
        binary = cv2.morphologyEx(
            binary,
            cv2.MORPH_OPEN,
            np.ones((5, 5), dtype=np.uint8),
        )
        return self._extract_primary_subject(binary)

    def _validate_calligraphy_features(self, binary: np.ndarray, ink_ratio: float) -> None:
        """
        书法特征验证 - 区分书法和杂物
        
        毛笔书法特点：
        - 笔画较粗，边缘密度相对较低
        - 可能有飞白效果（笔画内部的细小空白）
        - 墨迹分布可能较分散（大字、行书等）
        
        Args:
            binary: 二值化图像
            ink_ratio: 墨迹占比
            
        Raises:
            PreprocessingError: 如果不符合书法特征
        """
        h, w = binary.shape
        
        # 1. 长宽比检查（书法通常接近正方形或适度长方形）
        aspect_ratio = w / h
        if aspect_ratio < 0.2 or aspect_ratio > 5.0:
            self.logger.warning(f"长宽比异常: {aspect_ratio:.2f}")
            # 不直接拒绝，但记录警告
        
        # 2. 边缘复杂度检查
        # 毛笔字笔画较粗，边缘密度可能较低，放宽阈值
        edges = cv2.Canny(binary, 30, 100)  # 降低 Canny 阈值以检测更多边缘
        edge_pixels = int(np.sum(edges > 0))
        ink_pixels = int(np.sum(binary == 0))
        edge_ratio = edge_pixels / binary.size
        edge_to_ink_ratio = edge_pixels / max(1, ink_pixels)
        
        # 毛笔字边缘密度阈值放宽到 0.001（原来 0.01）
        if edge_ratio < 0.001:
            raise PreprocessingError(
                "内容过于简单，请确保拍摄的是书法作品",
                error_type="not_calligraphy"
            )

        dominant_component = self._find_dominant_central_component(binary)
        dominant_central_character = bool(
            dominant_component
            and dominant_component["ink_share"] >= self.precheck_config.get("min_dominant_ink_share", 0.42)
            and dominant_component["center_distance"] <= self.precheck_config.get("max_dominant_center_distance", 0.34)
        )

        contours, _ = cv2.findContours(255 - binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        largest_area_ratio = 0.0
        largest_solidity = 0.0
        largest_bbox_fill = 0.0
        if contours:
            largest_contour = max(contours, key=cv2.contourArea)
            largest_area = float(cv2.contourArea(largest_contour))
            largest_area_ratio = largest_area / binary.size
            x, y, w_box, h_box = cv2.boundingRect(largest_contour)
            bbox_area = max(1, w_box * h_box)
            hull = cv2.convexHull(largest_contour)
            hull_area = max(1.0, cv2.contourArea(hull))
            largest_solidity = largest_area / hull_area
            largest_bbox_fill = float(np.mean(binary[y : y + h_box, x : x + w_box] == 0))

            # 单个大色块或遮挡物通常边缘相对少、实心度和填充度都偏高。
            if (
                edge_to_ink_ratio < self.precheck_config.get("min_edge_to_ink_ratio", 0.08)
                and (
                    largest_solidity > self.precheck_config.get("max_blob_solidity", 0.90)
                    or largest_bbox_fill > self.precheck_config.get("max_blob_fill_ratio", 0.58)
                    or largest_area_ratio > self.precheck_config.get("max_blob_area_ratio", 0.18)
                )
                and not dominant_central_character
            ):
                raise PreprocessingError(
                    "未检测到清晰的单个毛笔字，请重新对准作品后再试",
                    error_type="not_calligraphy"
                )
        
        # 3. 连通性检查
        # 毛笔字可能有较多离散笔画（如点、撇等），放宽阈值
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
            255 - binary, connectivity=8
        )
        component_areas = stats[1:, cv2.CC_STAT_AREA] if num_labels > 1 else np.array([], dtype=np.int32)
        min_component_area = max(
            8,
            int(binary.size * self.precheck_config.get("min_component_area_ratio", 0.00008))
        )
        meaningful_components = component_areas[component_areas >= min_component_area]
        num_components = len(meaningful_components)
        dominant_central_character = dominant_central_character and (
            edge_to_ink_ratio >= self.precheck_config.get("dominant_min_edge_to_ink_ratio", 0.12)
            or num_components >= self.precheck_config.get("min_annotation_components", 4)
        )

        if (
            dominant_component
            and num_components <= 2
            and dominant_component["ink_share"] >= 0.9
            and edge_to_ink_ratio < self.precheck_config.get("solid_blob_max_edge_to_ink_ratio", 0.2)
            and largest_bbox_fill > self.precheck_config.get("solid_blob_max_fill_ratio", 0.7)
        ):
            raise PreprocessingError(
                "未检测到清晰的毛笔字主体，请重新对准作品后再试",
                error_type="not_calligraphy"
            )
        
        if (
            num_components > self.precheck_config.get("max_meaningful_components", 60)
            and not dominant_central_character
        ):
            raise PreprocessingError(
                "检测到较多零散笔画或背景噪点，请尽量对准单个字并保持画面干净后重试",
                error_type="too_fragmented"
            )
        
        # 4. 分布集中度检查
        # 毛笔书法（特别是行书、草书）笔画分布可能较分散，大幅放宽阈值
        ink_mask = binary == 0
        if np.sum(ink_mask) > 0:
            y_coords, x_coords = np.where(ink_mask)
            x_spread = np.std(x_coords) / w
            y_spread = np.std(y_coords) / h
            
            # 放宽到 0.7（原 0.45），允许更分散的布局
            if x_spread > 0.7 and y_spread > 0.7 and not dominant_central_character:
                raise PreprocessingError(
                    "内容分布过于分散，请对准单个汉字",
                    error_type="scattered_content"
                )
        
        self.logger.debug(
            f"书法特征验证通过: 边缘密度={edge_ratio:.4f}, 边缘墨迹比={edge_to_ink_ratio:.4f}, "
            f"最大连通域面积占比={largest_area_ratio:.4f}, 最大实心度={largest_solidity:.4f}, "
            f"最大包围盒填充率={largest_bbox_fill:.4f}, 有效连通域={num_components}, "
            f"最小面积阈值={min_component_area}"
        )
    
    def _find_dominant_central_component(self, binary: np.ndarray):
        mask = (binary == 0).astype(np.uint8)
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
        if num_labels <= 1:
            return None

        areas = stats[1:, cv2.CC_STAT_AREA]
        if areas.size == 0:
            return None

        dominant_index = int(np.argmax(areas)) + 1
        dominant_area = float(stats[dominant_index, cv2.CC_STAT_AREA])
        total_ink = float(np.sum(areas))
        if total_ink <= 0:
            return None

        h, w = binary.shape
        center_x = float(centroids[dominant_index][0])
        center_y = float(centroids[dominant_index][1])
        normalized_dx = (center_x - (w / 2.0)) / max(1.0, w / 2.0)
        normalized_dy = (center_y - (h / 2.0)) / max(1.0, h / 2.0)
        center_distance = float(np.hypot(normalized_dx, normalized_dy))

        return {
            "label": dominant_index,
            "area": dominant_area,
            "ink_share": dominant_area / total_ink,
            "center_distance": center_distance,
            "stats": stats[dominant_index],
        }

    def _extract_primary_subject(self, binary: np.ndarray) -> np.ndarray:
        dominant = self._find_dominant_central_component(binary)
        if not dominant:
            return binary

        if dominant["ink_share"] < self.precheck_config.get("min_dominant_ink_share", 0.42):
            return binary

        mask = (binary == 0).astype(np.uint8)
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
        if num_labels <= 1:
            return binary

        x = int(dominant["stats"][cv2.CC_STAT_LEFT])
        y = int(dominant["stats"][cv2.CC_STAT_TOP])
        w_box = int(dominant["stats"][cv2.CC_STAT_WIDTH])
        h_box = int(dominant["stats"][cv2.CC_STAT_HEIGHT])
        dominant_area = max(1.0, dominant["area"])
        margin = max(18, int(max(w_box, h_box) * 0.18))
        expanded_left = x - margin
        expanded_top = y - margin
        expanded_right = x + w_box + margin
        expanded_bottom = y + h_box + margin

        keep_mask = np.zeros_like(mask, dtype=np.uint8)
        total_kept = 0.0

        for label in range(1, num_labels):
            area = float(stats[label, cv2.CC_STAT_AREA])
            if area < max(12.0, dominant_area * 0.02):
                continue

            comp_x = int(stats[label, cv2.CC_STAT_LEFT])
            comp_y = int(stats[label, cv2.CC_STAT_TOP])
            comp_w = int(stats[label, cv2.CC_STAT_WIDTH])
            comp_h = int(stats[label, cv2.CC_STAT_HEIGHT])
            comp_center_x = float(centroids[label][0])
            comp_center_y = float(centroids[label][1])

            overlaps_focus = not (
                comp_x + comp_w < expanded_left
                or comp_x > expanded_right
                or comp_y + comp_h < expanded_top
                or comp_y > expanded_bottom
            )
            inside_focus = (
                expanded_left <= comp_center_x <= expanded_right
                and expanded_top <= comp_center_y <= expanded_bottom
            )
            sizable_companion = area >= dominant_area * 0.28

            if overlaps_focus or inside_focus or sizable_companion or label == dominant["label"]:
                keep_mask[labels == label] = 1
                total_kept += area

        total_ink = float(np.sum(stats[1:, cv2.CC_STAT_AREA]))
        if total_ink <= 0 or total_kept / total_ink < 0.55:
            return binary

        focused = np.where(keep_mask > 0, 0, 255).astype(np.uint8)
        focused = cv2.morphologyEx(
            focused,
            cv2.MORPH_CLOSE,
            np.ones((3, 3), dtype=np.uint8),
        )
        return focused

    def _extract_ocr_subject(self, gray: np.ndarray, focused_binary: np.ndarray) -> np.ndarray:
        """Crop a central grayscale subject for OCR without aggressive binarization."""
        points = cv2.findNonZero((255 - focused_binary).astype(np.uint8))
        if points is None:
            return gray

        x, y, w_box, h_box = cv2.boundingRect(points)
        pad = max(16, int(max(w_box, h_box) * 0.18))
        x0 = max(0, x - pad)
        y0 = max(0, y - pad)
        x1 = min(gray.shape[1], x + w_box + pad)
        y1 = min(gray.shape[0], y + h_box + pad)

        crop = gray[y0:y1, x0:x1].copy()
        if crop.size == 0:
            return gray

        clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
        return clahe.apply(crop)

    def _perspective_correction(self, image: np.ndarray) -> Tuple[np.ndarray, bool]:
        """
        透视校正 - 基于Canny边缘检测和霍夫变换
        
        算法流程（PDF文档）：
        1. 灰度化 → 高斯滤波抑制噪声
        2. Canny边缘检测（动态阈值50-150）
        3. 概率霍夫变换检测直线
        4. 计算线段交点定位四角
        5. 透视变换矩阵映射到正交视角
        
        Args:
            image: 输入图像
            
        Returns:
            Tuple[校正后的图像, 是否应用了校正]
        """
        try:
            # 转灰度
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
            
            # 高斯滤波降噪
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Canny边缘检测
            edges = cv2.Canny(blurred, 50, 150)
            
            # 概率霍夫变换检测直线
            lines = cv2.HoughLinesP(
                edges,
                rho=1,
                theta=np.pi / 180,
                threshold=100,
                minLineLength=100,
                maxLineGap=10
            )
            
            if lines is None or len(lines) < 4:
                self.logger.debug("未检测到足够直线，跳过透视校正")
                return image, False
            
            # 寻找四边形
            corners = self._find_quadrilateral(lines, image.shape[:2])
            
            if corners is None:
                self.logger.debug("未检测到有效四边形，跳过透视校正")
                return image, False
            
            # 计算透视变换矩阵
            dst_corners = np.array([
                [0, 0],
                [image.shape[1] - 1, 0],
                [image.shape[1] - 1, image.shape[0] - 1],
                [0, image.shape[0] - 1]
            ], dtype=np.float32)
            
            M = cv2.getPerspectiveTransform(corners.astype(np.float32), dst_corners)
            
            # 应用透视变换
            corrected = cv2.warpPerspective(
                image, M, 
                (image.shape[1], image.shape[0]),
                flags=cv2.INTER_LINEAR
            )
            
            return corrected, True
            
        except Exception as e:
            self.logger.warning(f"透视校正失败: {e}")
            return image, False
    
    def _find_quadrilateral(self, lines: np.ndarray, image_shape: Tuple[int, int]) -> Optional[np.ndarray]:
        """
        从检测到的直线中寻找四边形
        
        Args:
            lines: 霍夫变换检测到的直线
            image_shape: 图像尺寸 (h, w)
            
        Returns:
            四个角点的数组，或None
        """
        h, w = image_shape
        
        # 分类直线：水平和垂直
        horizontal_lines = []
        vertical_lines = []
        
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = np.arctan2(abs(y2 - y1), abs(x2 - x1))
            
            if angle < np.pi / 6:  # 接近水平
                horizontal_lines.append(line[0])
            elif angle > np.pi / 3:  # 接近垂直
                vertical_lines.append(line[0])
        
        if len(horizontal_lines) < 2 or len(vertical_lines) < 2:
            return None
        
        # 找到最上和最下的水平线
        horizontal_lines.sort(key=lambda l: (l[1] + l[3]) / 2)
        top_line = horizontal_lines[0]
        bottom_line = horizontal_lines[-1]
        
        # 找到最左和最右的垂直线
        vertical_lines.sort(key=lambda l: (l[0] + l[2]) / 2)
        left_line = vertical_lines[0]
        right_line = vertical_lines[-1]
        
        # 计算四个交点
        def line_intersection(line1, line2):
            x1, y1, x2, y2 = line1
            x3, y3, x4, y4 = line2
            
            denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
            if abs(denom) < 1e-10:
                return None
            
            t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
            
            x = x1 + t * (x2 - x1)
            y = y1 + t * (y2 - y1)
            
            return (x, y)
        
        corners = []
        intersections = [
            line_intersection(top_line, left_line),
            line_intersection(top_line, right_line),
            line_intersection(bottom_line, right_line),
            line_intersection(bottom_line, left_line)
        ]
        
        for point in intersections:
            if point is None:
                return None
            x, y = point
            # 检查点是否在图像范围内
            if x < -w * 0.1 or x > w * 1.1 or y < -h * 0.1 or y > h * 1.1:
                return None
            corners.append([x, y])
        
        return np.array(corners)
    
    def _remove_red_grid(self, image: np.ndarray) -> Tuple[np.ndarray, bool]:
        """
        HSV米字格滤除
        
        算法流程（PDF文档）：
        1. RGB → HSV色彩空间转换
        2. 生成两个红色掩码：
           - 低频红色: H ∈ [0, 10]
           - 高频红色: H ∈ [170, 180]
        3. 合并掩码 + 形态学闭运算
        4. 将红色区域替换为背景色
        5. Otsu二值化提取墨迹
        
        Args:
            image: 输入图像 (BGR格式)
            
        Returns:
            Tuple[处理后的图像, 是否应用了滤除]
        """
        try:
            # 转换到HSV色彩空间
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            
            # 定义红色的HSV范围
            # 低频红色 (0-10)
            lower_red1 = np.array([0, 70, 50])
            upper_red1 = np.array([10, 255, 255])
            
            # 高频红色 (170-180)
            lower_red2 = np.array([170, 70, 50])
            upper_red2 = np.array([180, 255, 255])
            
            # 创建两个掩码
            mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
            mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
            
            # 合并掩码
            red_mask = cv2.bitwise_or(mask1, mask2)
            
            # 检查是否有足够的红色像素
            red_ratio = np.sum(red_mask > 0) / red_mask.size
            
            if red_ratio < 0.005:  # 红色占比小于0.5%，跳过滤除
                self.logger.debug(f"未检测到红色网格 (红色占比: {red_ratio*100:.2f}%)")
                return image, False
            
            # 形态学闭运算，防止删除与红色交叠的墨迹
            kernel = np.ones((3, 3), np.uint8)
            red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel)
            
            # 计算背景色（非红色区域的平均色）
            non_red_mask = cv2.bitwise_not(red_mask)
            background = cv2.mean(image, mask=non_red_mask)[:3]
            background = np.array(background, dtype=np.uint8)
            
            # 将红色区域替换为背景色
            result = image.copy()
            result[red_mask > 0] = background
            
            self.logger.debug(f"米字格滤除: 红色占比={red_ratio*100:.2f}%")
            
            return result, True
            
        except Exception as e:
            self.logger.warning(f"米字格滤除失败: {e}")
            return image, False
    
    def _resize(self, image: np.ndarray) -> np.ndarray:
        """
        缩放图像到目标尺寸
        
        Args:
            image: 输入图像
            
        Returns:
            缩放后的图像
        """
        target_size = self.config["target_size"]
        h, w = image.shape[:2]
        
        # 计算缩放比例，保持宽高比
        scale = target_size / max(h, w)
        new_w = int(w * scale)
        new_h = int(h * scale)
        
        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        self.logger.debug(f"缩放: {w}x{h} -> {new_w}x{new_h}")
        
        return resized
    
    def _to_grayscale(self, image: np.ndarray) -> np.ndarray:
        """
        转换为灰度图
        
        Args:
            image: 输入图像
            
        Returns:
            灰度图像
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        return gray
    
    def _adaptive_threshold(self, gray: np.ndarray) -> np.ndarray:
        """
        自适应二值化
        
        使用局部阈值处理光照不均问题
        
        Args:
            gray: 灰度图像
            
        Returns:
            二值化图像
        """
        block_size = self.config["adaptive_block_size"]
        c = self.config["adaptive_c"]
        
        # 自适应阈值二值化
        binary = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            block_size,
            c
        )
        
        self.logger.debug(f"自适应二值化: block_size={block_size}, C={c}")
        return binary
    
    def _median_blur(self, image: np.ndarray) -> np.ndarray:
        """
        中值滤波降噪（毛笔字优化版）
        
        毛笔字特点：
        - 边缘有自然毛刺，不应被过度平滑
        - 飞白效果需要保留
        - 使用较小的核避免丢失笔锋特征
        
        Args:
            image: 输入图像
            
        Returns:
            降噪后的图像
        """
        # 毛笔字使用较小的滤波核，保留边缘特征
        ksize = 3  # 固定使用3x3，避免过度平滑
        denoised = cv2.medianBlur(image, ksize)
        
        self.logger.debug(f"中值滤波(毛笔优化): ksize={ksize}")
        return denoised
    
    def _sharpen(self, image: np.ndarray) -> np.ndarray:
        """
        拉普拉斯锐化
        
        增强笔画边缘清晰度
        
        Args:
            image: 输入图像
            
        Returns:
            锐化后的图像
        """
        # 拉普拉斯锐化卷积核
        kernel = np.array([
            [0, -1, 0],
            [-1, 5, -1],
            [0, -1, 0]
        ], dtype=np.float32)
        
        sharpened = cv2.filter2D(image, -1, kernel)
        
        self.logger.debug("拉普拉斯锐化完成")
        return sharpened
    
    def _save_image(self, image: np.ndarray) -> str:
        """
        保存处理后的图像
        
        Args:
            image: 处理后的图像
            
        Returns:
            保存路径
        """
        import time
        timestamp = int(time.time() * 1000)
        filename = f"processed_{timestamp}.png"
        filepath = PROCESSED_DIR / filename
        
        cv2.imwrite(str(filepath), image)
        self.logger.debug(f"保存处理后图像: {filepath}")
        
        return str(filepath)
    
    def release_memory(self):
        """释放 OpenCV 临时内存"""
        try:
            cv2.destroyAllWindows()
        except cv2.error:
            # Headless OpenCV builds may not include HighGUI support.
            pass
        self.logger.debug("释放 OpenCV 内存")


# 创建全局服务实例
preprocessing_service = PreprocessingService()
