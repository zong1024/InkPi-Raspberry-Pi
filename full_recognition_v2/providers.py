"""Candidate-provider abstractions for the next-gen recognition pipeline."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, List

from full_recognition_v2.types import RecognitionCandidate
from services.template_manager import template_manager


class CandidateProvider(ABC):
    """Abstract top-k candidate source."""

    name = "provider"

    @abstractmethod
    def get_candidates(self, image, limit: int = 8) -> List[RecognitionCandidate]:
        """Return coarse OCR candidates for the given image."""


class NullCandidateProvider(CandidateProvider):
    """Provider that yields no OCR candidates."""

    name = "null"

    def get_candidates(self, image, limit: int = 8) -> List[RecognitionCandidate]:
        return []


class ScriptedCandidateProvider(CandidateProvider):
    """Deterministic provider useful for tests and manual experiments."""

    name = "scripted"

    def __init__(self, keys: Iterable[str]) -> None:
        self.keys = [template_manager.resolve_character_key(key) for key in keys]

    def get_candidates(self, image, limit: int = 8) -> List[RecognitionCandidate]:
        items = []
        for rank, key in enumerate(self.keys[:limit]):
            items.append(
                RecognitionCandidate(
                    key=key,
                    display=template_manager.to_display_character(key),
                    provider_score=max(0.2, 1.0 - rank * 0.08),
                    provider=self.name,
                )
            )
        return items

