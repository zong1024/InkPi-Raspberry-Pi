#!/bin/bash
# ============================================================
# InkPi - V100 training entrypoint
# Supports synthetic, public character-level calligraphy,
# and strictly-audited real datasets.
# ============================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

DATA_SOURCE="${DATA_SOURCE:-public_character}"   # public_character | synthetic | real
DATA_DIR="${DATA_DIR:-}"
PUBLIC_INPUT_DIR="${PUBLIC_INPUT_DIR:-}"
SAMPLES_PER_LEVEL="${SAMPLES_PER_LEVEL:-500}"
EPOCHS="${EPOCHS:-100}"
BATCH_SIZE="${BATCH_SIZE:-128}"
LEARNING_RATE="${LEARNING_RATE:-3e-4}"
NUM_WORKERS="${NUM_WORKERS:-8}"
USE_PRETRAINED="${USE_PRETRAINED:-1}"
USE_AMP="${USE_AMP:-1}"
TRAIN_RATIO="${TRAIN_RATIO:-0.8}"
IMAGE_SIZE="${IMAGE_SIZE:-224}"
EMBEDDING_DIM="${EMBEDDING_DIM:-128}"
WEIGHT_DECAY="${WEIGHT_DECAY:-1e-5}"
MARGIN="${MARGIN:-0.0}"
SEED="${SEED:-42}"
NEGATIVE_RATIO="${NEGATIVE_RATIO:-1}"
MIN_MATCH_RATIO="${MIN_MATCH_RATIO:-0.95}"
MIN_MATCHED_SAMPLES="${MIN_MATCHED_SAMPLES:-1000}"
MIN_IMAGES_PER_CHAR="${MIN_IMAGES_PER_CHAR:-4}"
MAX_IMAGES_PER_CHAR="${MAX_IMAGES_PER_CHAR:-24}"
MAX_CHARS="${MAX_CHARS:-}"

MODEL_DIR="$PROJECT_ROOT/models"
mkdir -p "$MODEL_DIR"

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE} InkPi V100 Training ${NC}"
echo -e "${BLUE}============================================================${NC}"
echo "PROJECT_ROOT        : $PROJECT_ROOT"
echo "DATA_SOURCE         : $DATA_SOURCE"
echo "DATA_DIR            : ${DATA_DIR:-<auto>}"
echo "PUBLIC_INPUT_DIR    : ${PUBLIC_INPUT_DIR:-<none>}"
echo "EPOCHS              : $EPOCHS"
echo "BATCH_SIZE          : $BATCH_SIZE"
echo "LEARNING_RATE       : $LEARNING_RATE"
echo "NUM_WORKERS         : $NUM_WORKERS"
echo "USE_PRETRAINED      : $USE_PRETRAINED"
echo "USE_AMP             : $USE_AMP"
echo "NEGATIVE_RATIO      : $NEGATIVE_RATIO"
echo "MIN_MATCH_RATIO     : $MIN_MATCH_RATIO"
echo "MIN_MATCHED_SAMPLES : $MIN_MATCHED_SAMPLES"
echo ""

echo -e "${YELLOW}[1/5] Checking environment...${NC}"
if ! command -v python3 >/dev/null 2>&1; then
  echo -e "${RED}Error: python3 not found${NC}"
  exit 1
fi
if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo -e "${RED}Error: nvidia-smi not found; this is not a CUDA server${NC}"
  exit 1
fi

echo -e "${GREEN}GPU info:${NC}"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader

echo -e "${YELLOW}[2/5] Preparing Python environment...${NC}"
if [ ! -d "$PROJECT_ROOT/venv" ]; then
  python3 -m venv "$PROJECT_ROOT/venv"
fi

# shellcheck disable=SC1091
source "$PROJECT_ROOT/venv/bin/activate"

python -m pip install --upgrade pip
python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
python -m pip install numpy opencv-python scipy pillow tqdm onnx onnxruntime onnxscript

python - <<'PY'
import torch
print("PyTorch:", torch.__version__)
print("CUDA available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("CUDA version:", torch.version.cuda)
    print("GPU:", torch.cuda.get_device_name(0))
PY

echo -e "${YELLOW}[3/5] Preparing dataset...${NC}"
if [ -z "$DATA_DIR" ]; then
  case "$DATA_SOURCE" in
    public_character)
      DATA_DIR="$PROJECT_ROOT/data/public_character"
      ;;
    real)
      DATA_DIR="$PROJECT_ROOT/data/real"
      ;;
    synthetic)
      DATA_DIR="$PROJECT_ROOT/data/synthetic"
      ;;
    *)
      echo -e "${RED}Error: unsupported DATA_SOURCE=$DATA_SOURCE${NC}"
      echo "Supported values: public_character, real, synthetic"
      exit 1
      ;;
  esac
fi

