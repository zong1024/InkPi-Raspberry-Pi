"""
InkPi 书法评测系统 - 书法风格分类服务

基于CNN的书法风格识别，支持楷书/行书/草书/隶书/篆书五种风格分类

参考: https://github.com/MingtaoGuo/CNN-for-Chinese-Calligraphy-Styles-classification
"""
import numpy as np
import cv2
from typing import Tuple, Dict, Optional
import logging
from pathlib import Path
import time

try:
    import onnxruntime as ort
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False

try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DATA_DIR
from models.recognition_result import RecognitionResult


# 书法风格类别
STYLE_CLASSES = {
    0: "楷书",
    1: "行书", 
    2: "草书", 
    3: "隶书",
    4: "篆书"
}

# 风格描述
STYLE_DESCRIPTIONS = {
    "楷书": "端正工整，笔画清晰",
    "行书": "流畅自然，连笔顺势",
    "草书": "狂放不羁，笔势连绵",
    "隶书": "庄重古朴，蚕头燕尾",
    "篆书": "圆润均匀，笔画婉转"
}


class StyleClassificationService:
    """书法风格分类服务"""
    
    def __init__(
        self,
        model_path: str = None,
        use_quantized: bool = True
    ):
        self.logger = logging.getLogger(__name__)
        
        # 模型路径
        self.model_dir = DATA_DIR / "models"
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        if model_path:
            self.model_path = Path(model_path)
        else:
            model_name = "style_classifier.onnx" if not use_quantized else "style_classifier_int8.onnx"
            self.model_path = self.model_dir / model_name
        
        # ONNX会话
        self.session = None
        self.input_name = None
        self.output_name = None
        
        # PyTorch模型 (用于训练)
        self.torch_model = None
        
        if ONNX_AVAILABLE:
            self._init_onnx_session()
        elif TORCH_AVAILABLE:
            self._init_torch_model()
        else:
            self.logger.warning("无可用推理框架，将使用模拟模式")
    
    def _init_onnx_session(self):
        """初始化ONNX会话"""
        if not self.model_path.exists():
            self.logger.warning(f"模型文件不存在: {self.model_path}")
            return
        
        try:
            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            sess_options.intra_op_num_threads = 4
            
            self.session = ort.InferenceSession(
                str(self.model_path),
                sess_options,
                providers=['CPUExecutionProvider']
            )
            
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
            
            self.logger.info(f"风格分类ONNX模型加载成功: {self.model_path}")
        except Exception as e:
            self.logger.error(f"模型加载失败: {e}")
            self.session = None
    
    def _init_torch_model(self):
        """初始化PyTorch模型"""
        try:
            # 这里需要下载预训练权重
            self.logger.info("PyTorch模型需要下载权重文件")
        except Exception as e:
            self.logger.error(f"PyTorch模型初始化失败: {e}")
            self.torch_model = None
    
    def classify(self, image: np.ndarray) -> Tuple[str, float, Dict[str, float]]:
        """
        识别书法风格
        
        Args:
            image: 输入图像
            
        Returns:
            (风格名称, 置信度, 各风格概率)
        """
        start_time = time.time()
        
        # 预处理
        processed = self._preprocess(image)
        
        if self.session is not None:
            # ONNX推理
            style, confidence, probs = self._inference_onnx(processed)
        else:
            # 模拟模式
            style, confidence, probs = self._simulate_classification()
        
        inference_time = (time.time() - start_time) * 1000
        
        return style, confidence, probs
    
    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        """预处理图像"""
        # 转灰度
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # 调整尺寸
        resized = cv2.resize(gray, (128, 128), interpolation=cv2.INTER_AREA)
        
        # 归一化
        normalized = resized.astype(np.float32) / 255.0
        
        # 标准化
        mean = 0.5
        std = 0.5
        normalized = (normalized - mean) / std
        
        # 转换为模型输入格式
        processed = normalized.reshape(1, 1, 128, 128).astype(np.float32)
        
        return processed
    
    def _inference_onnx(self, processed: np.ndarray) -> Tuple[str, float, Dict[str, float]]:
        """ONNX推理"""
        outputs = self.session.run(
            [self.output_name], 
            {self.input_name: processed}
        )
        probs = outputs[0][0]  # (num_classes,)
        
        # Softmax
        exp_probs = np.exp(probs - np.max(probs))
        softmax_probs = exp_probs / np.sum(exp_probs)
        
        # 获取结果
        top_idx = np.argmax(softmax_probs)
        confidence = float(softmax_probs[top_idx])
        
        # 所有类别概率
        all_probs = {
            STYLE_CLASSES[i]: float(softmax_probs[i]) 
            for i in range(len(STYLE_CLASSES))
        }
        
        return STYLE_CLASSES[top_idx], confidence, all_probs
    
    def _simulate_classification(self) -> Tuple[str, float, Dict[str, float]]:
        """模拟分类"""
        # 随机生成概率
        probs = np.random.dirichlet(np.ones(5))
        
        # 稍微偏向楷书 (更常见)
        probs[0] += 0.1
        
        # 挌书特征
        kaishu_features = np.random.randn(5) * 0.3
        probs += kaishu_features
        
        style_idx = np.argmax(probs)
        confidence = float(probs[style_idx])
        
        all_probs = {
            STYLE_CLASSES[i]: float(probs[i]) 
            for i in range(len(STYLE_CLASSES))
        }
        
        return STYLE_CLASSES[style_idx], confidence, all_probs
    
    def is_model_loaded(self) -> bool:
        """检查模型是否加载"""
        return self.session is not None or self.torch_model is not None
    
    def get_model_info(self) -> Dict[str, str]:
        """获取模型信息"""
        return {
            "model_path": str(self.model_path),
            "model_exists": self.model_path.exists(),
            "onnx_available": ONNX_AVAILABLE,
            "torch_available": TORCH_AVAILABLE,
            "model_loaded": self.is_model_loaded(),
            "num_classes": len(STYLE_CLASSES),
            "styles": list(STYLE_CLASSES.values())
        }


# 创建全局实例
style_classification_service = StyleClassificationService()