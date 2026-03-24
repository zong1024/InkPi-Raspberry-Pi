#!/bin/bash
# ============================================================
# InkPi 书法评测系统 - CPU 版本训练脚本
# 适用于: 无 GPU 的 CPU 设备 (Linux/macOS/Windows WSL)
# ============================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置参数 (CPU 优化)
SAMPLES_PER_LEVEL=${SAMPLES_PER_LEVEL:-100}  # 每级别样本数 (CPU: 减少至 100)
EPOCHS=${EPOCHS:-30}                         # 训练轮数 (CPU: 减少至 30)
BATCH_SIZE=${BATCH_SIZE:-16}                 # 批大小 (CPU: 16)
LEARNING_RATE=${LEARNING_RATE:-1e-3}         # 学习率 (小 batch: 1e-3)
DATA_SOURCE=${DATA_SOURCE:-synthetic}        # 数据源: real (真实) 或 synthetic (合成)
NUM_WORKERS=${NUM_WORKERS:-1}                # 数据加载线程 (CPU: 1)

# 获取脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# 全局变量
TOTAL_COUNT=0
START_TIME=0
TRAINING_TIME=0

echo -e "${BLUE}"
echo "============================================================"
echo "  InkPi 书法评测系统 - CPU 版本训练"
echo "============================================================"
echo -e "${NC}"
echo "项目根目录: $PROJECT_ROOT"
echo "配置参数:"
echo "  - 每级别样本数: $SAMPLES_PER_LEVEL"
echo "  - 训练轮数: $EPOCHS"
echo "  - 批大小: $BATCH_SIZE"
echo "  - 学习率: $LEARNING_RATE"
echo "  - 数据源: $DATA_SOURCE"
echo "  - 数据加载线程: $NUM_WORKERS"
echo ""
echo "⚠️  CPU 训练速度较慢，建议:"
echo "  - 使用合成数据集 (DATA_SOURCE=synthetic)"
echo "  - 样本数量较少 (SAMPLES_PER_LEVEL=100)"
echo "  - 训练轮数较少 (EPOCHS=30)"
echo ""

# ============================================================
# 步骤 1: 环境检查
# ============================================================
echo -e "${YELLOW}[1/7] 环境检查...${NC}"

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未安装 Python 3${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION"

# 检查 pip
if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}错误: 未安装 pip3${NC}"
    exit 1
fi

echo ""

# ============================================================
# 步骤 2: 安装依赖
# ============================================================
echo -e "${YELLOW}[2/7] 安装 Python 依赖...${NC}"

cd "$PROJECT_ROOT"

# 创建虚拟环境（如果不存在）
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    if ! python3 -m venv venv 2>/dev/null; then
        echo "python3-venv 未安装，正在安装..."
        sudo apt-get update 2>/dev/null || true
        sudo apt-get install -y python3-venv python3-dev python3-pip 2>/dev/null || true
        python3 -m venv venv
    fi
fi

# 激活虚拟环境
source venv/bin/activate

# 升级 pip
pip install --upgrade pip

# 安装 PyTorch (CPU 版本，体积更小)
echo "安装 PyTorch (CPU 版本)..."
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# 安装其他依赖
echo "安装其他依赖..."
pip install numpy opencv-python scipy pillow tqdm onnx onnxruntime onnxscript

# 验证 PyTorch
python3 -c "
import torch
print(f'PyTorch 版本: {torch.__version__}')
print(f'CUDA 可用: {torch.cuda.is_available()}')
print(f'CPU 核心数: {torch.get_num_threads()}')
"

echo ""

# ============================================================
# 步骤 3: 准备数据集
# ============================================================
cd "$PROJECT_ROOT"

if [ "$DATA_SOURCE" = "real" ]; then
    echo -e "${YELLOW}[3/7] 下载真实书法数据集...${NC}"
    
    # 检查是否已有真实数据
    REAL_COUNT=$(find "$PROJECT_ROOT/data/real" -name "*.png" 2>/dev/null | wc -l)
    
    if [ "$REAL_COUNT" -ge 100 ]; then
        echo -e "${GREEN}已存在 $REAL_COUNT 张真实数据，跳过下载${NC}"
    else
        echo "从 GitHub 下载真实书法数据集..."
        python3 training/download_real_dataset.py --source github
    fi
    
    # 统计真实数据
    TOTAL_COUNT=$(find "$PROJECT_ROOT/data/real" -name "*.png" 2>/dev/null | wc -l)
    DATA_DIR="$PROJECT_ROOT/data/real"
    
    echo -e "${GREEN}真实数据集统计:${NC}"
    echo "  - 总计: $TOTAL_COUNT 张"
