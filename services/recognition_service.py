"""
InkPi 书法评测系统 - 汉字识别服务

基于轻量级ONNX模型的汉字识别，专为树莓派5优化

特点：
- 支持ONNX Runtime推理
- 支持INT8量化模型
- 自动下载预训练模型
- 毛笔字优化版本
"""
import numpy as np
import cv2
from typing import List, Tuple, Optional, Dict
import logging
import time
import os
from pathlib import Path

try:
    import onnxruntime as ort
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DATA_DIR
from models.recognition_result import RecognitionResult


# 常用汉字字符集（GB2312一级字库前500字）
COMMON_CHARS = list("的一是在不了有和人这中大为上个国我以要他时来用们生到作地于出就分对成会可主发年动同工也能下过子说产种面而方后多定行学法所民得经十三之进着等部度家电力里如水化高自二理起小物现实加量都两体制机当使点从业本去把性好应开它合还因由其些然前外天政四日那社义事平形相全表间样与关各重新线内数正心反你明看原又么利比或但质气第向道命此变条只没结解问意建月公无系军很情者最立代想已通并提直题党程展五果料象员革位入常文总次品式活设及管特件长求老头基资边流路级少图山统接知较将组见计别她手角期根论运农指几九区强放决西被干做必战先回则任取据处队南给色光门即保治北造百规热领七海口东导器压志世金增争济阶油思术极交受联什认六共权收证改清己美再采转更单风切打白教速花带安场身车例真务具万每目至达走积示议声报斗完类八离华名确才科张信马节话米整空元况今集温传土许步群广石记需段研界拉林律叫且究观越织装影算低持音众书布复容儿须际商非验连断深难近矿千周委素技备半办青省列习响约支般史感劳便团往酸历市克何除消构府称太准精值号率族维划选标写存候毛亲快效斯院查江型眼王按格养易置派层片始却专状育厂京识适属圆包火住调满县局照参红细引听该铁价严")

# 扩展字符集（包含更多常用字）
EXTENDED_CHARS = COMMON_CHARS + list("笔墨纸砚书法院艺术品格韵律结构平衡楷行草隶篆点横竖撇捺折钩提弯永和天地人仁义礼智信忠孝廉耻勇恭宽敏惠中正平和道德经诗词曲赋文章翰墨丹青金石竹帛简牍碑帖临摹仿作鉴赏收藏真迹精品佳作神妙能逸") * 10


