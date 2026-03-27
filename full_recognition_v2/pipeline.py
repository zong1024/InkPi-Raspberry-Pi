"""Isolated next-gen recognition pipeline with pluggable OCR frontends."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import logging
from typing import Dict, Iterable, List

import cv2
import numpy as np

from full_recognition_v2.providers import CandidateProvider, NullCandidateProvider
from full_recognition_v2.types import RecognitionCandidate, RecognitionDecision
from services.character_geometry_service import CharacterSubject, character_geometry_service
from services.siamese_engine import siamese_engine
from services.template_manager import template_manager


@dataclass
class NextGenConfig:
    """Thresholds for open-set decision making."""

    accept_score: float = 86.0
    min_gap_top2: float = 3.0
    min_gap_top3: float = 4.0
    min_provider_bonus: float = 0.0
    single_candidate_accept_score: float = 76.0
    single_candidate_min_provider: float = 0.48
    single_candidate_min_rerank: float = 79.0
    single_candidate_min_structure: float = 72.0
    rerank_weight: float = 0.82
    provider_weight: float = 0.18


class FullRecognitionPipeline:
    """Next-generation recognition flow isolated from the current runtime."""

    def __init__(
        self,
        providers: Iterable[CandidateProvider] | None = None,
        config: NextGenConfig | None = None,
    ) -> None:
        self.logger = logging.getLogger(__name__)
        self.providers = list(providers or [NullCandidateProvider()])
        self.config = config or NextGenConfig()

    def analyze(self, image: np.ndarray, limit: int = 8) -> RecognitionDecision:
        """Run ROI extraction, candidate generation, reranking and open-set decision."""
        subject = character_geometry_service.extract_subject(image)
        if subject is None:
            return RecognitionDecision(
                status="rejected",
                character_key=None,
                character_display=None,
                confidence=0.0,
                reason="未检测到稳定的单字主体。",
            )

        provider_candidates = self._collect_provider_candidates(image, limit=limit)
        reranked = self._rerank(subject, provider_candidates, limit=limit)
        return self._decide(subject, reranked)

    def _collect_provider_candidates(self, image: np.ndarray, limit: int) -> List[RecognitionCandidate]:
        merged: Dict[str, RecognitionCandidate] = {}
        for provider in self.providers:
            try:
                items = provider.get_candidates(image, limit=limit)
            except Exception as exc:  # noqa: BLE001
                self.logger.warning("Candidate provider %s failed: %s", provider.name, exc)
                continue

            for candidate in items:
                key = template_manager.resolve_character_key(candidate.key)
                if key not in merged or candidate.provider_score > merged[key].provider_score:
                    merged[key] = RecognitionCandidate(
                        key=key,
                        display=template_manager.to_display_character(key),
                        provider_score=float(candidate.provider_score),
                        provider=provider.name,
                    )
        return list(merged.values())

    def _rerank(
        self,
        subject: CharacterSubject,
        provider_candidates: List[RecognitionCandidate],
        limit: int,
    ) -> List[RecognitionCandidate]:
        provider_lookup = {candidate.key: candidate for candidate in provider_candidates}
        target_keys = set(provider_lookup.keys()) or set(template_manager.list_available_chars())
        best_by_key: Dict[str, RecognitionCandidate] = {}

        for key in target_keys:
            for template_info in template_manager.iter_character_templates(key):
                template = cv2.imread(template_info["path"], cv2.IMREAD_GRAYSCALE)
                if template is None:
                    continue

                template_subject = character_geometry_service.extract_subject(template)
                if template_subject is None:
                    continue

                rerank_score, evidence = self._score_subject(subject, template_subject)
                provider_score = provider_lookup.get(key).provider_score if key in provider_lookup else 0.0
                final_score = (
                    rerank_score * self.config.rerank_weight
                    + provider_score * 100.0 * self.config.provider_weight
                )
                candidate = RecognitionCandidate(
                    key=key,
                    display=template_manager.to_display_character(key),
                    provider_score=provider_score,
                    rerank_score=rerank_score,
                    final_score=final_score,
                    provider=provider_lookup.get(key).provider if key in provider_lookup else "internal",
                    style=template_manager.to_display_style(template_info["style"]),
                    evidence=evidence,
                )
                if key not in best_by_key or candidate.final_score > best_by_key[key].final_score:
                    best_by_key[key] = candidate

        return sorted(best_by_key.values(), key=lambda item: item.final_score, reverse=True)[:limit]

    def _score_subject(self, subject: CharacterSubject, template_subject: CharacterSubject) -> tuple[float, Dict[str, float]]:
        structure_score, balance_score = siamese_engine.compare_structure(subject.binary, template_subject.binary)
        signature_metrics = character_geometry_service.compare_signature(subject.signature, template_subject.signature)
        contour = character_geometry_service.contour_similarity(subject.binary, template_subject.binary)
        coverage = character_geometry_service.coverage_similarity(subject, template_subject)
        rerank_score = 100.0 * (
            (structure_score / 100.0) * 0.40
            + (balance_score / 100.0) * 0.08
            + signature_metrics["signature"] * 0.22
            + signature_metrics["topology"] * 0.14
            + contour * 0.08
            + coverage * 0.08
        )
        evidence = {
            "structure": float(structure_score),
            "balance": float(balance_score),
            "signature": float(signature_metrics["signature"] * 100.0),
            "topology": float(signature_metrics["topology"] * 100.0),
            "contour": float(contour * 100.0),
            "coverage": float(coverage * 100.0),
        }
        return rerank_score, evidence

    def _decide(self, subject: CharacterSubject, candidates: List[RecognitionCandidate]) -> RecognitionDecision:
        if not candidates:
            return RecognitionDecision(
                status="unsupported",
                character_key=None,
                character_display=None,
                confidence=0.0,
                reason="当前没有可用候选字或模板。",
                roi_bbox=subject.bbox,
            )

        top = candidates[0]
        second = candidates[1] if len(candidates) > 1 else None
        third = candidates[2] if len(candidates) > 2 else None
        gap_top2 = top.final_score - (second.final_score if second else 0.0)
        gap_top3 = top.final_score - (third.final_score if third else 0.0)

        diagnostics = {
            "top_score": round(top.final_score, 3),
            "gap_top2": round(gap_top2, 3),
            "gap_top3": round(gap_top3, 3),
            "provider_score": round(top.provider_score, 3),
            "dominant_share": round(subject.dominant_share, 3),
            "component_count": float(subject.component_count),
            "ink_ratio": round(subject.ink_ratio, 3),
        }
        confidence = self._confidence(top, second, third)

        if (
            top.final_score >= self.config.accept_score
            and gap_top2 >= self.config.min_gap_top2
            and gap_top3 >= self.config.min_gap_top3
            and top.provider_score >= self.config.min_provider_bonus
        ):
            return RecognitionDecision(
                status="matched",
                character_key=top.key,
                character_display=top.display,
                confidence=confidence,
                candidates=candidates,
                diagnostics=diagnostics,
                roi_bbox=subject.bbox,
            )

        if second is None and self._is_single_candidate_match(top):
            return RecognitionDecision(
                status="matched",
                character_key=top.key,
                character_display=top.display,
                confidence=max(confidence, 0.62),
                candidates=candidates,
                diagnostics=diagnostics,
                roi_bbox=subject.bbox,
            )

        if gap_top2 < self.config.min_gap_top2 or gap_top3 < self.config.min_gap_top3:
            return RecognitionDecision(
                status="ambiguous",
                character_key=None,
                character_display=None,
                confidence=confidence,
                candidates=candidates,
                reason="多个候选字得分过近，拒绝硬猜。",
                diagnostics=diagnostics,
                roi_bbox=subject.bbox,
            )

        return RecognitionDecision(
            status="unsupported",
            character_key=None,
            character_display=None,
            confidence=confidence,
            candidates=candidates,
            reason="画面像毛笔字，但当前候选集和模板库都无法稳定覆盖。",
            diagnostics=diagnostics,
            roi_bbox=subject.bbox,
        )

    def _confidence(
        self,
        top: RecognitionCandidate,
        second: RecognitionCandidate | None,
        third: RecognitionCandidate | None,
    ) -> float:
        gap_top2 = top.final_score - (second.final_score if second else 0.0)
        gap_top3 = top.final_score - (third.final_score if third else 0.0)
        score_term = np.clip((top.final_score - 78.0) / 16.0, 0.0, 1.0)
        gap_term = np.clip(gap_top2 / 8.0, 0.0, 1.0)
        gap3_term = np.clip(gap_top3 / 10.0, 0.0, 1.0)
        provider_term = np.clip(top.provider_score, 0.0, 1.0)
        return float(score_term * 0.5 + gap_term * 0.2 + gap3_term * 0.15 + provider_term * 0.15)

    def _is_single_candidate_match(self, top: RecognitionCandidate) -> bool:
        structure = float(top.evidence.get("structure", 0.0))
        return (
            top.final_score >= self.config.single_candidate_accept_score
            and top.provider_score >= self.config.single_candidate_min_provider
            and top.rerank_score >= self.config.single_candidate_min_rerank
            and structure >= self.config.single_candidate_min_structure
        )


full_recognition_pipeline = FullRecognitionPipeline()
