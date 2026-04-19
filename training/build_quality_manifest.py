"""Build a script-aware real-image quality manifest for the quality scorer."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys

import cv2
import numpy as np

try:
    from models.evaluation_framework import (
        RUBRIC_VERSION,
        build_rubric_items,
        build_rubric_preview_total,
        get_rubric_definition,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from models.evaluation_framework import (
        RUBRIC_VERSION,
        build_rubric_items,
        build_rubric_preview_total,
        get_rubric_definition,
    )

try:
    from training.quality_model_layout import (
        DEFAULT_MANIFEST_ROOT,
        DEFAULT_PUBLIC_CHARACTER_ROOT,
        DEFAULT_SCRIPT,
        build_manifest_path,
        normalize_script,
        resolve_script_source_dir,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from training.quality_model_layout import (
        DEFAULT_MANIFEST_ROOT,
        DEFAULT_PUBLIC_CHARACTER_ROOT,
        DEFAULT_SCRIPT,
        build_manifest_path,
        normalize_script,
        resolve_script_source_dir,
    )


@dataclass
class QualitySample:
    path: str
    script: str
    character: str
    label: str
    provenance: str
    source_group: str
    proxy_score: float
    rubric_version: str
    rubric_family: str
    rubric_items: list[dict]
    rubric_preview_total: float | None
    manual_review_score: float | None
    manual_review_level: str | None
    manual_review_notes: str | None


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


def proxy_to_anchor(proxy_score: float) -> int:
    if proxy_score >= 0.90:
        return 100
    if proxy_score >= 0.72:
        return 80
    if proxy_score >= 0.54:
        return 60
    if proxy_score >= 0.36:
        return 40
    return 20


def bootstrap_rubric_payload(script: str, proxy_score: float) -> tuple[str, list[dict], float | None]:
    definition = get_rubric_definition(script)
    anchor = proxy_to_anchor(proxy_score)
    rubric_scores = {item["key"]: anchor for item in definition["items"]}
    rubric_items = build_rubric_items(rubric_scores, script=script)
    return definition["rubric_family"], rubric_items, build_rubric_preview_total(rubric_items)


def make_quality_sample(
    *,
    path: Path,
    script: str,
    label: str,
    provenance: str,
    source_group: str,
    proxy_score: float,
) -> QualitySample:
    rubric_family, rubric_items, rubric_preview_total = bootstrap_rubric_payload(script, proxy_score)
    return QualitySample(
        path=str(path),
        script=script,
        character=parse_character_from_name(path),
        label=label,
        provenance=provenance,
        source_group=source_group,
        proxy_score=proxy_score,
        rubric_version=RUBRIC_VERSION,
        rubric_family=rubric_family,
        rubric_items=rubric_items,
        rubric_preview_total=rubric_preview_total,
        manual_review_score=None,
        manual_review_level=None,
        manual_review_notes=None,
    )


def select_ranked(
    paths: list[Path],
    medium_limit: int,
    bad_limit: int,
    script: str,
) -> tuple[list[QualitySample], list[QualitySample]]:
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
        make_quality_sample(
            path=path,
            script=script,
            label="medium",
            provenance="public_character/good",
            source_group="bootstrap_clean_real",
            proxy_score=score,
        )
        for path, score in medium_candidates[:medium_limit]
    ]
    bad = [
        make_quality_sample(
            path=path,
            script=script,
            label="bad",
            provenance="public_character/good",
            source_group="bootstrap_hard_real",
            proxy_score=score,
        )
        for path, score in bad_candidates[:bad_limit]
    ]
    return medium, bad


def build_manifest(
    public_character_dir: Path,
    output_path: Path,
    limit_good: int,
    limit_medium: int,
    limit_bad: int,
    script: str,
) -> dict:
    script = normalize_script(script)
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
        make_quality_sample(
            path=path,
            script=script,
            label="good",
            provenance=provenance,
            source_group="bootstrap_top_real",
            proxy_score=score,
        )
        for path, score, provenance in scored[:good_end][:limit_good]
    ]

    medium_samples = [
        make_quality_sample(
            path=path,
            script=script,
            label="medium",
            provenance=provenance,
            source_group="bootstrap_mid_real",
            proxy_score=score,
        )
        for path, score, provenance in scored[medium_start:medium_end][:limit_medium]
    ]

    bad_samples = [
        make_quality_sample(
            path=path,
            script=script,
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
        "script": script,
        "rubric_version": RUBRIC_VERSION,
        "rubric_family": get_rubric_definition(script)["rubric_family"],
        "public_character_dir": str(public_character_dir),
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
    parser = argparse.ArgumentParser(description="Build a script-specific quality manifest for the InkPi scorer.")
    parser.add_argument(
        "--script",
        type=str,
        default=DEFAULT_SCRIPT,
        help="Script bucket to build: regular or running.",
    )
    parser.add_argument(
        "--public-character",
        type=Path,
        default=DEFAULT_PUBLIC_CHARACTER_ROOT,
        help="Path to the public character root or to a single script directory.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output manifest .jsonl file. Defaults to data/quality_manifests/<script>/quality_manifest.jsonl",
    )
    parser.add_argument("--limit-good", type=int, default=6000)
    parser.add_argument("--limit-medium", type=int, default=12000)
    parser.add_argument("--limit-bad", type=int, default=8000)
    args = parser.parse_args()
    script = normalize_script(args.script)
    source_dir = resolve_script_source_dir(args.public_character, script)
    output_path = args.output or build_manifest_path(DEFAULT_MANIFEST_ROOT, script)

    summary = build_manifest(
        public_character_dir=source_dir,
        output_path=output_path,
        limit_good=args.limit_good,
        limit_medium=args.limit_medium,
        limit_bad=args.limit_bad,
        script=script,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
