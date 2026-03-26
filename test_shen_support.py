"""Regression checks for the built-in 神 character support."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from services.preprocessing_service import preprocessing_service
from services.recognition_flow_service import recognition_flow_service
from services.template_manager import template_manager


ROOT = Path(__file__).parent
SHEN_TEMPLATE = ROOT / "models" / "templates" / "shen_kaishu_processed.png"


def _build_mock_teaching_sheet(template: np.ndarray) -> np.ndarray:
    """Embed the template into a practice-sheet-like background."""
    canvas = np.ones((540, 540, 3), dtype=np.uint8) * 224

    for offset in range(-540, 540, 22):
        cv2.line(
            canvas,
            (max(offset, 0), max(-offset, 0)),
            (min(539 + offset, 539), min(539, 539 - offset)),
            (207, 202, 192),
            1,
        )

    cv2.rectangle(canvas, (28, 28), (512, 512), (104, 104, 104), 2)
    cv2.line(canvas, (28, 28), (512, 512), (140, 140, 140), 1)
    cv2.line(canvas, (512, 28), (28, 512), (140, 140, 140), 1)
    cv2.line(canvas, (270, 28), (270, 512), (140, 140, 140), 1)
    cv2.line(canvas, (28, 270), (512, 270), (140, 140, 140), 1)

    cv2.putText(canvas, "A", (220, 64), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (60, 60, 60), 2, cv2.LINE_AA)
    cv2.putText(canvas, "B", (372, 64), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (60, 60, 60), 2, cv2.LINE_AA)
    cv2.putText(canvas, "C", (70, 310), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (60, 60, 60), 2, cv2.LINE_AA)

    resized = cv2.resize(template, (294, 294), interpolation=cv2.INTER_NEAREST)
    subject = np.ones((294, 294, 3), dtype=np.uint8) * 224
    subject[resized == 0] = (22, 22, 22)

    top = 120
    left = 123
    region = canvas[top : top + 294, left : left + 294]
    mask = resized == 0
    region[mask] = subject[mask]
    return canvas


def main() -> int:
    expected_key = template_manager.resolve_character_key("神")
    expected_display = template_manager.to_display_character(expected_key)

    if expected_key != "shen":
        print(f"FAIL alias mapping mismatch: expected 'shen', got {expected_key!r}")
        return 1

    if not SHEN_TEMPLATE.exists():
        print(f"FAIL missing template: {SHEN_TEMPLATE}")
        return 1

    template = cv2.imread(str(SHEN_TEMPLATE), cv2.IMREAD_GRAYSCALE)
    if template is None:
        print(f"FAIL unreadable template: {SHEN_TEMPLATE}")
        return 1

    mock_sheet = _build_mock_teaching_sheet(template)
    processed, _ = preprocessing_service.preprocess(mock_sheet, save_processed=False)
    flow = recognition_flow_service.analyze(processed)

    if flow.character_name != expected_display:
        print(
            "FAIL shen recognition mismatch: "
            f"expected={expected_display}, got={flow.character_name}, candidates={flow.candidates[:3]}"
        )
        return 1

    print(
        "PASS shen support: "
        f"character={flow.character_name}, style={flow.style}, confidence={flow.recognition_confidence:.2f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
