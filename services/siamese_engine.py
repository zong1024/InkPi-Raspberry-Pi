"""
InkPi 书法评测系统 - 孪生网络推理引擎

混合架构核心组件：
- 负责结构与平衡维度的评分
- 与标准字帖进行相似度对比
- 支持模拟模式（无ONNX模型时）和真实推理模式

设计理念：
- 孪生网络只输出：结构相似度 + 平衡感知分数
- 笔画和韵律由 OpenCV 物理特征模块负责
"""
import contextlib
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import MODELS_DIR, MODEL_CONFIG, DATA_DIR


class SiameseEngine:
    """
    孪生网络推理引擎
    
    功能：
    1. 加载 ONNX 孪生网络模型（单例模式）
    2. 提取图像特征向量
    3. 计算与字帖的相似度
    """
    
    _instance = None
    _session = None
    
    def __new__(cls, *args, **kwargs):
        """单例模式：确保 ONNX Session 只创建一次"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, model_path: str = None, use_mock: bool = False):
        self.logger = logging.getLogger(__name__)
        self.use_mock = use_mock
        self.input_size = (224, 224)  # 输入尺寸
        
        # 模型路径
        self.model_path = self._resolve_model_path(model_path)
        
        # 初始化 ONNX Session
        if not use_mock:
            self._init_onnx_session()
        else:
            self.logger.info("孪生网络使用模拟模式")

    def _resolve_model_path(self, model_path: str = None) -> str:
        """解析孪生网络模型路径，支持环境变量和多个兼容位置。"""
        candidates = []

        env_model_path = os.environ.get("INKPI_SIAMESE_MODEL")
        if env_model_path:
            candidates.append(Path(env_model_path))

        if model_path:
            candidates.append(Path(model_path))

        config_model_path = MODEL_CONFIG.get("onnx_path")
        if config_model_path:
            candidates.append(Path(config_model_path))

        candidates.extend([
            MODELS_DIR / "siamese_calligraphy.onnx",
            DATA_DIR / "models" / "siamese_calligraphy.onnx",
        ])

        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return str(Path(candidate))

        # 回退到默认位置，方便后续日志输出
        return str(candidates[0] if candidates else MODELS_DIR / "siamese_calligraphy.onnx")

    @contextlib.contextmanager
    def _suppress_native_stderr(self):
        """
        Debian arm64 onnxruntime packages can emit large volumes of schema
        warnings to the native stderr stream even when model loading succeeds.
        Keep Raspberry Pi startup quiet unless verbose diagnostics are enabled.
        """
        if os.environ.get("INKPI_VERBOSE_ONNX") == "1" or os.name != "posix":
            yield
            return

        try:
            saved_stderr = os.dup(2)
            null_stderr = os.open(os.devnull, os.O_WRONLY)
        except OSError:
            yield
            return

        try:
            os.dup2(null_stderr, 2)
            yield
        finally:
            os.dup2(saved_stderr, 2)
            os.close(saved_stderr)
            os.close(null_stderr)
    
    def _init_onnx_session(self):
        """初始化 ONNX Runtime Session（全局单例）"""
        try:
            import onnxruntime as ort
            
            # 检查模型文件是否存在
            if not Path(self.model_path).exists():
                self.logger.debug(f"ONNX 模型不存在: {self.model_path}，使用模拟模式")
                self.use_mock = True
                return
            
            # 创建 ONNX Session
            providers = ['CPUExecutionProvider']
            if 'CUDAExecutionProvider' in ort.get_available_providers():
                providers.insert(0, 'CUDAExecutionProvider')
            
            session_options = ort.SessionOptions()
            session_options.log_severity_level = 3

            with self._suppress_native_stderr():
                self._session = ort.InferenceSession(
                    self.model_path,
                    sess_options=session_options,
                    providers=providers
                )
            
            # 获取输入输出信息
            self.input_names = [inp.name for inp in self._session.get_inputs()]
            self.output_names = [out.name for out in self._session.get_outputs()]
            
            self.logger.info(f"ONNX Session 初始化成功: {self.model_path}")
            self.logger.info(f"输入: {self.input_names}, 输出: {self.output_names}")
            
        except ImportError:
            self.logger.warning("ONNX Runtime 未安装，使用模拟模式")
            self.use_mock = True
        except Exception as e:
            self.logger.warning(f"ONNX Session 初始化失败: {e}，使用模拟模式")
            self.use_mock = True

    def is_model_loaded(self) -> bool:
        """检查真实 ONNX 模型是否已加载。"""
        if self._session is None and self.use_mock and Path(self.model_path).exists():
            self.use_mock = False
            self._init_onnx_session()

        return (self._session is not None) and (not self.use_mock)
    
    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        预处理图像为网络输入格式
        
        Args:
            image: 输入图像 (BGR 或灰度)
            
        Returns:
            预处理后的图像 (1, 1, 224, 224) float32
        """
        # 转灰度
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # 缩放到 224x224
        resized = cv2.resize(gray, self.input_size, interpolation=cv2.INTER_AREA)
        
        # 归一化到 [0, 1]
        normalized = resized.astype(np.float32) / 255.0
        
        # 添加 batch 和 channel 维度 (1, 1, 224, 224)
        tensor = normalized[np.newaxis, np.newaxis, :, :]
        
        return tensor
    
    def extract_features(self, image: np.ndarray) -> np.ndarray:
        """
        提取图像特征向量
        
        Args:
            image: 输入图像
            
        Returns:
            128维特征向量
        """
        if self.use_mock:
            return self._mock_extract_features(image)
        
        # 预处理
        tensor = self.preprocess_image(image)
        input_feed = {name: tensor for name in self.input_names}
        outputs = self._session.run([self.output_names[0]], input_feed)
        features = outputs[0].flatten()
        
        return features

    def infer_pair(self, image1: np.ndarray, image2: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        对一对图像执行孪生网络推理。

        Args:
            image1: 图像1
            image2: 图像2

        Returns:
            Tuple[feature1, feature2]
        """
        if self.use_mock:
            return self._mock_extract_features(image1), self._mock_extract_features(image2)

        tensor1 = self.preprocess_image(image1)
        tensor2 = self.preprocess_image(image2)
        input_feed = {
            self.input_names[0]: tensor1,
            self.input_names[1]: tensor2,
        }
        outputs = self._session.run(self.output_names[:2], input_feed)
        return outputs[0].flatten(), outputs[1].flatten()
    
    def _mock_extract_features(self, image: np.ndarray) -> np.ndarray:
        """
        模拟特征提取（基于图像统计特征）
        
        在无 ONNX 模型时，使用传统 CV 特征模拟
        
        Args:
            image: 输入图像
            
        Returns:
            128维模拟特征向量
        """
        # 转灰度
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # 缩放到统一尺寸
        resized = cv2.resize(gray, self.input_size)
        
        # 提取多种特征模拟 128 维向量
        features = []
        
        # 1. 网格特征 (64维): 8x8 网格的均值
        cell_h, cell_w = resized.shape[0] // 8, resized.shape[1] // 8
        for i in range(8):
            for j in range(8):
                cell = resized[i*cell_h:(i+1)*cell_h, j*cell_w:(j+1)*cell_w]
                features.append(np.mean(cell) / 255.0)
        
        # 2. 投影特征 (32维): 水平+垂直投影
        h_proj = np.mean(resized, axis=1) / 255.0
        v_proj = np.mean(resized, axis=0) / 255.0
        # 降采样到各16维
        h_proj_ds = np.interp(np.linspace(0, len(h_proj)-1, 16), 
                              np.arange(len(h_proj)), h_proj)
        v_proj_ds = np.interp(np.linspace(0, len(v_proj)-1, 16), 
                              np.arange(len(v_proj)), v_proj)
        features.extend(h_proj_ds)
        features.extend(v_proj_ds)
        
        # 3. 区域特征 (16维): 4x4 区域的墨迹占比
        cell_h4, cell_w4 = resized.shape[0] // 4, resized.shape[1] // 4
        _, binary = cv2.threshold(resized, 127, 255, cv2.THRESH_BINARY)
        for i in range(4):
            for j in range(4):
                cell = binary[i*cell_h4:(i+1)*cell_h4, j*cell_w4:(j+1)*cell_w4]
                ink_ratio = np.sum(cell == 0) / cell.size
                features.append(ink_ratio)
        
        # 4. 边缘特征 (16维): HOG 简化版
        edges = cv2.Canny(resized, 50, 150)
        for i in range(4):
            for j in range(4):
                cell = edges[i*cell_h4:(i+1)*cell_h4, j*cell_w4:(j+1)*cell_w4]
                edge_density = np.sum(cell > 0) / cell.size
                features.append(edge_density)
        
        return np.array(features, dtype=np.float32)
    
    def compute_similarity(self, features1: np.ndarray, features2: np.ndarray) -> float:
        """
        计算余弦相似度
        
        Args:
            features1: 特征向量1
            features2: 特征向量2
            
        Returns:
            相似度 [0, 1]
        """
        # 余弦相似度
        dot_product = np.dot(features1, features2)
        norm1 = np.linalg.norm(features1)
        norm2 = np.linalg.norm(features2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        cos_sim = dot_product / (norm1 * norm2)
        
        # 映射到 [0, 1]
        similarity = (cos_sim + 1) / 2
        
        return float(similarity)
    
    def compare_structure(
        self, 
        user_image: np.ndarray, 
        template_image: np.ndarray
    ) -> Tuple[float, float]:
        """
        对比结构相似度
        
        Args:
            user_image: 用户书写图像
            template_image: 标准字帖图像
            
        Returns:
            Tuple[结构相似度 (0-100), 平衡相似度 (0-100)]
        """
        start_time = time.perf_counter()
        
        # 提取特征
        user_features, template_features = self.infer_pair(user_image, template_image)
        
        # 计算整体相似度 → 结构分
        structure_similarity = self.compute_similarity(user_features, template_features)
        structure_score = structure_similarity * 100
        
        # 计算平衡感知分数
        balance_score = self._compute_balance_score(user_image, template_image)
        
        elapsed = (time.perf_counter() - start_time) * 1000
        self.logger.debug(f"孪生网络对比耗时: {elapsed:.2f}ms")
        
        return structure_score, balance_score
    
    def _compute_balance_score(
        self, 
        user_image: np.ndarray, 
        template_image: np.ndarray
    ) -> float:
        """
        计算平衡感知分数
        
        对比用户字和字帖的重心分布
        
        Args:
            user_image: 用户书写图像
            template_image: 标准字帖图像
            
        Returns:
            平衡分数 (0-100)
        """
        # 获取二值图
        def get_center(binary):
            ink_mask = binary == 0
            if np.sum(ink_mask) == 0:
                return 0.5, 0.5
            y_coords, x_coords = np.where(ink_mask)
            return np.mean(x_coords) / binary.shape[1], np.mean(y_coords) / binary.shape[0]
        
        # 处理用户图像
        if len(user_image.shape) == 3:
            user_gray = cv2.cvtColor(user_image, cv2.COLOR_BGR2GRAY)
        else:
            user_gray = user_image
        _, user_binary = cv2.threshold(user_gray, 127, 255, cv2.THRESH_BINARY)
        user_cx, user_cy = get_center(user_binary)
        
        # 处理字帖图像
        if len(template_image.shape) == 3:
            template_gray = cv2.cvtColor(template_image, cv2.COLOR_BGR2GRAY)
        else:
            template_gray = template_image
        _, template_binary = cv2.threshold(template_gray, 127, 255, cv2.THRESH_BINARY)
        template_cx, template_cy = get_center(template_binary)
        
        # 计算重心偏差
        offset = np.sqrt((user_cx - template_cx)**2 + (user_cy - template_cy)**2)
        
        # 偏差越小，分数越高
        # 最大偏差约为 sqrt(2) ≈ 1.414
        balance_score = max(0, 1 - offset / 0.5) * 100
        
        return balance_score


# 创建全局单例
siamese_engine = SiameseEngine()
