#!/bin/bash
# ============================================================
# InkPi 书法评测系统 - V100 服务器一键训练脚本
# 适用于: Dell R730 + Ubuntu + NVIDIA V100
# ============================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置参数
SAMPLES_PER_LEVEL=${SAMPLES_PER_LEVEL:-500}  # 每级别样本数
EPOCHS=${EPOCHS:-100}                        # 训练轮数
BATCH_SIZE=${BATCH_SIZE:-64}                 # 批大小
LEARNING_RATE=${LEARNING_RATE:-1e-4}         # 学习率
WORKERS=${WORKERS:-8}                        # 数据加载线程

# 获取脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# 全局变量
TOTAL_COUNT=0
START_TIME=0
TRAINING_TIME=0

echo -e "${BLUE}"
echo "============================================================"
echo "  InkPi 书法评测系统 - V100 一键训练"
echo "============================================================"
echo -e "${NC}"
echo "项目根目录: $PROJECT_ROOT"
echo "配置参数:"
echo "  - 每级别样本数: $SAMPLES_PER_LEVEL"
echo "  - 训练轮数: $EPOCHS"
echo "  - 批大小: $BATCH_SIZE"
echo "  - 学习率: $LEARNING_RATE"
echo "  - 数据加载线程: $WORKERS"
echo ""

# ============================================================
# 步骤 1: 环境检查
# ============================================================
echo -e "${YELLOW}[1/6] 环境检查...${NC}"

# 检查 NVIDIA 驱动
if ! command -v nvidia-smi &> /dev/null; then
    echo -e "${RED}错误: 未检测到 NVIDIA 驱动${NC}"
    exit 1
fi

# 检查 GPU
echo -e "${GREEN}GPU 信息:${NC}"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader

# 检查 CUDA
if ! command -v nvcc &> /dev/null; then
    echo -e "${YELLOW}警告: nvcc 未找到，尝试使用系统 CUDA${NC}"
else
    CUDA_VERSION=$(nvcc --version | grep "release" | awk '{print $6}' | cut -c2-)
    echo -e "${GREEN}CUDA 版本: $CUDA_VERSION${NC}"
fi

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未安装 Python3${NC}"
    exit 1
fi
PYTHON_VERSION=$(python3 --version)
echo -e "${GREEN}Python 版本: $PYTHON_VERSION${NC}"

# 检查 pip
if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}错误: 未安装 pip3${NC}"
    exit 1
fi

echo ""

# ============================================================
# 步骤 2: 安装依赖
# ============================================================
echo -e "${YELLOW}[2/6] 安装 Python 依赖...${NC}"

cd "$PROJECT_ROOT"

# 安装 python3-venv（Ubuntu 24.04 需要）
if ! python3 -m venv --help &> /dev/null; then
    echo "安装 python3-venv..."
    sudo apt-get update
    sudo apt-get install -y python3-venv python3-dev python3-pip
fi

# 创建虚拟环境（如果不存在）
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 升级 pip
pip install --upgrade pip

# 安装 PyTorch (CUDA 11.8 版本)
echo "安装 PyTorch (CUDA 11.8)..."
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# 安装其他依赖
echo "安装其他依赖..."
pip install numpy opencv-python scipy pillow tqdm onnx onnxruntime

