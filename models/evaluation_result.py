"""Evaluation result data model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional
import json


@dataclass
class EvaluationResult:
    """Single evaluation record."""

    total_score: int
    detail_scores: Dict[str, int]
    feedback: str
    timestamp: datetime
    image_path: Optional[str] = None
    processed_image_path: Optional[str] = None
    character_name: Optional[str] = None
    id: Optional[int] = None
    style: Optional[str] = None
    style_confidence: Optional[float] = None
    recognition_status: Optional[str] = None
    recognition_confidence: Optional[float] = None
    score_mode: Optional[str] = None
    score_explanation: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to a serializable dictionary."""
        return {
            "id": self.id,
            "total_score": self.total_score,
            "detail_scores": self.detail_scores,
            "feedback": self.feedback,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "image_path": self.image_path,
            "processed_image_path": self.processed_image_path,
            "character_name": self.character_name,
            "style": self.style,
            "style_confidence": self.style_confidence,
            "recognition_status": self.recognition_status,
            "recognition_confidence": self.recognition_confidence,
            "score_mode": self.score_mode,
            "score_explanation": self.score_explanation,
        }

    def to_json(self) -> str:
        """Convert to formatted JSON."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> "EvaluationResult":
        """Rebuild from a dictionary."""
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
            style=data.get("style"),
            style_confidence=data.get("style_confidence"),
            recognition_status=data.get("recognition_status"),
            recognition_confidence=data.get("recognition_confidence"),
            score_mode=data.get("score_mode"),
            score_explanation=data.get("score_explanation"),
        )

    def __str__(self) -> str:
        """Readable representation."""
        scores_str = ", ".join([f"{k}: {v}" for k, v in self.detail_scores.items()])
        return (
            f"EvaluationResult(total={self.total_score}, "
            f"scores={{{scores_str}}}, "
            f"character={self.character_name}, "
            f"mode={self.score_mode})"
        )

    def get_grade(self) -> str:
        """Human-readable grade."""
        excellent_threshold, good_threshold = self._get_grade_thresholds()
        if self.total_score >= excellent_threshold:
            return "优秀"
        if self.total_score >= good_threshold:
            return "良好"
        return "需加强"

    def get_color(self) -> str:
        """UI color helper."""
        excellent_threshold, good_threshold = self._get_grade_thresholds()
        if self.total_score >= excellent_threshold:
            return "#4CAF50"
        if self.total_score >= good_threshold:
            return "#FF9800"
        return "#F44336"

    @staticmethod
    def _get_grade_thresholds() -> tuple[int, int]:
        """Read thresholds from config with a safe fallback."""
        try:
            from config import EVALUATION_CONFIG

            return (
                int(EVALUATION_CONFIG.get("excellent_threshold", 80)),
                int(EVALUATION_CONFIG.get("good_threshold", 60)),
            )
        except Exception:
            return (80, 60)
