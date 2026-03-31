"""Build a real-image quality manifest for the single-chain scorer."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path

import cv2
import numpy as np


@dataclass
class QualitySample:
    path: str
    character: str
    label: str
    provenance: str
    source_group: str
    proxy_score: float


def load_gray(path: Path) -> np.ndarray | None:
    return cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)


def parse_character_from_name(path: Path) -> str:
    stem = path.stem
    if "_good_" in stem:
        return stem.split("_good_", 1)[0]
    return stem


def compute_proxy_score(image: np.ndarray) -> float:
    """A lightweight bootstrap score used only for mining real samples."""
    if image is None or image.size == 0:
        return 0.0

    normalized = cv2.normalize(image, None, 0, 255, cv2.NORM_MINMAX)
    if float(np.mean(normalized)) < 127:
        normalized = 255 - normalized

    _, binary = cv2.threshold(normalized, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    points = cv2.findNonZero(binary)
    if points is None:
        return 0.0

    x, y, w, h = cv2.boundingRect(points)
    h_img, w_img = binary.shape
    bbox_area = max(1.0, float(w * h))
    image_area = max(1.0, float(h_img * w_img))
    fg_ratio = float(np.mean(binary > 0))
    bbox_ratio = bbox_area / image_area

    moments = cv2.moments(binary)
    if moments["m00"] > 0:
        cx = moments["m10"] / moments["m00"]
        cy = moments["m01"] / moments["m00"]
    else:
        cx = w_img / 2.0
        cy = h_img / 2.0
    center_distance = float(
        np.hypot((cx - w_img / 2.0) / max(1.0, w_img / 2.0), (cy - h_img / 2.0) / max(1.0, h_img / 2.0))
    )

    comp_count = max(0, cv2.connectedComponents(binary)[0] - 1)
    edge_touch = float(
        np.mean(binary[0, :] > 0)
        + np.mean(binary[-1, :] > 0)
        + np.mean(binary[:, 0] > 0)
        + np.mean(binary[:, -1] > 0)
    ) / 4.0

    size_score = 1.0 - min(abs(bbox_ratio - 0.42) / 0.42, 1.0)
    ink_score = 1.0 - min(abs(fg_ratio - 0.18) / 0.18, 1.0)
    center_score = max(0.0, 1.0 - center_distance)
    component_score = max(0.0, 1.0 - min(comp_count / 18.0, 1.0))
    edge_score = max(0.0, 1.0 - min(edge_touch / 0.15, 1.0))

    return float(
        0.28 * size_score
        + 0.22 * ink_score
        + 0.24 * center_score
        + 0.14 * component_score
        + 0.12 * edge_score
    )


def select_ranked(paths: list[Path], medium_limit: int, bad_limit: int) -> tuple[list[QualitySample], list[QualitySample]]:
    scored: list[tuple[Path, float]] = []
    for path in paths:
        image = load_gray(path)
        if image is None:
            continue
        scored.append((path, compute_proxy_score(image)))

    scored.sort(key=lambda item: item[1], reverse=True)
    if not scored:
        return [], []

    medium_start = max(0, int(len(scored) * 0.30))
    medium_end = max(medium_start + 1, int(len(scored) * 0.70))
    bad_start = max(medium_end, int(len(scored) * 0.82))

    medium_candidates = scored[medium_start:medium_end]
    bad_candidates = scored[bad_start:]

    medium = [
        QualitySample(
            path=str(path),
            character=parse_character_from_name(path),
            label="medium",
            provenance="public_character/good",
            source_group="bootstrap_clean_real",
            proxy_score=score,
        )
        for path, score in medium_candidates[:medium_limit]
    ]
    bad = [
        QualitySample(
            path=str(path),
            character=parse_character_from_name(path),
            label="bad",
            provenance="public_character/good",
            source_group="bootstrap_hard_real",
            proxy_score=score,
        )
        for path, score in bad_candidates[:bad_limit]
    ]
    return medium, bad


def build_manifest(public_character_dir: Path, output_path: Path, limit_good: int, limit_medium: int, limit_bad: int) -> dict:
    originals_dir = public_character_dir / "originals"
    good_dir = public_character_dir / "good"
    pool = sorted(originals_dir.glob("*.png")) + sorted(good_dir.glob("*.png"))
    scored: list[tuple[Path, float, str]] = []
    for path in pool:
        image = load_gray(path)
        if image is None:
            continue
        provenance = "public_character/originals" if path.parent == originals_dir else "public_character/good"
        scored.append((path, compute_proxy_score(image), provenance))

    scored.sort(key=lambda item: item[1], reverse=True)
    good_end = max(1, int(len(scored) * 0.18))
    medium_start = max(good_end, int(len(scored) * 0.38))
    medium_end = max(medium_start + 1, int(len(scored) * 0.68))
    bad_start = max(medium_end, int(len(scored) * 0.84))

    good_samples = [
        QualitySample(
            path=str(path),
            character=parse_character_from_name(path),
            label="good",
            provenance=provenance,
            source_group="bootstrap_top_real",
            proxy_score=score,
        )
        for path, score, provenance in scored[:good_end][:limit_good]
    ]

    medium_samples = [
        QualitySample(
            path=str(path),
            character=parse_character_from_name(path),
            label="medium",
            provenance=provenance,
            source_group="bootstrap_mid_real",
            proxy_score=score,
        )
        for path, score, provenance in scored[medium_start:medium_end][:limit_medium]
    ]

    bad_samples = [
        QualitySample(
            path=str(path),
            character=parse_character_from_name(path),
            label="bad",
            provenance=provenance,
            source_group="bootstrap_hard_real",
            proxy_score=score,
        )
        for path, score, provenance in scored[bad_start:][:limit_bad]
    ]

    all_samples = good_samples + medium_samples + bad_samples
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for sample in all_samples:
            handle.write(json.dumps(sample.__dict__, ensure_ascii=False) + "\n")

    summary = {
        "manifest": str(output_path),
        "counts": {
            "good": len(good_samples),
            "medium": len(medium_samples),
            "bad": len(bad_samples),
            "total": len(all_samples),
        },
    }
    (output_path.with_suffix(".summary.json")).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a quality manifest for the InkPi single-chain scorer.")
    parser.add_argument("--public-character", type=Path, required=True, help="Path to data/public_character")
    parser.add_argument("--output", type=Path, required=True, help="Output manifest .jsonl file")
    parser.add_argument("--limit-good", type=int, default=6000)
    parser.add_argument("--limit-medium", type=int, default=12000)
    parser.add_argument("--limit-bad", type=int, default=8000)
    args = parser.parse_args()

    summary = build_manifest(
        public_character_dir=args.public_character,
        output_path=args.output,
        limit_good=args.limit_good,
        limit_medium=args.limit_medium,
        limit_bad=args.limit_bad,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
