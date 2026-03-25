"""Recognition result model with explicit open-set states."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple


@dataclass
class RecognitionResult:
    """Structured output from the character recognition pipeline."""

    character: str
    confidence: float
    candidates: List[Tuple[str, float]] = field(default_factory=list)
    inference_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    image_path: Optional[str] = None
    source: Optional[str] = None
    status: str = "matched"
    reason: Optional[str] = None
    diagnostics: Dict[str, float | str] = field(default_factory=dict)
    roi_bbox: Optional[Tuple[int, int, int, int]] = None

    def __str__(self) -> str:
        return (
            f"RecognitionResult(character='{self.character}', status='{self.status}', "
            f"confidence={self.confidence:.2%})"
        )

    def to_dict(self) -> dict:
        """Serialize to a plain dictionary."""
        return {
            "character": self.character,
            "confidence": self.confidence,
            "candidates": self.candidates,
            "inference_time_ms": self.inference_time_ms,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "image_path": self.image_path,
            "source": self.source,
            "status": self.status,
            "reason": self.reason,
            "diagnostics": self.diagnostics,
            "roi_bbox": list(self.roi_bbox) if self.roi_bbox else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RecognitionResult":
        """Restore from a serialized dictionary."""
        bbox = data.get("roi_bbox")
        return cls(
            character=data.get("character", ""),
            confidence=data.get("confidence", 0.0),
            candidates=data.get("candidates", []),
            inference_time_ms=data.get("inference_time_ms", 0.0),
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else datetime.now(),
            image_path=data.get("image_path"),
            source=data.get("source"),
            status=data.get("status", "matched"),
            reason=data.get("reason"),
            diagnostics=data.get("diagnostics", {}),
            roi_bbox=tuple(bbox) if bbox else None,
        )

    def is_confident(self, threshold: float = 0.8) -> bool:
        """Whether the result is a confident positive match."""
        return self.status == "matched" and self.confidence >= threshold

    def get_top_candidates(self, n: int = 3) -> List[Tuple[str, float]]:
        """Return the top-N candidates."""
        return self.candidates[:n]
