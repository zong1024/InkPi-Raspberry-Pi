"""Evaluation result data model for the source-backed InkPi rubric."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any

from models.evaluation_framework import (
    LEGACY_RUBRIC_VERSION,
    RUBRIC_VERSION,
    build_practice_profile,
    build_rubric_items,
    build_rubric_preview_total,
    build_scope_boundary,
    get_rubric_source_catalog,
    get_script_label,
    normalize_script,
    summarize_rubric_items,
)


QUALITY_LABELS = {
    "good": "甲",
    "medium": "乙",
    "bad": "待提升",
}

QUALITY_COLORS = {
    "good": "#B90F1F",
    "medium": "#AB6D2F",
    "bad": "#B34B3E",
}


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


def _normalize_json_list(value: Any) -> list[dict[str, Any]] | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)] or None
        return None
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)] or None
    return None


@dataclass
class EvaluationResult:
    """Single evaluation record."""

    total_score: int
    feedback: str
    timestamp: datetime
    script: str = "regular"
    character_name: str | None = None
    ocr_confidence: float | None = None
    quality_level: str = "medium"
    quality_confidence: float | None = None
    image_path: str | None = None
    processed_image_path: str | None = None
    rubric_version: str | None = None
    rubric_family: str | None = None
    rubric_items: list[dict[str, Any]] | None = None
    rubric_summary: dict[str, Any] | None = None
    rubric_source_refs: list[dict[str, Any]] | None = None
    rubric_preview_total: float | None = None
    score_debug: dict[str, Any] | None = None
    dimension_scores: dict[str, int] | None = None
    id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        script = self.get_script()
        rubric_items = self.get_rubric_items()
        legacy_dimension_scores = self.get_dimension_scores()
        payload = {
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
            "script": script,
            "script_label": self.get_script_label(),
            "rubric_version": self.get_rubric_version(),
            "rubric_family": self.get_rubric_family(),
            "rubric_items": rubric_items,
            "rubric_summary": self.get_rubric_summary(),
            "rubric_source_refs": self.get_rubric_source_refs(),
            "rubric_preview_total": self.get_rubric_preview_total(),
            "practice_profile": self.get_practice_profile(),
            "scope_boundary": build_scope_boundary(script),
            "score_debug": self.score_debug,
            "is_legacy_standard": self.is_legacy_standard(),
        }
        if legacy_dimension_scores is not None:
            payload["dimension_scores"] = legacy_dimension_scores
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvaluationResult":
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now()

        quality_level = data.get("quality_level") or _level_from_score(int(data.get("total_score", 0)))
        score_debug = _normalize_json_dict(data.get("score_debug"))
        rubric_items = _normalize_json_list(data.get("rubric_items"))
        rubric_summary = _normalize_json_dict(data.get("rubric_summary"))
        rubric_source_refs = _normalize_json_list(data.get("rubric_source_refs"))
        legacy_dimension_scores = _normalize_json_dict(data.get("dimension_scores"))

        return cls(
            id=data.get("id"),
            total_score=int(data["total_score"]),
            feedback=data["feedback"],
            timestamp=timestamp,
            image_path=data.get("image_path"),
            processed_image_path=data.get("processed_image_path"),
            script=normalize_script(data.get("script")),
            character_name=data.get("character_name"),
            ocr_confidence=data.get("ocr_confidence"),
            quality_level=quality_level,
            quality_confidence=data.get("quality_confidence"),
            rubric_version=str(data.get("rubric_version") or "").strip() or None,
            rubric_family=str(data.get("rubric_family") or "").strip() or None,
            rubric_items=rubric_items,
            rubric_summary=rubric_summary,
            rubric_source_refs=rubric_source_refs,
            rubric_preview_total=float(data["rubric_preview_total"])
            if data.get("rubric_preview_total") is not None
            else None,
            score_debug=score_debug,
            dimension_scores=legacy_dimension_scores,
        )

    def __str__(self) -> str:
        return (
            f"EvaluationResult(total={self.total_score}, character={self.character_name}, "
            f"script={self.get_script()}, quality={self.quality_level}, rubric={self.get_rubric_family()})"
        )

    def get_grade(self) -> str:
        return QUALITY_LABELS.get(self.quality_level, QUALITY_LABELS["medium"])

    def get_color(self) -> str:
        return QUALITY_COLORS.get(self.quality_level, QUALITY_COLORS["medium"])

    def get_script(self) -> str:
        return normalize_script(self.script)

    def get_script_label(self) -> str:
        return get_script_label(self.get_script())

    def get_rubric_version(self) -> str:
        if self.rubric_items:
            return str(self.rubric_version or RUBRIC_VERSION)
        if self.rubric_version:
            return str(self.rubric_version)
        return LEGACY_RUBRIC_VERSION

    def get_rubric_family(self) -> str:
        if self.rubric_family:
            return self.rubric_family
        return "legacy_v0" if self.is_legacy_standard() else f"{self.get_script()}_rubric_v1"

    def get_rubric_items(self) -> list[dict[str, Any]] | None:
        if self.rubric_items:
            return self.rubric_items
        if self.dimension_scores:
            return None
        return None

    def get_rubric_summary(self) -> dict[str, Any] | None:
        if self.rubric_summary:
            return self.rubric_summary
        return summarize_rubric_items(self.get_rubric_items())

    def get_rubric_source_refs(self) -> list[dict[str, Any]] | None:
        if self.rubric_source_refs:
            return self.rubric_source_refs
        rubric_items = self.get_rubric_items()
        if not rubric_items:
            return None
        codes: list[str] = []
        for item in rubric_items:
            for code in item.get("basis_codes", []):
                if code not in codes:
                    codes.append(code)
        return get_rubric_source_catalog(codes)

    def get_rubric_preview_total(self) -> float | None:
        if self.rubric_preview_total is not None:
            return float(self.rubric_preview_total)
        return build_rubric_preview_total(self.get_rubric_items())

    def get_dimension_scores(self) -> dict[str, int] | None:
        if not self.dimension_scores:
            return None
        return {
            key: int(value)
            for key, value in self.dimension_scores.items()
            if value is not None
        }

    def is_legacy_standard(self) -> bool:
        return not bool(self.rubric_items)

    def get_rubric_items_for_ui(self) -> list[dict[str, Any]]:
        return self.get_rubric_items() or []

    def get_practice_profile(self) -> dict[str, Any]:
        return build_practice_profile(
            self.get_rubric_items(),
            total_score=int(self.total_score),
            quality_level=self.quality_level,
            character_name=self.character_name,
            script=self.get_script(),
            rubric_version=self.get_rubric_version(),
        )

    @classmethod
    def from_rubric_scores(
        cls,
        *,
        total_score: int,
        feedback: str,
        timestamp: datetime,
        script: str,
        character_name: str | None,
        ocr_confidence: float | None,
        quality_level: str,
        quality_confidence: float | None,
        image_path: str | None,
        processed_image_path: str | None,
        rubric_family: str,
        rubric_scores: dict[str, int],
        score_debug: dict[str, Any] | None = None,
    ) -> "EvaluationResult":
        normalized_script = normalize_script(script)
        rubric_items = build_rubric_items(rubric_scores, script=normalized_script)
        return cls(
            total_score=total_score,
            feedback=feedback,
            timestamp=timestamp,
            script=normalized_script,
            character_name=character_name,
            ocr_confidence=ocr_confidence,
            quality_level=quality_level,
            quality_confidence=quality_confidence,
            image_path=image_path,
            processed_image_path=processed_image_path,
            rubric_version=RUBRIC_VERSION,
            rubric_family=rubric_family,
            rubric_items=rubric_items,
            rubric_summary=summarize_rubric_items(rubric_items),
            rubric_source_refs=None,
            rubric_preview_total=build_rubric_preview_total(rubric_items),
            score_debug=score_debug,
        )


def _level_from_score(score: int) -> str:
    if score >= 85:
        return "good"
    if score >= 70:
        return "medium"
    return "bad"
