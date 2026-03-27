"""Factory helpers for assembling the isolated full-recognition pipeline."""

from __future__ import annotations

from full_recognition_v2.http_provider import HttpOcrCandidateProvider
from full_recognition_v2.paddle_provider import PaddleOcrCandidateProvider
from full_recognition_v2.pipeline import FullRecognitionPipeline
from full_recognition_v2.providers import NullCandidateProvider


def build_default_full_pipeline() -> FullRecognitionPipeline:
    """Build the isolated next-gen pipeline with optional PaddleOCR frontend."""
    remote_provider = HttpOcrCandidateProvider()
    paddle_provider = PaddleOcrCandidateProvider()
    providers = [
        provider
        for provider in (remote_provider, paddle_provider)
        if getattr(provider, "available", False)
    ]
    if not providers:
        providers = [NullCandidateProvider()]
    return FullRecognitionPipeline(providers=providers)
