"""Application-facing wrapper around the isolated full-recognition pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from full_recognition_v2.factory import build_default_full_pipeline
from full_recognition_v2.pipeline import FullRecognitionPipeline
from full_recognition_v2.types import RecognitionDecision
from services.character_geometry_service import character_geometry_service
from services.template_manager import template_manager


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


@dataclass
class TemplateBootstrapResult:
    """Outcome of turning an analyzed image into a new local template."""

    created: bool
    character_key: Optional[str]
    character_display: Optional[str]
    template_path: Optional[str]
    before_status: str
    after_status: Optional[str]
    message: str

    def to_dict(self) -> dict:
        """Serialize to a plain dictionary."""
        return {
            "created": self.created,
            "character_key": self.character_key,
            "character_display": self.character_display,
            "template_path": self.template_path,
            "before_status": self.before_status,
            "after_status": self.after_status,
            "message": self.message,
        }


class FullRecognitionService:
    """Thin adapter that turns pipeline decisions into product-level semantics."""

    def __init__(self, pipeline: FullRecognitionPipeline | None = None) -> None:
        self.pipeline = pipeline or build_default_full_pipeline()

    @property
    def is_candidate_ready(self) -> bool:
        """Whether an external OCR candidate source is available."""
        return self.pipeline._has_external_candidate_provider()

    def analyze(self, image: np.ndarray, limit: int = 8) -> FullRecognitionAnalysis:
        """Analyze an image and return a UI-ready interpretation."""
        decision = self.pipeline.analyze(image, limit=limit)
        return self._present(decision)

    def analyze_path(self, path: str | Path, limit: int = 8) -> FullRecognitionAnalysis:
        """Load an image from disk and analyze it."""
        image = template_manager.load_image(path, 0)
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

    def bootstrap_template(
        self,
        image: np.ndarray,
        style: str = "kaishu",
        calligrapher: str = "bootstrap",
        min_confidence: float = 0.82,
        force_character: Optional[str] = None,
    ) -> TemplateBootstrapResult:
        """Create a new local template from a high-confidence recognized character image."""
        before = self.analyze(image)
        character_display = self._resolve_bootstrap_character(
            before,
            min_confidence=min_confidence,
            force_character=force_character,
        )
        character_key = template_manager.resolve_character_key(character_display) if character_display else None

        if not character_display:
            return TemplateBootstrapResult(
                created=False,
                character_key=None,
                character_display=None,
                template_path=None,
                before_status=before.status,
                after_status=None,
                message="当前图片还没有足够稳定的字符结果，无法自动建模板。",
            )

        if before.template_ready and not force_character and before.character_display == character_display:
            return TemplateBootstrapResult(
                created=False,
                character_key=character_key,
                character_display=character_display,
                template_path=self._template_path(character_display, style, calligrapher),
                before_status=before.status,
                after_status=before.status,
                message="当前字符已经有可用模板，无需重复生成。",
            )

        bootstrap_confidence = self._bootstrap_confidence(before, character_display)
        if bootstrap_confidence < min_confidence and not force_character:
            return TemplateBootstrapResult(
                created=False,
                character_key=character_key,
                character_display=character_display,
                template_path=None,
                before_status=before.status,
                after_status=None,
                message="识别置信度还不够高，暂时不自动建模板。",
            )

        seed = self.extract_template_seed(image)
        if seed is None:
            return TemplateBootstrapResult(
                created=False,
                character_key=character_key,
                character_display=character_display,
                template_path=None,
                before_status=before.status,
                after_status=None,
                message="未能从图片中提取到稳定的主字区域，无法生成模板。",
            )

        style_key = template_manager.resolve_style_key(style)
        subject = character_geometry_service.extract_subject(seed)
        if subject is None:
            subject = character_geometry_service.extract_subject(image)
        if subject is not None:
            template_image = subject.binary
        else:
            template_image = template_manager.create_template_from_user_image(seed, character_display, style_key)

        created = template_manager.add_template(
            template_image,
            character=character_display,
            style=style_key,
            calligrapher=calligrapher,
        )
        template_path = Path(self._template_path(character_display, style_key, calligrapher))
        if not created:
            return TemplateBootstrapResult(
                created=False,
                character_key=character_key,
                character_display=character_display,
                template_path=None,
                before_status=before.status,
                after_status=None,
                message="模板文件写入失败。",
            )

        if not self._validate_saved_template(template_path):
            self._discard_template(character_display, style_key, calligrapher, template_path)
            return TemplateBootstrapResult(
                created=False,
                character_key=character_key,
                character_display=character_display,
                template_path=None,
                before_status=before.status,
                after_status=None,
                message="生成出的模板主体不稳定，已自动回滚。",
            )

        after = self.analyze(image)
        return TemplateBootstrapResult(
            created=True,
            character_key=template_manager.resolve_character_key(character_display),
            character_display=character_display,
            template_path=str(template_path),
            before_status=before.status,
            after_status=after.status,
            message="模板已生成并加入本地模板库。",
        )

    def extract_template_seed(self, image: np.ndarray) -> np.ndarray | None:
        """Extract a seed crop that is suitable for new template generation."""
        for provider in self.pipeline.providers:
            extractor = getattr(provider, "extract_template_seed", None)
            if callable(extractor):
                seed = extractor(image)
                if seed is not None:
                    return seed

        subject = character_geometry_service.extract_subject(image)
        if subject is not None:
            return subject.binary
        return None

    def _resolve_bootstrap_character(
        self,
        analysis: FullRecognitionAnalysis,
        min_confidence: float,
        force_character: Optional[str] = None,
    ) -> Optional[str]:
        """Pick the safest character label to turn into a new local template."""
        if force_character:
            return force_character

        if analysis.character_display and analysis.confidence >= min_confidence:
            return analysis.character_display

        if analysis.status != "unsupported" or not analysis.candidates:
            return None

        top = analysis.candidates[0]
        second = analysis.candidates[1] if len(analysis.candidates) > 1 else None
        gap_top2 = top.confidence - (second.confidence if second else 0.0)
        if top.confidence >= min_confidence and gap_top2 >= 0.08:
            return top.display
        return None

    def _bootstrap_confidence(self, analysis: FullRecognitionAnalysis, character_display: str) -> float:
        """Estimate how trustworthy the chosen bootstrap label is."""
        if analysis.character_display == character_display:
            return analysis.confidence

        for candidate in analysis.candidates:
            if candidate.display == character_display or candidate.key == character_display:
                return candidate.confidence
        return 0.0

    def _validate_saved_template(self, path: Path) -> bool:
        """Ensure the saved template can be loaded back and still exposes a stable subject."""
        image = template_manager.load_image(path, 0)
        if image is None:
            return False
        return character_geometry_service.extract_subject(image) is not None

    def _discard_template(self, character: str, style: str, calligrapher: str, path: Path) -> None:
        """Remove a newly created template file and in-memory index entry."""
        try:
            if path.exists():
                path.unlink()
        except Exception:
            pass

        normalized_char = template_manager.resolve_character_key(character)
        entries = template_manager._templates.get(normalized_char, [])
        template_manager._templates[normalized_char] = [
            item
            for item in entries
            if not (
                item.get("char") == character
                and template_manager.resolve_style_key(item.get("style", "")) == template_manager.resolve_style_key(style)
                and item.get("calligrapher") == calligrapher
            )
        ]
        if not template_manager._templates[normalized_char]:
            template_manager._templates.pop(normalized_char, None)

        prefix = f"{normalized_char}_{template_manager.resolve_style_key(style)}_"
        template_manager._cache = {
            key: value
            for key, value in template_manager._cache.items()
            if not (key.startswith(prefix) and key.endswith(calligrapher))
        }

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

    def _template_path(self, character: str, style: str, calligrapher: str) -> str:
        return str(template_manager.template_dir / f"{character}_{style}_{calligrapher}.png")


full_recognition_service = FullRecognitionService()
