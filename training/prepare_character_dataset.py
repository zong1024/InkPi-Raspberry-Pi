from __future__ import annotations

import argparse
import json
import random
import shutil
from pathlib import Path


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}


def list_images(path: Path) -> list[Path]:
    return sorted(
        p for p in path.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )


def sanitize_name(name: str) -> str:
    return name.strip().replace("/", "_").replace("\\", "_")


def build_dataset(
    input_dir: Path,
    output_dir: Path,
    min_images_per_char: int,
    max_chars: int | None,
    max_images_per_char: int | None,
    seed: int,
) -> dict:
    rng = random.Random(seed)
    output_dir.mkdir(parents=True, exist_ok=True)
    originals_dir = output_dir / "originals"
    good_dir = output_dir / "good"
    medium_dir = output_dir / "medium"
    poor_dir = output_dir / "poor"
    for directory in (originals_dir, good_dir, medium_dir, poor_dir):
        directory.mkdir(parents=True, exist_ok=True)

    char_dirs = [p for p in sorted(input_dir.iterdir()) if p.is_dir()]
    candidates: list[tuple[str, list[Path]]] = []
    skipped: list[dict] = []
    for char_dir in char_dirs:
        images = list_images(char_dir)
        if len(images) < min_images_per_char:
            skipped.append({"character": char_dir.name, "images": len(images)})
            continue
        candidates.append((sanitize_name(char_dir.name), images))

    candidates.sort(key=lambda item: len(item[1]), reverse=True)
    if max_chars is not None:
        candidates = candidates[:max_chars]

    manifest = {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "min_images_per_char": min_images_per_char,
        "selected_characters": 0,
        "good_samples": 0,
        "skipped_characters": skipped[:100],
        "characters": [],
    }

    for char_name, images in candidates:
        selected = images[:]
        rng.shuffle(selected)
        if max_images_per_char is not None:
            selected = selected[:max_images_per_char]
        if len(selected) < 2:
            continue

        template = selected[0]
        shutil.copy2(template, originals_dir / f"{char_name}.png")

        copied_samples = 0
        for index, image_path in enumerate(selected[1:], start=1):
            target = good_dir / f"{char_name}_good_{index:04d}.png"
            shutil.copy2(image_path, target)
            copied_samples += 1

        manifest["selected_characters"] += 1
        manifest["good_samples"] += copied_samples
        manifest["characters"].append(
            {
                "character": char_name,
                "source_images": len(images),
                "used_images": len(selected),
                "good_samples": copied_samples,
            }
        )

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a folder-per-character calligraphy dataset into InkPi training format."
    )
    parser.add_argument("--input", required=True, help="Root directory containing one subfolder per character")
    parser.add_argument("--output", required=True, help="Output InkPi dataset directory")
    parser.add_argument("--min-images-per-char", type=int, default=4)
    parser.add_argument("--max-chars", type=int, default=None)
    parser.add_argument("--max-images-per-char", type=int, default=24)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--clear-output",
        action="store_true",
        help="Delete the output directory before conversion",
    )
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)
    if not input_dir.exists():
        raise SystemExit(f"Input directory does not exist: {input_dir}")

    if args.clear_output and output_dir.exists():
        shutil.rmtree(output_dir)

    manifest = build_dataset(
        input_dir=input_dir,
        output_dir=output_dir,
        min_images_per_char=args.min_images_per_char,
        max_chars=args.max_chars,
        max_images_per_char=args.max_images_per_char,
        seed=args.seed,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
