"""Next-generation recognition pipeline kept isolated from the current demo."""

from full_recognition_v2.service import (
    FullRecognitionAnalysis,
    FullRecognitionService,
    TemplateBootstrapResult,
    full_recognition_service,
)

__all__ = [
    "FullRecognitionAnalysis",
    "FullRecognitionService",
    "TemplateBootstrapResult",
    "full_recognition_service",
]

