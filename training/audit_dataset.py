from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

QUALITY_LEVELS = ("good", "medium", "poor")
QUALITY_FILENAME_PATTERN = re.compile(
    r"^(?P<char>.+?)_(?P<quality>good|medium|poor)_(?P<index>\d+)$"
)


def parse_sample_character(sample_path: Path) -> tuple[str | None, str | None]:
    match = QUALITY_FILENAME_PATTERN.match(sample_path.stem)
    if match:
        return match.group("char"), match.group("quality")

    parts = sample_path.stem.split("_")
    if len(parts) >= 3 and parts[-2] in QUALITY_LEVELS:
        return "_".join(parts[:-2]), parts[-2]

    return None, None


def audit_dataset_dir(data_dir: Path) -> dict:
    data_dir = Path(data_dir)
    templates = {p.stem for p in (data_dir / "originals").glob("*.png")}
    total_samples = 0
    matched_samples = 0
    quality_counts = {quality: 0 for quality in QUALITY_LEVELS}
    matched_quality_counts = {quality: 0 for quality in QUALITY_LEVELS}
    matched_chars = set()
    unmatched_examples: list[str] = []

    for quality in QUALITY_LEVELS:
        q_dir = data_dir / quality
        if not q_dir.exists():
            continue

        for sample_path in q_dir.glob("*.png"):
            total_samples += 1
            quality_counts[quality] += 1
            char_name, parsed_quality = parse_sample_character(sample_path)

            if parsed_quality not in QUALITY_LEVELS:
                if len(unmatched_examples) < 10:
                    unmatched_examples.append(sample_path.name)
                continue

            if char_name in templates:
                matched_samples += 1
                matched_quality_counts[quality] += 1
                matched_chars.add(char_name)
            elif len(unmatched_examples) < 10:
                unmatched_examples.append(sample_path.name)

    unmatched_samples = total_samples - matched_samples
    matched_ratio = matched_samples / total_samples if total_samples else 0.0
    return {
        "templates": len(templates),
        "samples": total_samples,
        "matched_samples": matched_samples,
        "unmatched_samples": unmatched_samples,
        "matched_ratio": matched_ratio,
        "unique_chars": len(matched_chars),
        "quality_counts": quality_counts,
        "matched_quality_counts": matched_quality_counts,
        "unmatched_examples": unmatched_examples,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit an InkPi training dataset.")
    parser.add_argument("--data", required=True, help="Dataset directory to inspect")
    parser.add_argument("--strict", action="store_true", help="Exit with code 1 when the dataset looks unsafe")
    parser.add_argument("--min-match-ratio", type=float, default=0.5)
    parser.add_argument("--min-matched-samples", type=int, default=100)
    args = parser.parse_args()

    payload = audit_dataset_dir(Path(args.data))
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if args.strict:
        if payload["matched_samples"] < args.min_matched_samples:
            raise SystemExit(1)
        if payload["matched_ratio"] < args.min_match_ratio:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
