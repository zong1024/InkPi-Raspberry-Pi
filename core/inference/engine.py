"""
InkPi 推理引擎

支持多种推理后端:
- PyTorch (.pth)
- ONNX (.onnx)
- TFLite (.tflite) - 移动端/树莓派
"""
import numpy as np
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Tuple, Optional, Union
import logging

logger = logging.getLogger(__name__)


class BaseInferenceEngine(ABC):
    """推理引擎基类"""
    
    def __init__(self, model_path: str, device: str = "cpu"):
        """
        初始化推理引擎
        
        Args:
            model_path: 模型文件路径
            device: 运行设备 (cpu/cuda)
        """
        self.model_path = Path(model_path)
        self.device = device
        self.model = None
        self._load_model()
    
    @abstractmethod
    def _load_model(self):
        """加载模型"""
        pass
    
    @abstractmethod
    def infer(self, image1: np.ndarray, image2: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        执行推理
        
        Args:
            image1: 模板图像 [H, W] 或 [1, H, W]
            image2: 待评测图像 [H, W] 或 [1, H, W]
            
        Returns:
            (feature1, feature2): 两个特征向量
        """
        pass
    
    def compute_similarity(self, image1: np.ndarray, image2: np.ndarray) -> float:
        """
        计算相似度
        
        Args:
            image1: 模板图像
            image2: 待评测图像
            
        Returns:
            相似度分数 [-1, 1]
        """
        feat1, feat2 = self.infer(image1, image2)
        similarity = np.dot(feat1.flatten(), feat2.flatten())
        return float(similarity)
    
    def _preprocess(self, image: np.ndarray, target_size: int = 224) -> np.ndarray:
        """
        预处理图像
        
        Args:
            image: 输入图像
            target_size: 目标尺寸
            
        Returns:
            预处理后的图像 [1, 1, H, W]
        """
        import cv2
        
        # 确保是灰度图
        if len(image.shape) == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # 调整大小
        image = cv2.resize(image, (target_size, target_size), interpolation=cv2.INTER_AREA)
        
        # 归一化
        image = image.astype(np.float32) / 255.0
        
        # 添加 batch 和 channel 维度
        image = image[np.newaxis, np.newaxis, :, :]
        
        return image


class TorchInferenceEngine(BaseInferenceEngine):
    """PyTorch 推理引擎"""
    
    def _load_model(self):
        import torch
        from core.models.siamese_net import load_model
        
        logger.info(f"加载 PyTorch 模型: {self.model_path}")
        self.model = load_model(str(self.model_path), device=self.device)
        self.model.eval()
        logger.info("PyTorch 模型加载完成")
    
    def infer(self, image1: np.ndarray, image2: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        import torch
        
        # 预处理
        img1 = self._preprocess(image1)
        img2 = self._preprocess(image2)
        
        # 转换为 tensor
        tensor1 = torch.from_numpy(img1).to(self.device)
        tensor2 = torch.from_numpy(img2).to(self.device)
        
        # 推理
        with torch.no_grad():
            feat1, feat2 = self.model(tensor1, tensor2)
        
        return feat1.cpu().numpy(), feat2.cpu().numpy()


class ONNXInferenceEngine(BaseInferenceEngine):
    """ONNX 推理引擎 - 适用于树莓派"""
    
    def __init__(self, model_path: str, device: str = "cpu", providers: list = None):
        """
        初始化 ONNX 推理引擎
        
        Args:
            model_path: ONNX 模型路径
            device: 运行设备
            providers: ONNX Runtime providers
        """
        self.providers = providers or ["CPUExecutionProvider"]
        super().__init__(model_path, device)
    
    def _load_model(self):
        import onnxruntime as ort
        
        logger.info(f"加载 ONNX 模型: {self.model_path}")
        
        # 创建推理会话
        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        
        self.session = ort.InferenceSession(
            str(self.model_path),
            sess_options=sess_options,
            providers=self.providers,
        )
        
        # 获取输入输出信息
        self.input_names = [inp.name for inp in self.session.get_inputs()]
        self.output_names = [out.name for out in self.session.get_outputs()]
        
        logger.info(f"ONNX 模型加载完成, 输入: {self.input_names}, 输出: {self.output_names}")
    
    def infer(self, image1: np.ndarray, image2: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        # 预处理
        img1 = self._preprocess(image1)
        img2 = self._preprocess(image2)
        
        # 推理
        outputs = self.session.run(
            self.output_names,
            {
                self.input_names[0]: img1,
                self.input_names[1]: img2,
            }
        )
        
        return outputs[0], outputs[1]


class TFLiteInferenceEngine(BaseInferenceEngine):
    """TFLite 推理引擎 - 适用于移动端/树莓派"""
    
    def __init__(self, model_path: str, device: str = "cpu", num_threads: int = 4):
        """
        初始化 TFLite 推理引擎
        
        Args:
            model_path: TFLite 模型路径
            device: 运行设备
            num_threads: 线程数
        """
        self.num_threads = num_threads
        super().__init__(model_path, device)
    
    def _load_model(self):
        try:
            import tflite_runtime.interpreter as tflite
        except ImportError:
            import tensorflow.lite as tflite
        
        logger.info(f"加载 TFLite 模型: {self.model_path}")
        
        # 创建解释器
        self.interpreter = tflite.Interpreter(
            model_path=str(self.model_path),
            num_threads=self.num_threads,
        )
        self.interpreter.allocate_tensors()
        
        # 获取输入输出信息
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()
        
        logger.info(f"TFLite 模型加载完成")
    
    def infer(self, image1: np.ndarray, image2: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        # 预处理
        img1 = self._preprocess(image1)
        img2 = self._preprocess(image2)
        
        # 设置输入
        self.interpreter.set_tensor(self.input_details[0]['index'], img1)
        self.interpreter.set_tensor(self.input_details[1]['index'], img2)
        
        # 推理
        self.interpreter.invoke()
        
        # 获取输出
        feat1 = self.interpreter.get_tensor(self.output_details[0]['index'])
        feat2 = self.interpreter.get_tensor(self.output_details[1]['index'])
        
        return feat1, feat2


def create_engine(
    model_path: str,
    engine_type: str = "auto",
    device: str = "cpu",
    **kwargs
) -> BaseInferenceEngine:
    """
    创建推理引擎
    
    Args:
        model_path: 模型路径
        engine_type: 引擎类型 ("auto", "torch", "onnx", "tflite")
        device: 运行设备
        **kwargs: 其他参数
        
    Returns:
        推理引擎实例
    """
    model_path = Path(model_path)
    suffix = model_path.suffix.lower()
    
    # 自动检测引擎类型
    if engine_type == "auto":
        if suffix == ".pth" or suffix == ".pt":
            engine_type = "torch"
        elif suffix == ".onnx":
            engine_type = "onnx"
        elif suffix == ".tflite":
            engine_type = "tflite"
        else:
            raise ValueError(f"无法识别的模型格式: {suffix}")
    
    # 创建对应的引擎
    if engine_type == "torch":
        return TorchInferenceEngine(model_path, device, **kwargs)
    elif engine_type == "onnx":
        return ONNXInferenceEngine(model_path, device, **kwargs)
    elif engine_type == "tflite":
        return TFLiteInferenceEngine(model_path, device, **kwargs)
    else:
        raise ValueError(f"不支持的引擎类型: {engine_type}")