else
    echo -e "${YELLOW}[3/7] 生成合成数据集...${NC}"
    
    # 检查是否已有足够数据
    EXISTING_SAMPLES=$(find "$PROJECT_ROOT/data/synthetic/good" -name "*.png" 2>/dev/null | wc -l)

    if [ "$EXISTING_SAMPLES" -ge "$SAMPLES_PER_LEVEL" ]; then
        echo -e "${GREEN}已存在 $EXISTING_SAMPLES 个样本，跳过数据集生成${NC}"
    else
        echo "生成 $SAMPLES_PER_LEVEL 个样本 per 级别..."
        python3 training/dataset_builder.py \
            --samples $SAMPLES_PER_LEVEL \
            --output "$PROJECT_ROOT/data/synthetic" \
            --quality good medium poor
    fi

    # 统计总样本数
    TOTAL_GOOD=$(find "$PROJECT_ROOT/data/synthetic/good" -name "*.png" 2>/dev/null | wc -l)
    TOTAL_MEDIUM=$(find "$PROJECT_ROOT/data/synthetic/medium" -name "*.png" 2>/dev/null | wc -l)
    TOTAL_POOR=$(find "$PROJECT_ROOT/data/synthetic/poor" -name "*.png" 2>/dev/null | wc -l)
    TOTAL_COUNT=$((TOTAL_GOOD + TOTAL_MEDIUM + TOTAL_POOR))
    DATA_DIR="$PROJECT_ROOT/data/synthetic"

    echo -e "${GREEN}合成数据集统计:${NC}"
    echo "  - good: $TOTAL_GOOD 张"
    echo "  - medium: $TOTAL_MEDIUM 张"
    echo "  - poor: $TOTAL_POOR 张"
    echo "  - 总计: $TOTAL_COUNT 张"
fi

if [ "$TOTAL_COUNT" -lt 10 ]; then
    echo -e "${RED}错误: 样本数量过少 (至少需要 10 张)${NC}"
    exit 1
fi

echo ""

# ============================================================
# 步骤 4: 开始训练
# ============================================================
echo -e "${YELLOW}[4/7] 开始训练模型...${NC}"

cd "$PROJECT_ROOT"

# 记录开始时间
START_TIME=$(date +%s)

# 运行训练 (CPU 优化: 禁用 AMP + 小 batch + 1 个线程)
echo -e "${YELLOW}⏱️  预计训练时间: 2-4 小时 (取决于 CPU 性能)${NC}"
echo ""

python3 training/train_siamese.py \
    --data "$DATA_DIR" \
    --epochs $EPOCHS \
    --batch-size $BATCH_SIZE \
    --lr $LEARNING_RATE \
    --device cpu \
    --workers $NUM_WORKERS

# 记录结束时间
END_TIME=$(date +%s)
TRAINING_TIME=$((END_TIME - START_TIME))
HOURS=$((TRAINING_TIME / 3600))
MINUTES=$(((TRAINING_TIME % 3600) / 60))
SECONDS=$((TRAINING_TIME % 60))

echo -e "${GREEN}训练完成! 耗时: ${HOURS}h ${MINUTES}m ${SECONDS}s${NC}"

echo ""

# ============================================================
# 步骤 5: 验证模型
# ============================================================
echo -e "${YELLOW}[5/7] 验证训练结果...${NC}"

cd "$PROJECT_ROOT"

# 检查模型文件
if [ ! -f "$PROJECT_ROOT/models/siamese_calligraphy_best.pth" ]; then
    echo -e "${RED}错误: 训练后的模型文件不存在${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} PyTorch 模型生成成功"

echo ""

# ============================================================
# 步骤 6: 导出 ONNX
# ============================================================
echo -e "${YELLOW}[6/7] 导出 ONNX 模型...${NC}"

