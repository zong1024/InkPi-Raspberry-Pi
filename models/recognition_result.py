"""
InkPi 书法评测系统 - 识别结果模型

存储汉字识别的结果
"""
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from datetime import datetime


@dataclass
class RecognitionResult:
    """汉字识别结果"""
    
    # 识别的汉字
    character: str
    
    # 置信度 (0.0 - 1.0)
    confidence: float
    
    # 候选字列表 [(汉字, 置信度), ...]
    candidates: List[Tuple[str, float]] = field(default_factory=list)
    
    # 识别耗时 (毫秒)
    inference_time_ms: float = 0.0
    
    # 识别时间
    timestamp: datetime = field(default_factory=datetime.now)
    
    # 图像路径（可选）
    image_path: Optional[str] = None

    # 结果来源（onnx / template / fallback 等）
    source: Optional[str] = None
    
    def __str__(self) -> str:
        return f"RecognitionResult(character='{self.character}', confidence={self.confidence:.2%})"
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "character": self.character,
            "confidence": self.confidence,
            "candidates": self.candidates,
            "inference_time_ms": self.inference_time_ms,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "image_path": self.image_path,
            "source": self.source,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "RecognitionResult":
        """从字典创建实例"""
        return cls(
            character=data.get("character", ""),
            confidence=data.get("confidence", 0.0),
            candidates=data.get("candidates", []),
            inference_time_ms=data.get("inference_time_ms", 0.0),
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else datetime.now(),
            image_path=data.get("image_path"),
            source=data.get("source"),
        )
    
    def is_confident(self, threshold: float = 0.8) -> bool:
        """检查置信度是否超过阈值"""
        return self.confidence >= threshold
    
    def get_top_candidates(self, n: int = 3) -> List[Tuple[str, float]]:
        """获取前N个候选字"""
        return self.candidates[:n]
