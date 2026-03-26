"""Shared data structures for the isolated full-recognition pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class RecognitionCandidate:
    """Single OCR or reranking candidate."""

    key: str
    display: str
    provider_score: float
    rerank_score: float = 0.0
    final_score: float = 0.0
    provider: str = ""
    style: Optional[str] = None
    evidence: Dict[str, float] = field(default_factory=dict)


@dataclass
class RecognitionDecision:
    """Final next-gen recognition verdict."""

    status: str
    character_key: Optional[str]
    character_display: Optional[str]
    confidence: float
    candidates: List[RecognitionCandidate] = field(default_factory=list)
    reason: Optional[str] = None
    diagnostics: Dict[str, float | str] = field(default_factory=dict)
    roi_bbox: Optional[Tuple[int, int, int, int]] = None

