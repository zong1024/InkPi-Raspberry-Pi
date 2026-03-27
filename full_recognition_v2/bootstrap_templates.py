"""Batch-bootstrap local scoring templates from recognized character images."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, List

import cv2

from full_recognition_v2.service import FullRecognitionService


def iter_images(root: Path) -> Iterable[Path]:
    """Yield image files from a directory or a single file path."""
    if root.is_file():
        yield root
        return

    for path in sorted(root.rglob("*")):
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".webp"} and path.is_file():
            yield path


def bootstrap_directory(
    source: Path,
    min_confidence: float = 0.82,
    style: str = "kaishu",
    calligrapher: str = "bootstrap",
) -> List[dict]:
    """Bootstrap templates for all eligible images in a directory."""
    service = FullRecognitionService()
    report: List[dict] = []

    for image_path in iter_images(source):
        image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            report.append(
                {
                    "file": str(image_path),
                    "created": False,
                    "status": "load_error",
                    "message": "image_load_failed",
                }
            )
            continue

        analysis = service.analyze(image)
        if analysis.status != "untemplated":
            report.append(
                {
                    "file": str(image_path),
                    "created": False,
                    "status": analysis.status,
                    "character": analysis.character_display,
                    "message": "skipped",
                }
            )
            continue

        result = service.bootstrap_template(
            image,
            style=style,
            calligrapher=calligrapher,
            min_confidence=min_confidence,
        )
        report.append(
            {
                "file": str(image_path),
                "created": result.created,
                "status": result.after_status or result.before_status,
                "character": result.character_display,
                "template_path": result.template_path,
                "message": result.message,
            }
        )

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap local templates from a directory of character images.")
    parser.add_argument("source", help="Image file or directory to scan")
    parser.add_argument("--min-confidence", type=float, default=0.82, help="Minimum confidence for auto-bootstrap")
    parser.add_argument("--style", default="kaishu", help="Template style key")
    parser.add_argument("--calligrapher", default="bootstrap", help="Tag used in generated template filenames")
    parser.add_argument("--report", help="Optional JSON report path")
    args = parser.parse_args()

    report = bootstrap_directory(
        Path(args.source),
        min_confidence=args.min_confidence,
        style=args.style,
        calligrapher=args.calligrapher,
    )
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)
    if args.report:
        Path(args.report).write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
