#!/bin/bash
# ============================================================
# InkPi - V100 稳定训练脚本（重写版）
# 目标：稳定、可复现、少副作用
# ============================================================

set -euo pipefail

# ---------- 颜色 ----------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ---------- 路径 ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# ---------- 参数（可通过环境变量覆盖） ----------
DATA_SOURCE="${DATA_SOURCE:-synthetic}"      # synthetic | real
SAMPLES_PER_LEVEL="${SAMPLES_PER_LEVEL:-500}"
EPOCHS="${EPOCHS:-100}"
BATCH_SIZE="${BATCH_SIZE:-128}"
LEARNING_RATE="${LEARNING_RATE:-3e-4}"
NUM_WORKERS="${NUM_WORKERS:-8}"
USE_PRETRAINED="${USE_PRETRAINED:-1}"        # 1/0
USE_AMP="${USE_AMP:-1}"                      # 1/0
TRAIN_RATIO="${TRAIN_RATIO:-0.8}"
IMAGE_SIZE="${IMAGE_SIZE:-224}"
EMBEDDING_DIM="${EMBEDDING_DIM:-128}"
WEIGHT_DECAY="${WEIGHT_DECAY:-1e-5}"
MARGIN="${MARGIN:-0.0}"
SEED="${SEED:-42}"

# ---------- 输出 ----------
MODEL_DIR="$PROJECT_ROOT/models"
mkdir -p "$MODEL_DIR"

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE} InkPi V100 稳定训练脚本 ${NC}"
echo -e "${BLUE}============================================================${NC}"
echo "PROJECT_ROOT      : $PROJECT_ROOT"
echo "DATA_SOURCE       : $DATA_SOURCE"
echo "EPOCHS            : $EPOCHS"
echo "BATCH_SIZE        : $BATCH_SIZE"
echo "LEARNING_RATE     : $LEARNING_RATE"
echo "NUM_WORKERS       : $NUM_WORKERS"
echo "USE_PRETRAINED    : $USE_PRETRAINED"
echo "USE_AMP           : $USE_AMP"
echo ""

# ============================================================
# 1) 环境检查
# ============================================================
echo -e "${YELLOW}[1/5] 环境检查...${NC}"

if ! command -v python3 >/dev/null 2>&1; then
  echo -e "${RED}错误: 未找到 python3${NC}"
  exit 1
fi

if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo -e "${RED}错误: 未找到 nvidia-smi，当前不是可用 GPU 环境${NC}"
  exit 1
fi

echo -e "${GREEN}GPU 信息:${NC}"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader

# ============================================================
# 2) 准备 Python 环境
# ============================================================
echo -e "${YELLOW}[2/5] 准备 Python 环境...${NC}"

if [ ! -d "$PROJECT_ROOT/venv" ]; then
  python3 -m venv "$PROJECT_ROOT/venv"
fi

# shellcheck disable=SC1091
source "$PROJECT_ROOT/venv/bin/activate"

python -m pip install --upgrade pip
python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
python -m pip install numpy opencv-python tqdm onnx

python - <<'PY'
import torch
print("PyTorch:", torch.__version__)
print("CUDA available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("CUDA version:", torch.version.cuda)
    print("GPU:", torch.cuda.get_device_name(0))
PY

# ============================================================
# 3) 准备数据
# ============================================================
echo -e "${YELLOW}[3/5] 准备数据...${NC}"

if [ "$DATA_SOURCE" = "real" ]; then
  DATA_DIR="$PROJECT_ROOT/data/real"
  if [ ! -d "$DATA_DIR" ] || [ "$(find "$DATA_DIR" -name '*.png' | wc -l)" -lt 100 ]; then
    echo "真实数据不足，开始下载..."
    python "$PROJECT_ROOT/training/download_real_dataset.py" --source github
  fi
else
  DATA_DIR="$PROJECT_ROOT/data/synthetic"
  GOOD_COUNT=0
  if [ -d "$DATA_DIR/good" ]; then
    GOOD_COUNT="$(find "$DATA_DIR/good" -name '*.png' | wc -l)"
  fi

  if [ "$GOOD_COUNT" -lt "$SAMPLES_PER_LEVEL" ]; then
    echo "合成数据不足，开始生成..."
    python "$PROJECT_ROOT/training/dataset_builder.py" \
      --samples "$SAMPLES_PER_LEVEL" \
      --output "$DATA_DIR" \
      --quality good medium poor
  fi
fi

echo "DATA_DIR: $DATA_DIR"
echo "originals: $(find "$DATA_DIR/originals" -name '*.png' 2>/dev/null | wc -l)"
echo "good     : $(find "$DATA_DIR/good" -name '*.png' 2>/dev/null | wc -l)"
echo "medium   : $(find "$DATA_DIR/medium" -name '*.png' 2>/dev/null | wc -l)"
echo "poor     : $(find "$DATA_DIR/poor" -name '*.png' 2>/dev/null | wc -l)"

# ============================================================
# 4) 训练
# ============================================================
echo -e "${YELLOW}[4/5] 开始训练...${NC}"

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
)

if [ "$USE_PRETRAINED" = "1" ]; then
  CMD+=(--pretrained)
fi

if [ "$USE_AMP" = "1" ]; then
  CMD+=(--amp)
fi

echo "执行命令:"
printf ' %q' "${CMD[@]}"
echo ""
"${CMD[@]}"

END_TIME=$(date +%s)
COST=$((END_TIME - START_TIME))
echo -e "${GREEN}训练完成，耗时 ${COST}s${NC}"

# ============================================================
# 5) 结果检查
# ============================================================
echo -e "${YELLOW}[5/5] 结果检查...${NC}"

for f in \
  "$MODEL_DIR/siamese_calligraphy_best.pth" \
  "$MODEL_DIR/siamese_calligraphy_final.pth" \
  "$MODEL_DIR/siamese_calligraphy.onnx" \
  "$MODEL_DIR/training_history.json"
do
  if [ -f "$f" ]; then
    echo -e "${GREEN}✓${NC} $(basename "$f")"
  else
    echo -e "${RED}✗ 缺失: $(basename "$f")${NC}"
  fi
done

echo -e "${BLUE}============================================================${NC}"
echo -e "${GREEN}全部流程结束${NC}"
echo -e "${BLUE}============================================================${NC}"

deactivate