cd "$PROJECT_ROOT"

# 检查模型文件
if [ ! -f "$PROJECT_ROOT/models/siamese_calligraphy_best.pth" ]; then
    echo -e "${RED}错误: 训练后的模型文件不存在${NC}"
    exit 1
fi

# 验证 ONNX 模型
if [ -f "$PROJECT_ROOT/models/siamese_calligraphy.onnx" ]; then
    echo -e "${GREEN}✓ ONNX 模型已导出: models/siamese_calligraphy.onnx${NC}"
    
    # 显示模型信息
    python3 -c "
import onnx
model = onnx.load('$PROJECT_ROOT/models/siamese_calligraphy.onnx')
print('ONNX 模型信息:')
print(f'  - IR 版本: {model.ir_version}')
print(f'  - 生产者: {model.producer_name}')
print(f'  - 输入:')
for inp in model.graph.input:
    print(f'      {inp.name}: {[d.dim_value for d in inp.type.tensor_type.shape.dim]}')
print(f'  - 输出:')
for out in model.graph.output:
    print(f'      {out.name}: {[d.dim_value for d in out.type.tensor_type.shape.dim]}')
"
else
    echo -e "${RED}警告: ONNX 模型未找到，请检查训练日志${NC}"
fi

echo ""

# ============================================================
# 步骤 7: 结果汇总
# ============================================================
echo -e "${YELLOW}[7/7] 结果汇总${NC}"

cd "$PROJECT_ROOT"

echo -e "${GREEN}"
echo "============================================================"
echo "  训练完成!"
echo "============================================================"
echo -e "${NC}"

echo "输出文件:"
echo ""

# 模型文件
if [ -f "$PROJECT_ROOT/models/siamese_calligraphy_best.pth" ]; then
    BEST_SIZE=$(du -h "$PROJECT_ROOT/models/siamese_calligraphy_best.pth" | cut -f1)
    echo -e "  ${GREEN}✓${NC} models/siamese_calligraphy_best.pth ($BEST_SIZE)"
fi

if [ -f "$PROJECT_ROOT/models/siamese_calligraphy_final.pth" ]; then
    FINAL_SIZE=$(du -h "$PROJECT_ROOT/models/siamese_calligraphy_final.pth" | cut -f1)
    echo -e "  ${GREEN}✓${NC} models/siamese_calligraphy_final.pth ($FINAL_SIZE)"
fi

if [ -f "$PROJECT_ROOT/models/siamese_calligraphy.onnx" ]; then
    ONNX_SIZE=$(du -h "$PROJECT_ROOT/models/siamese_calligraphy.onnx" | cut -f1)
    echo -e "  ${GREEN}✓${NC} models/siamese_calligraphy.onnx ($ONNX_SIZE)"
fi

if [ -f "$PROJECT_ROOT/models/training_history.json" ]; then
    echo -e "  ${GREEN}✓${NC} models/training_history.json"
fi

echo ""
echo "训练统计:"
echo "  - 数据集大小: $TOTAL_COUNT 张"
echo "  - 训练轮数: $EPOCHS"
echo "  - 批大小: $BATCH_SIZE"
echo "  - 训练时长: ${HOURS}h ${MINUTES}m ${SECONDS}s"
echo ""

# 部署说明
echo -e "${BLUE}部署说明:${NC}"
echo ""
echo "1. 复制 ONNX 模型到树莓派项目目录:"
echo "   scp models/siamese_calligraphy.onnx pi@raspberrypi:~/InkPi-Raspberry-Pi/models/"
echo ""
echo "2. 或在树莓派项目根目录运行:"
echo "   MODEL_SOURCE=/path/to/siamese_calligraphy.onnx ./deploy_rpi.sh"
echo ""
echo "3. 验证模型:"
echo "   python3 -c \"import onnxruntime as ort; sess = ort.InferenceSession('models/siamese_calligraphy.onnx'); print('✓ 模型加载成功')\""
echo ""
echo "============================================================"
echo ""
echo -e "${GREEN}提示: CPU 版本训练速度较慢，后续可升级到 GPU 训练以加速${NC}"
echo ""

# 退出虚拟环境
deactivate
