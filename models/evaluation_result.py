"""Evaluation result data model for the single-chain OCR + ONNX pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any

from models.evaluation_framework import build_practice_profile, get_dimension_basis


QUALITY_LABELS = {
    "good": "甲",
    "medium": "乙",
    "bad": "丙",
}

QUALITY_COLORS = {
    "good": "#B90F1F",
    "medium": "#AB6D2F",
    "bad": "#B34B3E",
}

DIMENSION_LABELS = {
    "structure": "结构",
    "stroke": "笔画",
    "integrity": "完整",
    "stability": "稳定",
}

DIMENSION_ORDER = ("structure", "stroke", "integrity", "stability")


def _normalize_json_dict(value: Any) -> dict[str, Any] | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    if isinstance(value, dict):
        return value
    return None


def summarize_dimension_scores(
    dimension_scores: dict[str, int] | None,
) -> dict[str, dict[str, Any]] | None:
    if not dimension_scores:
        return None

    available_items = [
        (key, int(dimension_scores[key]))
        for key in DIMENSION_ORDER
        if key in dimension_scores and dimension_scores[key] is not None
    ]
    if not available_items:
        return None

    strongest_key, strongest_score = max(available_items, key=lambda item: (item[1], -DIMENSION_ORDER.index(item[0])))
    weakest_key, weakest_score = min(available_items, key=lambda item: (item[1], DIMENSION_ORDER.index(item[0])))
    return {
        "best": {
            "key": strongest_key,
            "label": DIMENSION_LABELS.get(strongest_key, strongest_key),
            "score": strongest_score,
        },
        "weakest": {
            "key": weakest_key,
            "label": DIMENSION_LABELS.get(weakest_key, weakest_key),
            "score": weakest_score,
        },
    }


@dataclass
class EvaluationResult:
    """Single evaluation record."""

    total_score: int
    feedback: str
    timestamp: datetime
    character_name: str | None = None
    ocr_confidence: float | None = None
    quality_level: str = "medium"
    quality_confidence: float | None = None
    image_path: str | None = None
    processed_image_path: str | None = None
    dimension_scores: dict[str, int] | None = None
    score_debug: dict[str, Any] | None = None
    id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to a serializable dictionary."""
        dimension_scores = self.get_dimension_scores()
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
            "dimension_scores": dimension_scores,
            "dimension_summary": summarize_dimension_scores(dimension_scores),
            "dimension_basis": get_dimension_basis(dimension_scores),
            "practice_profile": self.get_practice_profile(),
            "score_debug": self.score_debug,
        }

    def to_json(self) -> str:
        """Convert to formatted JSON."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvaluationResult":
        """Rebuild from a dictionary."""
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now()

        quality_level = data.get("quality_level") or _level_from_score(int(data.get("total_score", 0)))
        dimension_scores = _normalize_json_dict(data.get("dimension_scores"))
        score_debug = _normalize_json_dict(data.get("score_debug"))

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
            dimension_scores={
                key: int(value)
                for key, value in (dimension_scores or {}).items()
                if key in DIMENSION_LABELS and value is not None
            }
            or None,
            score_debug=score_debug,
        )

    def __str__(self) -> str:
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

    def get_dimension_scores(self) -> dict[str, int] | None:
        """Return normalized dimension scores in a stable order."""
        if not self.dimension_scores:
            return None
        normalized = {
            key: int(self.dimension_scores[key])
            for key in DIMENSION_ORDER
            if key in self.dimension_scores and self.dimension_scores[key] is not None
        }
        return normalized or None

    def get_dimension_summary(self) -> dict[str, dict[str, Any]] | None:
        """Return strongest and weakest dimension metadata."""
        return summarize_dimension_scores(self.get_dimension_scores())

    def get_dimension_items(self) -> list[dict[str, Any]]:
        """Return ordered dimension items for UI rendering."""
        scores = self.get_dimension_scores() or {}
        return [
            {
                "key": key,
                "label": DIMENSION_LABELS[key],
                "score": int(scores[key]),
            }
            for key in DIMENSION_ORDER
            if key in scores
        ]

    def get_practice_profile(self) -> dict[str, Any]:
        """Return coach-style practice guidance based on current result."""
        return build_practice_profile(
            self.get_dimension_scores(),
            total_score=int(self.total_score),
            quality_level=self.quality_level,
            character_name=self.character_name,
        )


def _level_from_score(score: int) -> str:
    if score >= 85:
        return "good"
    if score >= 70:
        return "medium"
    return "bad"
