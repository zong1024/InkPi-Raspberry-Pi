"""Regression checks for manually locked evaluation characters."""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from services.evaluation_service import evaluation_service
from services.preprocessing_service import preprocessing_service
from services.template_manager import template_manager


def create_teaching_sheet_image() -> np.ndarray:
    """Create a practice-sheet-like image with a central calligraphy subject."""
    img = np.ones((520, 520, 3), dtype=np.uint8) * 226

    for offset in range(-520, 520, 18):
        cv2.line(
            img,
            (max(offset, 0), max(-offset, 0)),
            (min(519 + offset, 519), min(519, 519 - offset)),
            (210, 206, 194),
            1,
        )

    cv2.rectangle(img, (22, 22), (498, 498), (90, 90, 90), 2)
    cv2.line(img, (22, 22), (498, 498), (130, 130, 130), 1)
    cv2.line(img, (498, 22), (22, 498), (130, 130, 130), 1)
    cv2.line(img, (260, 22), (260, 498), (130, 130, 130), 1)
    cv2.line(img, (22, 260), (498, 260), (130, 130, 130), 1)

    cv2.putText(img, "A", (180, 70), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (50, 50, 50), 3, cv2.LINE_AA)
    cv2.putText(img, "B", (360, 70), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (50, 50, 50), 3, cv2.LINE_AA)
    cv2.putText(img, "C", (56, 266), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (50, 50, 50), 3, cv2.LINE_AA)
    cv2.putText(img, "D", (372, 432), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (50, 50, 50), 3, cv2.LINE_AA)

    cv2.ellipse(img, (185, 292), (88, 20), -28, 0, 180, (24, 24, 24), 26)
    cv2.line(img, (212, 212), (165, 372), (24, 24, 24), 30)
    cv2.line(img, (286, 116), (286, 422), (24, 24, 24), 24)
    cv2.ellipse(img, (358, 238), (58, 82), 0, 10, 330, (24, 24, 24), 28)
    cv2.line(img, (288, 238), (406, 238), (24, 24, 24), 24)

    return img


def main() -> int:
    image = create_teaching_sheet_image()
    processed, _ = preprocessing_service.preprocess(image, save_processed=False)

    result = evaluation_service.evaluate(processed, character_name="shui")
    expected = template_manager.to_display_character("shui")

    if result.character_name != expected:
        print(f"FAIL locked character mismatch: expected={expected}, got={result.character_name}")
        return 1

    print(f"PASS locked character propagated: {result.character_name}, score={result.total_score}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