# 验证 PyTorch CUDA
python3 -c "
import torch
print(f'PyTorch 版本: {torch.__version__}')
print(f'CUDA 可用: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'CUDA 版本: {torch.version.cuda}')
    print(f'GPU 数量: {torch.cuda.device_count()}')
    print(f'当前 GPU: {torch.cuda.get_device_name(0)}')
"

echo ""

# ============================================================
# 步骤 3: 生成数据集
# ============================================================
echo -e "${YELLOW}[3/6] 生成合成数据集...${NC}"

cd "$PROJECT_ROOT"

# 检查是否已有足够数据
EXISTING_SAMPLES=$(find data/synthetic/good -name "*.png" 2>/dev/null | wc -l)

if [ "$EXISTING_SAMPLES" -ge "$SAMPLES_PER_LEVEL" ]; then
    echo -e "${GREEN}已存在 $EXISTING_SAMPLES 个样本，跳过数据集生成${NC}"
else
    echo "生成 $SAMPLES_PER_LEVEL 个样本 per 级别..."
    python3 training/dataset_builder.py \
        --samples $SAMPLES_PER_LEVEL \
        --output data/synthetic \
        --quality good medium poor
fi

# 统计总样本数
TOTAL_GOOD=$(find data/synthetic/good -name "*.png" 2>/dev/null | wc -l)
TOTAL_MEDIUM=$(find data/synthetic/medium -name "*.png" 2>/dev/null | wc -l)
TOTAL_POOR=$(find data/synthetic/poor -name "*.png" 2>/dev/null | wc -l)
TOTAL_COUNT=$((TOTAL_GOOD + TOTAL_MEDIUM + TOTAL_POOR))

echo -e "${GREEN}数据集统计:${NC}"
echo "  - good: $TOTAL_GOOD 张"
echo "  - medium: $TOTAL_MEDIUM 张"
echo "  - poor: $TOTAL_POOR 张"
echo "  - 总计: $TOTAL_COUNT 张"

echo ""

# ============================================================
# 步骤 4: 训练模型
# ============================================================
echo -e "${YELLOW}[4/6] 开始训练模型...${NC}"

cd "$PROJECT_ROOT"

# 记录开始时间
START_TIME=$(date +%s)

# 运行训练
python3 training/train_siamese.py \
    --epochs $EPOCHS \
    --batch-size $BATCH_SIZE \
    --lr $LEARNING_RATE \
    --workers $WORKERS \
    --device cuda \
    --pretrained

# 记录结束时间
END_TIME=$(date +%s)
TRAINING_TIME=$((END_TIME - START_TIME))
HOURS=$((TRAINING_TIME / 3600))
MINUTES=$(((TRAINING_TIME % 3600) / 60))
SECONDS=$((TRAINING_TIME % 60))

echo -e "${GREEN}训练完成! 耗时: ${HOURS}h ${MINUTES}m ${SECONDS}s${NC}"

echo ""

# ============================================================
# 步骤 5: 导出 ONNX
# ============================================================
echo -e "${YELLOW}[5/6] 导出 ONNX 模型...${NC}"

cd "$PROJECT_ROOT"

# 检查模型文件
if [ ! -f "models/siamese_calligraphy_best.pth" ]; then
    echo -e "${RED}错误: 训练后的模型文件不存在${NC}"
    exit 1
fi

# 验证 ONNX 模型
if [ -f "models/siamese_calligraphy.onnx" ]; then
    echo -e "${GREEN}ONNX 模型已导出: models/siamese_calligraphy.onnx${NC}"
    
    # 显示模型信息
    python3 -c "
import onnx
model = onnx.load('models/siamese_calligraphy.onnx')
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
# 步骤 6: 结果汇总
# ============================================================
echo -e "${YELLOW}[6/6] 结果汇总${NC}"

cd "$PROJECT_ROOT"

echo -e "${GREEN}"
echo "============================================================"
echo "  训练完成!"
echo "============================================================"
echo -e "${NC}"

echo "输出文件:"
echo ""

# 模型文件
if [ -f "models/siamese_calligraphy_best.pth" ]; then
    BEST_SIZE=$(du -h models/siamese_calligraphy_best.pth | cut -f1)
    echo -e "  ${GREEN}✓${NC} models/siamese_calligraphy_best.pth ($BEST_SIZE)"
fi

if [ -f "models/siamese_calligraphy_final.pth" ]; then
    FINAL_SIZE=$(du -h models/siamese_calligraphy_final.pth | cut -f1)
    echo -e "  ${GREEN}✓${NC} models/siamese_calligraphy_final.pth ($FINAL_SIZE)"
fi

if [ -f "models/siamese_calligraphy.onnx" ]; then
    ONNX_SIZE=$(du -h models/siamese_calligraphy.onnx | cut -f1)
    echo -e "  ${GREEN}✓${NC} models/siamese_calligraphy.onnx ($ONNX_SIZE)"
fi

if [ -f "models/training_history.json" ]; then
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
echo -e "${BLUE}部署到树莓派:${NC}"
echo "  scp models/siamese_calligraphy.onnx pi@raspberrypi:~/.inkpi/data/models/"
echo ""
echo "或复制到项目目录:"
echo "  cp models/siamese_calligraphy.onnx ~/.inkpi/data/models/ch_recognize_mobile_int8.onnx"
echo ""
echo "============================================================"

# 退出虚拟环境
deactivate