if [ "$DATA_SOURCE" = "public_character" ]; then
  if [ ! -d "$DATA_DIR/originals" ] || [ ! -d "$DATA_DIR/good" ]; then
    if [ -z "$PUBLIC_INPUT_DIR" ]; then
      echo -e "${RED}Error: public character dataset is not prepared.${NC}"
      echo "Provide an existing DATA_DIR or set PUBLIC_INPUT_DIR to the folder-per-character source."
      exit 1
    fi

    PREP_CMD=(
      python "$PROJECT_ROOT/training/prepare_character_dataset.py"
      --input "$PUBLIC_INPUT_DIR"
      --output "$DATA_DIR"
      --min-images-per-char "$MIN_IMAGES_PER_CHAR"
      --max-images-per-char "$MAX_IMAGES_PER_CHAR"
      --seed "$SEED"
      --clear-output
    )
    if [ -n "$MAX_CHARS" ]; then
      PREP_CMD+=(--max-chars "$MAX_CHARS")
    fi

    echo "Preparing public character dataset:"
    printf ' %q' "${PREP_CMD[@]}"
    echo ""
    "${PREP_CMD[@]}"
  fi
elif [ "$DATA_SOURCE" = "real" ]; then
  if [ ! -d "$DATA_DIR" ] || [ "$(find "$DATA_DIR" -name '*.png' | wc -l)" -lt 100 ]; then
    echo "Real dataset is missing or too small; trying downloader..."
    python "$PROJECT_ROOT/training/download_real_dataset.py" --source github
  fi
else
  GOOD_COUNT=0
  if [ -d "$DATA_DIR/good" ]; then
    GOOD_COUNT="$(find "$DATA_DIR/good" -name '*.png' | wc -l)"
  fi
  if [ "$GOOD_COUNT" -lt "$SAMPLES_PER_LEVEL" ]; then
    echo "Synthetic samples are insufficient; generating more..."
    python "$PROJECT_ROOT/training/dataset_builder.py" \
      --samples "$SAMPLES_PER_LEVEL" \
      --output "$DATA_DIR" \
      --quality good medium poor
  fi
fi

echo "DATA_DIR  : $DATA_DIR"
echo "originals : $(find "$DATA_DIR/originals" -name '*.png' 2>/dev/null | wc -l)"
echo "good      : $(find "$DATA_DIR/good" -name '*.png' 2>/dev/null | wc -l)"
echo "medium    : $(find "$DATA_DIR/medium" -name '*.png' 2>/dev/null | wc -l)"
echo "poor      : $(find "$DATA_DIR/poor" -name '*.png' 2>/dev/null | wc -l)"

echo "Dataset audit:"
python "$PROJECT_ROOT/training/audit_dataset.py" \
  --data "$DATA_DIR" \
  --strict \
  --min-match-ratio "$MIN_MATCH_RATIO" \
  --min-matched-samples "$MIN_MATCHED_SAMPLES"

echo -e "${YELLOW}[4/5] Starting training...${NC}"
START_TIME=$(date +%s)

CMD=(
  python "$PROJECT_ROOT/training/train_siamese.py"
  --data "$DATA_DIR"
  --output "$MODEL_DIR"
  --epochs "$EPOCHS"
  --batch-size "$BATCH_SIZE"
  --lr "$LEARNING_RATE"
  --weight-decay "$WEIGHT_DECAY"
  --margin "$MARGIN"
  --train-ratio "$TRAIN_RATIO"
  --image-size "$IMAGE_SIZE"
  --embedding-dim "$EMBEDDING_DIM"
  --workers "$NUM_WORKERS"
  --seed "$SEED"
  --device cuda
  --negative-ratio "$NEGATIVE_RATIO"
  --min-match-ratio "$MIN_MATCH_RATIO"
  --min-matched-samples "$MIN_MATCHED_SAMPLES"
)

if [ "$USE_PRETRAINED" = "1" ]; then
  CMD+=(--pretrained)
fi
if [ "$USE_AMP" = "1" ]; then
  CMD+=(--amp)
fi

echo "Running command:"
printf ' %q' "${CMD[@]}"
echo ""
"${CMD[@]}"

END_TIME=$(date +%s)
COST=$((END_TIME - START_TIME))
echo -e "${GREEN}Training finished in ${COST}s${NC}"

echo -e "${YELLOW}[5/5] Checking outputs...${NC}"
for f in \
  "$MODEL_DIR/siamese_calligraphy_best.pth" \
  "$MODEL_DIR/siamese_calligraphy_final.pth" \
  "$MODEL_DIR/siamese_calligraphy.onnx" \
  "$MODEL_DIR/training_history.json"
do
  if [ -f "$f" ]; then
    echo -e "${GREEN}OK${NC} $(basename "$f")"
  else
    echo -e "${RED}Missing${NC} $(basename "$f")"
  fi
done

echo -e "${BLUE}============================================================${NC}"
echo -e "${GREEN}Workflow complete${NC}"
echo -e "${BLUE}============================================================${NC}"

deactivate
