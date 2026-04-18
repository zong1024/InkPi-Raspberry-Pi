#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${DATA_DIR:-$ROOT_DIR/data/public_character}"
MANIFEST_ROOT="${MANIFEST_ROOT:-$ROOT_DIR/data/quality_manifests}"
OUTPUT_DIR="${OUTPUT_DIR:-$ROOT_DIR/models/quality_scorer}"
INPUT_SIZE="${INPUT_SIZE:-32}"
LIMIT_GOOD="${LIMIT_GOOD:-6000}"
LIMIT_MEDIUM="${LIMIT_MEDIUM:-12000}"
LIMIT_BAD="${LIMIT_BAD:-8000}"
MAX_ITER="${MAX_ITER:-24}"
SCRIPT_TARGET="${SCRIPT:-all}"
MANIFEST_PATH_OVERRIDE="${MANIFEST_PATH:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --script)
      SCRIPT_TARGET="${2:-}"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      echo "Usage: bash training/train_quality_scorer.sh [--script regular|running|all]" >&2
      exit 1
      ;;
  esac
done

train_one() {
  local script="$1"
  local manifest_path="${MANIFEST_ROOT}/${script}/quality_manifest.jsonl"
  local artifact_dir="${OUTPUT_DIR}/${script}"

  if [[ -n "$MANIFEST_PATH_OVERRIDE" ]]; then
    manifest_path="$MANIFEST_PATH_OVERRIDE"
  fi

  echo "==> Building manifest for script=${script}"
  python "$ROOT_DIR/training/build_quality_manifest.py" \
    --script "$script" \
    --public-character "$DATA_DIR" \
    --output "$manifest_path" \
    --limit-good "$LIMIT_GOOD" \
    --limit-medium "$LIMIT_MEDIUM" \
    --limit-bad "$LIMIT_BAD"

  echo "==> Training scorer for script=${script}"
  python "$ROOT_DIR/training/train_quality_scorer.py" \
    --script "$script" \
    --manifest "$manifest_path" \
    --output-dir "$OUTPUT_DIR" \
    --input-size "$INPUT_SIZE" \
    --max-iter "$MAX_ITER"

  echo "Exported ${script} quality scorer to ${artifact_dir}/quality_scorer_${script}.onnx"
  echo "Metrics written to ${artifact_dir}/quality_scorer_${script}.metrics.json"
}

case "$SCRIPT_TARGET" in
  regular|running)
    train_one "$SCRIPT_TARGET"
    ;;
  all)
    if [[ -n "$MANIFEST_PATH_OVERRIDE" ]]; then
      echo "MANIFEST_PATH is only supported when --script targets a single script." >&2
      exit 1
    fi
    train_one "regular"
    train_one "running"
    ;;
  *)
    echo "Unsupported script target: $SCRIPT_TARGET" >&2
    echo "Expected one of: regular, running, all" >&2
    exit 1
    ;;
esac
