"""
InkPi 书法评测系统 - 评测结果数据模型
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict
import json


@dataclass
class EvaluationResult:
    """评测结果数据类"""
    
    total_score: int                              # 总分 (0-100)
    detail_scores: Dict[str, int]                 # 四维评分
    feedback: str                                 # 文字反馈
    timestamp: datetime                           # 评测时间
    image_path: Optional[str] = None              # 原始图片路径
    processed_image_path: Optional[str] = None    # 预处理后图片路径
    character_name: Optional[str] = None          # 字符名称
    id: Optional[int] = None                      # 数据库ID
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "id": self.id,
            "total_score": self.total_score,
            "detail_scores": self.detail_scores,
            "feedback": self.feedback,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "image_path": self.image_path,
            "processed_image_path": self.processed_image_path,
            "character_name": self.character_name,
        }
    
    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_dict(cls, data: dict) -> "EvaluationResult":
        """从字典创建实例"""
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now()
            
        return cls(
            id=data.get("id"),
            total_score=data["total_score"],
            detail_scores=data["detail_scores"],
            feedback=data["feedback"],
            timestamp=timestamp,
            image_path=data.get("image_path"),
            processed_image_path=data.get("processed_image_path"),
            character_name=data.get("character_name"),
        )
    
    def __str__(self) -> str:
        """字符串表示"""
        scores_str = ", ".join([f"{k}: {v}" for k, v in self.detail_scores.items()])
        return (
            f"EvaluationResult(total={self.total_score}, "
            f"scores={{{scores_str}}}, "
            f"character={self.character_name})"
        )
    
    def get_grade(self) -> str:
        """获取等级评价"""
        if self.total_score >= 80:
            return "优秀"
        elif self.total_score >= 60:
            return "良好"
        else:
            return "需加强"
    
    def get_color(self) -> str:
        """获取对应颜色（用于UI显示）"""
        if self.total_score >= 80:
            return "#4CAF50"  # 绿色
        elif self.total_score >= 60:
            return "#FF9800"  # 橙色
        else:
            return "#F44336"  # 红色