"""Evaluation result data model for the single-chain OCR + ONNX pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from typing import Optional


QUALITY_LABELS = {
    "good": "好",
    "medium": "中",
    "bad": "坏",
}

QUALITY_COLORS = {
    "good": "#3F8451",
    "medium": "#AB6D2F",
    "bad": "#B34B3E",
}


@dataclass
class EvaluationResult:
    """Single evaluation record."""

    total_score: int
    feedback: str
    timestamp: datetime
    character_name: Optional[str] = None
    ocr_confidence: Optional[float] = None
    quality_level: str = "medium"
    quality_confidence: Optional[float] = None
    image_path: Optional[str] = None
    processed_image_path: Optional[str] = None
    id: Optional[int] = None

    def to_dict(self) -> dict:
        """Convert to a serializable dictionary."""
        return {
            "id": self.id,
            "total_score": int(self.total_score),
            "feedback": self.feedback,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "image_path": self.image_path,
            "processed_image_path": self.processed_image_path,
            "character_name": self.character_name,
            "ocr_confidence": self.ocr_confidence,
            "quality_level": self.quality_level,
            "quality_label": self.get_grade(),
            "quality_confidence": self.quality_confidence,
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

        quality_level = data.get("quality_level") or _level_from_score(int(data.get("total_score", 0)))

        return cls(
            id=data.get("id"),
            total_score=int(data["total_score"]),
            feedback=data["feedback"],
            timestamp=timestamp,
            image_path=data.get("image_path"),
            processed_image_path=data.get("processed_image_path"),
            character_name=data.get("character_name"),
            ocr_confidence=data.get("ocr_confidence"),
            quality_level=quality_level,
            quality_confidence=data.get("quality_confidence"),
        )

    def __str__(self) -> str:
        """Readable representation."""
        return (
            f"EvaluationResult(total={self.total_score}, "
            f"character={self.character_name}, "
            f"quality={self.quality_level}, "
            f"ocr={self.ocr_confidence})"
        )

    def get_grade(self) -> str:
        """Human-readable quality label."""
        return QUALITY_LABELS.get(self.quality_level, QUALITY_LABELS["medium"])

    def get_color(self) -> str:
        """UI color helper."""
        return QUALITY_COLORS.get(self.quality_level, QUALITY_COLORS["medium"])


def _level_from_score(score: int) -> str:
    if score >= 85:
        return "good"
    if score >= 70:
        return "medium"
    return "bad"
