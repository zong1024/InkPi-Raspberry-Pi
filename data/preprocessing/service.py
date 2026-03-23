"""
InkPi 图像预处理服务

参考 DeepVision 的图像处理设计
提供毛笔字图像的预处理功能
"""
import numpy as np
import cv2
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class PreprocessingService:
    """
    图像预处理服务
    
    功能:
    - 图像增强
    - 去噪
    - 二值化
    - 透视校正
    - 尺寸调整
    """
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.target_size = self.config.get("target_size", 224)
        self.threshold_method = self.config.get("threshold_method", "otsu")
        self.blur_kernel = self.config.get("blur_kernel", 3)
    
    def process(self, image: np.ndarray) -> np.ndarray:
        """执行完整预处理流程"""
        gray = self.to_grayscale(image)
        denoised = self.denoise(gray)
        enhanced = self.enhance_contrast(denoised)
        binary = self.binarize(enhanced)
        resized = self.resize(binary)
        return resized
    
    def to_grayscale(self, image: np.ndarray) -> np.ndarray:
        """转换为灰度图"""
        if len(image.shape) == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return image
    
    def denoise(self, image: np.ndarray) -> np.ndarray:
        """去噪处理"""
        if self.blur_kernel > 0:
            image = cv2.GaussianBlur(image, (self.blur_kernel, self.blur_kernel), 0)
        return image
    
    def enhance_contrast(self, image: np.ndarray) -> np.ndarray:
        """对比度增强 - 使用 CLAHE"""
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(image)
    
    def binarize(self, image: np.ndarray) -> np.ndarray:
        """二值化处理"""
        if self.threshold_method == "otsu":
            _, binary = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        elif self.threshold_method == "adaptive":
            binary = cv2.adaptiveThreshold(image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        else:
            _, binary = cv2.threshold(image, 127, 255, cv2.THRESH_BINARY)
        return binary
    
    def resize(self, image: np.ndarray) -> np.ndarray:
        """调整图像尺寸"""
        return cv2.resize(image, (self.target_size, self.target_size), interpolation=cv2.INTER_AREA)
    
    def crop_to_content(self, image: np.ndarray, padding: int = 10) -> np.ndarray:
        """裁剪到内容区域"""
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        coords = cv2.findNonZero(255 - binary)
        
        if coords is None:
            return image
        
        x, y, w, h = cv2.boundingRect(coords)
        x = max(0, x - padding)
        y = max(0, y - padding)
        w = min(image.shape[1] - x, w + 2 * padding)
        h = min(image.shape[0] - y, h + 2 * padding)
        
        return image[y:y+h, x:x+w]
    
    def preprocess_for_model(self, image: np.ndarray) -> np.ndarray:
        """为模型推理预处理图像"""
        processed = self.process(image)
        normalized = processed.astype(np.float32) / 255.0
        return normalized[np.newaxis, :, :]