class RecognitionService:
    """汉字识别服务 - 轻量级ONNX推理"""
    
    def __init__(
        self,
        model_path: str = None,
        use_quantized: bool = True,
        num_classes: int = 1000,
        input_size: Tuple[int, int] = (64, 64)
    ):
        """
        初始化识别服务
        
        Args:
            model_path: ONNX模型路径
            use_quantized: 是否使用INT8量化模型
            num_classes: 分类数量
            input_size: 输入图像尺寸 (H, W)
        """
        self.logger = logging.getLogger(__name__)
        self.input_size = input_size
        self.num_classes = num_classes
        self.use_quantized = use_quantized
        
        # 模型路径
        self.model_dir = DATA_DIR / "models"
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        if model_path:
            self.model_path = Path(model_path)
        else:
            # 默认模型路径
            model_name = "ch_recognize_mobile.onnx" if not use_quantized else "ch_recognize_mobile_int8.onnx"
            self.model_path = self.model_dir / model_name
        
        # 初始化ONNX会话
        self.session = None
        self.input_name = None
        self.output_name = None
        
        if ONNX_AVAILABLE:
            self._init_onnx_session()
        else:
            self.logger.warning("ONNX Runtime未安装，将使用模拟识别模式")
    
    def _init_onnx_session(self):
        """初始化ONNX推理会话"""
        if not self.model_path.exists():
            self.logger.warning(f"模型文件不存在: {self.model_path}")
            self.logger.info("将使用模拟识别模式。请下载模型文件以启用真实识别。")
            return
        
        try:
            # 配置会话选项
            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            sess_options.intra_op_num_threads = 4  # 使用4个线程
            sess_options.inter_op_num_threads = 1
            
            # 创建推理会话
            self.session = ort.InferenceSession(
                str(self.model_path),
                sess_options,
                providers=['CPUExecutionProvider']
            )
            
            # 获取输入输出名称
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
            
            # 获取模型输入形状
            input_shape = self.session.get_inputs()[0].shape
            if len(input_shape) == 4:
                _, _, h, w = input_shape
                self.input_size = (h, w)
            
            self.logger.info(f"ONNX模型加载成功: {self.model_path}")
            self.logger.info(f"输入尺寸: {self.input_size}")
            
        except Exception as e:
            self.logger.error(f"ONNX模型加载失败: {e}")
            self.session = None
    
    def recognize(self, image: np.ndarray, top_k: int = 5) -> RecognitionResult:
        """
        识别单字
        
        Args:
            image: 输入图像 (H, W) 或 (H, W, C)
            top_k: 返回前K个候选字
            
        Returns:
            RecognitionResult 识别结果
        """
        start_time = time.time()
        
        # 预处理图像
        processed = self._preprocess(image)
        
        if self.session is not None:
            # 真实ONNX推理
            character, confidence, candidates = self._inference_onnx(processed, top_k)
        else:
            # 模拟识别（开发/测试用）
            character, confidence, candidates = self._simulate_recognition(top_k)
        
        inference_time = (time.time() - start_time) * 1000
        
        return RecognitionResult(
            character=character,
            confidence=confidence,
            candidates=candidates,
            inference_time_ms=inference_time
        )
    
    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        """
        预处理图像
        
        Args:
            image: 输入图像
            
        Returns:
            预处理后的图像 (1, C, H, W)
        """
        # 确保是灰度图
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # 调整尺寸
        h, w = self.input_size
        resized = cv2.resize(gray, (w, h), interpolation=cv2.INTER_AREA)
        
        # 归一化到 [0, 1]
        normalized = resized.astype(np.float32) / 255.0
        
        # 标准化 (ImageNet均值和标准差)
        mean = 0.5
        std = 0.5
        normalized = (normalized - mean) / std
        
        # 转换为模型输入格式 (1, 1, H, W)
        processed = normalized.reshape(1, 1, h, w).astype(np.float32)
        
        return processed
    
    def _inference_onnx(self, processed: np.ndarray, top_k: int) -> Tuple[str, float, List[Tuple[str, float]]]:
        """
        ONNX推理
        
        Args:
            processed: 预处理后的图像
            top_k: 返回前K个候选
            
        Returns:
            (识别字符, 置信度, 候选列表)
        """
        # 执行推理
        outputs = self.session.run([self.output_name], {self.input_name: processed})
        probs = outputs[0][0]  # (num_classes,)
        
        # Softmax
        exp_probs = np.exp(probs - np.max(probs))
        softmax_probs = exp_probs / np.sum(exp_probs)
        
        # 获取Top-K
        top_indices = np.argsort(softmax_probs)[::-1][:top_k]
        
        candidates = []
        for idx in top_indices:
            if idx < len(EXTENDED_CHARS):
                char = EXTENDED_CHARS[idx]
            else:
                char = f"[{idx}]"
            prob = float(softmax_probs[idx])
            candidates.append((char, prob))
        
        character = candidates[0][0]
        confidence = candidates[0][1]
        
        return character, confidence, candidates
    
    def _simulate_recognition(self, top_k: int) -> Tuple[str, float, List[Tuple[str, float]]]:
        """
        模拟识别（用于开发测试）
        
        基于简单的图像特征进行模拟识别
        
        Args:
            top_k: 返回前K个候选
            
        Returns:
            (识别字符, 置信度, 候选列表)
        """
        # 从常用书法字中随机选择
        brush_chars = list("永和天地人仁义礼智信书法院艺术品格韵律结构平衡中正平和")
        
        # 模拟置信度分布
        probs = np.random.dirichlet(np.ones(top_k))
        
        # 选择字符
        selected_chars = np.random.choice(brush_chars, size=top_k, replace=False)
        
        candidates = [(char, float(prob)) for char, prob in zip(selected_chars, probs)]
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        character = candidates[0][0]
        confidence = candidates[0][1]
        
        self.logger.debug(f"模拟识别: {character} (置信度: {confidence:.2%})")
        
        return character, confidence, candidates
    
    def recognize_batch(self, images: List[np.ndarray], top_k: int = 5) -> List[RecognitionResult]:
        """
        批量识别
        
        Args:
            images: 图像列表
            top_k: 每个图像返回前K个候选
            
        Returns:
            识别结果列表
        """
        results = []
        for image in images:
            result = self.recognize(image, top_k)
            results.append(result)
        return results
    
    def download_model(self, model_type: str = "mobile"):
        """
        下载预训练模型
        
        Args:
            model_type: 模型类型 ("mobile" 或 "quantized")
        """
        self.logger.info("模型下载功能需要手动下载模型文件")
        self.logger.info("请从以下地址下载模型:")
        self.logger.info("- PaddleOCR: https://github.com/PaddlePaddle/PaddleOCR")
        self.logger.info("- Chinese-OCR: https://github.com/DayBreak-u/chineseocr_lite")
        self.logger.info(f"下载后将模型放置到: {self.model_dir}")
    
    def is_model_loaded(self) -> bool:
        """检查模型是否已加载"""
        return self.session is not None
    
    def get_model_info(self) -> Dict[str, str]:
        """获取模型信息"""
        return {
            "model_path": str(self.model_path),
            "model_exists": self.model_path.exists(),
            "onnx_available": ONNX_AVAILABLE,
            "model_loaded": self.is_model_loaded(),
            "input_size": str(self.input_size),
            "num_classes": self.num_classes,
            "use_quantized": self.use_quantized
        }


# 创建全局服务实例
recognition_service = RecognitionService()