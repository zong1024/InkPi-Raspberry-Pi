#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${DATA_DIR:-$ROOT_DIR/data/public_character}"
MANIFEST_PATH="${MANIFEST_PATH:-$ROOT_DIR/data/quality_manifest.jsonl}"
OUTPUT_DIR="${OUTPUT_DIR:-$ROOT_DIR/models/quality_scorer_build}"
INPUT_SIZE="${INPUT_SIZE:-32}"
LIMIT_GOOD="${LIMIT_GOOD:-6000}"
LIMIT_MEDIUM="${LIMIT_MEDIUM:-12000}"
LIMIT_BAD="${LIMIT_BAD:-8000}"
MAX_ITER="${MAX_ITER:-24}"

python "$ROOT_DIR/training/build_quality_manifest.py" \
  --public-character "$DATA_DIR" \
  --output "$MANIFEST_PATH" \
  --limit-good "$LIMIT_GOOD" \
  --limit-medium "$LIMIT_MEDIUM" \
  --limit-bad "$LIMIT_BAD"

python "$ROOT_DIR/training/train_quality_scorer.py" \
  --manifest "$MANIFEST_PATH" \
  --output-dir "$OUTPUT_DIR" \
  --input-size "$INPUT_SIZE" \
  --max-iter "$MAX_ITER"

cp "$OUTPUT_DIR/quality_scorer.onnx" "$ROOT_DIR/models/quality_scorer.onnx"
echo "Quality scorer exported to $ROOT_DIR/models/quality_scorer.onnx"
