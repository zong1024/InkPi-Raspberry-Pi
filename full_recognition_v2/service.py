"""Application-facing wrapper around the isolated full-recognition pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np

from full_recognition_v2.factory import build_default_full_pipeline
from full_recognition_v2.pipeline import FullRecognitionPipeline
from full_recognition_v2.types import RecognitionDecision


@dataclass
class FullRecognitionCandidateView:
    """UI-friendly candidate summary."""

    key: str
    display: str
    confidence: float
    source: str
    rerank_score: float = 0.0
    final_score: float = 0.0


@dataclass
class FullRecognitionAnalysis:
    """High-level result that UI/API layers can consume directly."""

    status: str
    character_key: Optional[str]
    character_display: Optional[str]
    confidence: float
    score_ready: bool
    template_ready: bool
    title: str
    message: str
    next_action: str
    candidates: List[FullRecognitionCandidateView] = field(default_factory=list)
    diagnostics: Dict[str, float | str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to a plain dictionary."""
        return {
            "status": self.status,
            "character_key": self.character_key,
            "character_display": self.character_display,
            "confidence": self.confidence,
            "score_ready": self.score_ready,
            "template_ready": self.template_ready,
            "title": self.title,
            "message": self.message,
            "next_action": self.next_action,
            "candidates": [
                {
                    "key": item.key,
                    "display": item.display,
                    "confidence": item.confidence,
                    "source": item.source,
                    "rerank_score": item.rerank_score,
                    "final_score": item.final_score,
                }
                for item in self.candidates
            ],
            "diagnostics": self.diagnostics,
        }


class FullRecognitionService:
    """Thin adapter that turns pipeline decisions into product-level semantics."""

    def __init__(self, pipeline: FullRecognitionPipeline | None = None) -> None:
        self.pipeline = pipeline or build_default_full_pipeline()

    def analyze(self, image: np.ndarray, limit: int = 8) -> FullRecognitionAnalysis:
        """Analyze an image and return a UI-ready interpretation."""
        decision = self.pipeline.analyze(image, limit=limit)
        return self._present(decision)

    def analyze_path(self, path: str | Path, limit: int = 8) -> FullRecognitionAnalysis:
        """Load an image from disk and analyze it."""
        image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            return FullRecognitionAnalysis(
                status="load_error",
                character_key=None,
                character_display=None,
                confidence=0.0,
                score_ready=False,
                template_ready=False,
                title="图片读取失败",
                message="指定路径的图片无法读取，请检查文件是否存在或格式是否正确。",
                next_action="retry",
            )
        return self.analyze(image, limit=limit)

    def _present(self, decision: RecognitionDecision) -> FullRecognitionAnalysis:
        candidates = [
            FullRecognitionCandidateView(
                key=item.key,
                display=item.display,
                confidence=float(item.provider_score),
                source=item.provider,
                rerank_score=float(item.rerank_score),
                final_score=float(item.final_score),
            )
            for item in decision.candidates[:5]
        ]

        if decision.status == "matched":
            display = decision.character_display or decision.character_key
            return FullRecognitionAnalysis(
                status=decision.status,
                character_key=decision.character_key,
                character_display=display,
                confidence=decision.confidence,
                score_ready=True,
                template_ready=True,
                title=f"已识别为 {display}",
                message="字符已经锁定，并且本地模板库可以继续进入评分阶段。",
                next_action="score",
                candidates=candidates,
                diagnostics=decision.diagnostics,
            )

        if decision.status == "untemplated":
            display = decision.character_display or decision.character_key
            return FullRecognitionAnalysis(
                status=decision.status,
                character_key=decision.character_key,
                character_display=display,
                confidence=decision.confidence,
                score_ready=False,
                template_ready=False,
                title=f"已识别为 {display}",
                message=decision.reason or "当前已经识别出字符，但本地评分模板尚未覆盖它。",
                next_action="add_template",
                candidates=candidates,
                diagnostics=decision.diagnostics,
            )

        if decision.status == "ambiguous":
            return FullRecognitionAnalysis(
                status=decision.status,
                character_key=None,
                character_display=None,
                confidence=decision.confidence,
                score_ready=False,
                template_ready=False,
                title="识别结果不稳定",
                message=decision.reason or "多个候选字过于接近，当前不建议继续评分。",
                next_action="retry",
                candidates=candidates,
                diagnostics=decision.diagnostics,
            )

        if decision.status == "rejected":
            return FullRecognitionAnalysis(
                status=decision.status,
                character_key=None,
                character_display=None,
                confidence=decision.confidence,
                score_ready=False,
                template_ready=False,
                title="未检测到稳定单字",
                message=decision.reason or "请重新取景，确保画面里只有一个清晰的毛笔字主体。",
                next_action="retry",
                candidates=candidates,
                diagnostics=decision.diagnostics,
            )

        return FullRecognitionAnalysis(
            status=decision.status,
            character_key=decision.character_key,
            character_display=decision.character_display,
            confidence=decision.confidence,
            score_ready=False,
            template_ready=False,
            title="当前无法稳定评分",
            message=decision.reason or "这张图暂时无法进入评分阶段。",
            next_action="review",
            candidates=candidates,
            diagnostics=decision.diagnostics,
        )


full_recognition_service = FullRecognitionService()
