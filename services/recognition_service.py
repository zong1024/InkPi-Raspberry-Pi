"""Hybrid open-set character recognition built on ROI extraction and prototype matching."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import time
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import numpy as np

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DATA_DIR
from models.recognition_result import RecognitionResult
from services.character_geometry_service import CharacterSubject, character_geometry_service
from services.siamese_engine import siamese_engine
from services.template_manager import template_manager


@dataclass
class TemplatePrototype:
    """Cached normalized template prototype."""

    character_key: str
    display_character: str
    style_key: str
    display_style: str
    path: str
    subject: CharacterSubject


class RecognitionService:
    """Recognize supported characters while explicitly rejecting unknown ones."""

    def __init__(self, model_path: str | None = None, use_quantized: bool = True) -> None:
        self.logger = logging.getLogger(__name__)
        self.model_dir = DATA_DIR / "models"
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.model_path = Path(model_path) if model_path else self.model_dir / (
            "ch_recognize_mobile_int8.onnx" if use_quantized else "ch_recognize_mobile.onnx"
        )
        self.use_quantized = use_quantized
        self.geometry = character_geometry_service
        self.prototypes: List[TemplatePrototype] = []
        self.impostor_ceilings: Dict[str, float] = {}
        self.accept_score = 84.0
        self.min_open_margin = 0.0
        self.min_support_margin = 0.0
        self.min_gap_top2 = 2.5
        self.min_gap_top3 = 3.8
        self._load_prototypes()

    def recognize(self, image: np.ndarray, top_k: int = 5) -> RecognitionResult:
        """Recognize a processed single-character image with open-set rejection."""
        start_time = time.time()
        subject = self.geometry.extract_subject(image)
        if subject is None:
            return self._finalize(
                RecognitionResult(
                    character="",
                    confidence=0.0,
                    candidates=[],
                    source="prototype_rejected",
                    status="rejected",
                    reason="未检测到稳定的单字主体。",
                ),
                start_time,
            )

        if not self.prototypes:
            return self._finalize(
                RecognitionResult(
                    character="",
                    confidence=0.0,
                    candidates=[],
                    source="prototype_missing",
                    status="missing_templates",
                    reason="当前模板库为空，无法执行字符识别。",
                    roi_bbox=subject.bbox,
                ),
                start_time,
            )

        ranked = self._rank_candidates(subject)
        ordered = self._aggregate_candidates(ranked)
        if not ordered:
            return self._finalize(
                RecognitionResult(
                    character="",
                    confidence=0.0,
                    candidates=[],
                    source="prototype_missing",
                    status="missing_templates",
                    reason="当前模板库为空，无法执行字符识别。",
                    roi_bbox=subject.bbox,
                ),
                start_time,
            )

        top = ordered[0]
        second = ordered[1] if len(ordered) > 1 else None
        third = ordered[2] if len(ordered) > 2 else None
        open_margin = top["score"] - self.impostor_ceilings.get(top["character_key"], top["score"] - 1.0)
        support_margin = self._support_margin(ordered)
        gap2 = top["score"] - (second["score"] if second else 0.0)
        gap3 = top["score"] - (third["score"] if third else 0.0)

        diagnostics = {
            "top_score": round(top["score"], 3),
            "gap_top2": round(gap2, 3),
            "gap_top3": round(gap3, 3),
            "open_margin": round(open_margin, 3),
            "support_margin": round(support_margin, 3),
            "dominant_share": round(subject.dominant_share, 3),
            "component_count": float(subject.component_count),
            "ink_ratio": round(subject.ink_ratio, 3),
        }

        candidates = [
            (
                candidate["display_character"],
                self._candidate_confidence(candidate["score"], ordered, candidate["character_key"]),
            )
            for candidate in ordered[:top_k]
        ]

        result = self._classify_match(
            top=top,
            second=second,
            third=third,
            ordered=ordered,
            candidates=candidates,
            diagnostics=diagnostics,
            roi_bbox=subject.bbox,
        )
        return self._finalize(result, start_time)

    def recognize_batch(self, images: List[np.ndarray], top_k: int = 5) -> List[RecognitionResult]:
        """Recognize a batch of images."""
        return [self.recognize(image, top_k=top_k) for image in images]

    def download_model(self, model_type: str = "mobile") -> None:
        """Document how to install an optional large-vocabulary OCR model."""
        self.logger.info("Optional OCR model installation remains manual. Suggested type: %s", model_type)
        self.logger.info("Drop OCR models under %s if you later extend the recognizer.", self.model_dir)

    def is_model_loaded(self) -> bool:
        """This recognizer currently relies on geometric prototypes rather than an OCR classifier."""
        return False

    def get_model_info(self) -> Dict[str, str]:
        """Return recognizer metadata for diagnostics."""
        return {
            "model_path": str(self.model_path),
            "model_exists": str(self.model_path.exists()),
            "model_loaded": "False",
            "prototype_count": str(len(self.prototypes)),
            "characters": ",".join(sorted({proto.character_key for proto in self.prototypes})),
            "open_margin": str(self.min_open_margin),
            "support_margin": str(self.min_support_margin),
        }

    def _load_prototypes(self) -> None:
        self.prototypes = []
        for template_info in template_manager.iter_templates():
            template = cv2.imread(template_info["path"], cv2.IMREAD_GRAYSCALE)
            if template is None:
                continue
            subject = self.geometry.extract_subject(template)
            if subject is None:
                self.logger.warning("Skip unusable template: %s", template_info["path"])
                continue
            character_key = template_manager.resolve_character_key(template_info["char"])
            style_key = template_manager.resolve_style_key(template_info["style"])
            self.prototypes.append(
                TemplatePrototype(
                    character_key=character_key,
                    display_character=template_manager.to_display_character(character_key),
                    style_key=style_key,
                    display_style=template_manager.to_display_style(style_key),
                    path=template_info["path"],
                    subject=subject,
                )
            )
        self.impostor_ceilings = self._build_impostor_ceilings()
        self.logger.info(
            "Recognition prototypes ready: %s characters, %s templates",
            len({proto.character_key for proto in self.prototypes}),
            len(self.prototypes),
        )

    def _build_impostor_ceilings(self) -> Dict[str, float]:
        ceilings: Dict[str, float] = {}
        for prototype in self.prototypes:
            impostor_scores = []
            for other in self.prototypes:
                if other.character_key == prototype.character_key:
                    continue
                score, _ = self._score_subject_against_prototype(prototype.subject, other)
                impostor_scores.append(score)
            ceilings[prototype.character_key] = max(impostor_scores) if impostor_scores else 0.0
        return ceilings

    def _rank_candidates(self, subject: CharacterSubject) -> List[Dict]:
        ranked = []
        for prototype in self.prototypes:
            score, metrics = self._score_subject_against_prototype(subject, prototype)
            ranked.append(
                {
                    "character_key": prototype.character_key,
                    "display_character": prototype.display_character,
                    "style_key": prototype.style_key,
                    "display_style": prototype.display_style,
                    "score": float(score),
                    "metrics": metrics,
                }
            )
        return ranked

    def _aggregate_candidates(self, ranked: List[Dict]) -> List[Dict]:
        best_by_character: Dict[str, Dict] = {}
        for candidate in ranked:
            character_key = candidate["character_key"]
            if character_key not in best_by_character or candidate["score"] > best_by_character[character_key]["score"]:
                best_by_character[character_key] = candidate
        return sorted(best_by_character.values(), key=lambda item: item["score"], reverse=True)

    def _score_subject_against_prototype(self, subject: CharacterSubject, prototype: TemplatePrototype) -> Tuple[float, Dict[str, float]]:
        structure_score, balance_score = siamese_engine.compare_structure(subject.binary, prototype.subject.binary)
        structure = structure_score / 100.0
        balance = balance_score / 100.0
        signature_metrics = self.geometry.compare_signature(subject.signature, prototype.subject.signature)
        contour = self.geometry.contour_similarity(subject.binary, prototype.subject.binary)
        coverage = self.geometry.coverage_similarity(subject, prototype.subject)

        total = 100.0 * (
            structure * 0.36
            + balance * 0.08
            + signature_metrics["signature"] * 0.22
            + signature_metrics["topology"] * 0.14
            + contour * 0.10
            + coverage * 0.10
        )
        metrics = {
            "structure": float(structure),
            "balance": float(balance),
            "signature": float(signature_metrics["signature"]),
            "projection": float(signature_metrics["projection"]),
            "zoning": float(signature_metrics["zoning"]),
            "orientation": float(signature_metrics["orientation"]),
            "hu": float(signature_metrics["hu"]),
            "topology": float(signature_metrics["topology"]),
            "contour": float(contour),
            "coverage": float(coverage),
        }
        return total, metrics

    def _classify_match(
        self,
        top: Dict,
        second: Dict | None,
        third: Dict | None,
        ordered: List[Dict],
        candidates: List[Tuple[str, float]],
        diagnostics: Dict[str, float],
        roi_bbox: Tuple[int, int, int, int],
    ) -> RecognitionResult:
        second_metrics = second["metrics"] if second else {}
        top_metrics = top["metrics"]
        open_margin = float(diagnostics["open_margin"])
        support_margin = float(diagnostics["support_margin"])
        gap2 = float(diagnostics["gap_top2"])
        gap3 = float(diagnostics["gap_top3"])

        strong_votes = sum(
            [
                top_metrics["structure"] >= 0.78,
                top_metrics["signature"] >= 0.72,
                top_metrics["topology"] >= 0.66,
                top_metrics["contour"] >= 0.56,
                top_metrics["coverage"] >= 0.70,
                open_margin >= self.min_open_margin,
            ]
        )
        margin_votes = sum(
            [
                top_metrics["structure"] - second_metrics.get("structure", 0.0) >= 0.03,
                top_metrics["signature"] - second_metrics.get("signature", 0.0) >= 0.03,
                top_metrics["topology"] - second_metrics.get("topology", 0.0) >= 0.03,
                top_metrics["contour"] - second_metrics.get("contour", 0.0) >= 0.02,
            ]
        )
        diagnostics["strong_votes"] = float(strong_votes)
        diagnostics["margin_votes"] = float(margin_votes)
        confidence = self._candidate_confidence(top["score"], ordered, top["character_key"])

        is_match = (
            top["score"] >= self.accept_score
            and gap2 >= self.min_gap_top2
            and gap3 >= self.min_gap_top3
            and strong_votes >= 4
            and margin_votes >= 1
        )
        if is_match:
            return RecognitionResult(
                character=top["display_character"],
                confidence=max(0.72, float(confidence)),
                candidates=candidates,
                source=f"prototype:{top['display_style']}",
                status="matched",
                diagnostics=diagnostics,
                roi_bbox=roi_bbox,
            )

        if gap2 < 1.8 or gap3 < 2.8 or margin_votes < 1:
            return RecognitionResult(
                character="",
                confidence=float(confidence),
                candidates=candidates,
                source="prototype_ambiguous",
                status="ambiguous",
                reason="当前字形与多个内置评测字模板过于接近，系统无法稳定判定。",
                diagnostics=diagnostics,
                roi_bbox=roi_bbox,
            )

        return RecognitionResult(
            character="",
            confidence=float(confidence),
            candidates=candidates,
            source="prototype_unsupported",
            status="unsupported",
            reason="当前作品是毛笔字，但字形不在当前内置评测字库中。",
            diagnostics=diagnostics,
            roi_bbox=roi_bbox,
        )

    def _candidate_confidence(self, score: float, ordered: List[Dict], character_key: str) -> float:
        second_score = ordered[1]["score"] if len(ordered) > 1 else 0.0
        open_margin = score - self.impostor_ceilings.get(character_key, 0.0)
        support_margin = self._support_margin(ordered)
        score_term = np.clip((score - 78.0) / 14.0, 0.0, 1.0)
        gap_term = np.clip((score - second_score) / 6.0, 0.0, 1.0)
        open_term = np.clip((open_margin + 2.0) / 8.0, 0.0, 1.0)
        support_term = np.clip((support_margin + 1.0) / 8.0, 0.0, 1.0)
        return float(score_term * 0.55 + gap_term * 0.25 + open_term * 0.10 + support_term * 0.10)

    def _support_margin(self, ordered: List[Dict]) -> float:
        if len(ordered) <= 1:
            return float(ordered[0]["score"]) if ordered else 0.0
        tail = [candidate["score"] for candidate in ordered[1:4]]
        return float(ordered[0]["score"] - float(np.mean(tail)))

    def _finalize(self, result: RecognitionResult, start_time: float) -> RecognitionResult:
        result.inference_time_ms = (time.time() - start_time) * 1000
        return result


recognition_service = RecognitionService()
