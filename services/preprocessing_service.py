"""
InkPi 书法评测系统 - 图像预处理服务

处理流程：
原始图像 → 缩放(512px) → 灰度化 → 自适应二值化 → 中值滤波降噪 → 锐化增强 → 输出
"""
import cv2
import numpy as np
from typing import Tuple, Optional
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
        
        # 2. 缩放
        resized = self._resize(image)
        
        # 3. 灰度化
        gray = self._to_grayscale(resized)
        
        # 4. 自适应二值化
        binary = self._adaptive_threshold(gray)
        
        # 5. 中值滤波降噪
        denoised = self._median_blur(binary)
        
        # 6. 锐化增强
        sharpened = self._sharpen(denoised)
        
        # 保存处理后的图像
        processed_path = None
        if save_processed:
            processed_path = self._save_image(sharpened)
            
        self.logger.info("图像预处理完成")
        return sharpened, processed_path
    
    def _precheck(self, image: np.ndarray) -> None:
        """
        图像预检与异常拦截 (Fail-Fast 机制)
        
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
            
        self.logger.debug("图像预检通过")
        
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
        
        使用局部阈值处理光照不均问题，模拟米字格滤除效果
        
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
        中值滤波降噪
        
        去除椒盐噪点，保留边缘
        
        Args:
            image: 输入图像
            
        Returns:
            降噪后的图像
        """
        ksize = self.config["median_blur_size"]
        denoised = cv2.medianBlur(image, ksize)
        
        self.logger.debug(f"中值滤波: ksize={ksize}")
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
        cv2.destroyAllWindows()
        self.logger.debug("释放 OpenCV 内存")


# 创建全局服务实例
preprocessing_service = PreprocessingService()