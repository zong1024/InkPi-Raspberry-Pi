#!/bin/bash
# ============================================================
# InkPi 书法评测系统 - V100 服务器一键训练脚本
# 适用于: Dell R730 + Ubuntu + NVIDIA V100
# ============================================================

set -e

# ============================================================
# 权限检查：驱动安装需要 sudo 权限
# ============================================================

# 检查用户权限
if ! sudo -n true 2>/dev/null; then
    echo "本脚本需要 sudo 权限来安装 NVIDIA 驱动和 CUDA。"
    echo "请配置 sudoers 以支持无密码 sudo，或者手动构建 sudo 权限。"
    echo ""
    echo "可选: 手动运行以下命令来授予 sudo 权限:"
    echo "  sudo visudo"
    echo "然后在文件末尾添加:"
    echo "  $USER ALL=(ALL) NOPASSWD: ALL"
fi

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置参数 (V100 优化)
SAMPLES_PER_LEVEL=${SAMPLES_PER_LEVEL:-500}  # 每级别样本数
EPOCHS=${EPOCHS:-100}                        # 训练轮数
BATCH_SIZE=${BATCH_SIZE:-128}                # 批大小 (V100: 128)
LEARNING_RATE=${LEARNING_RATE:-3e-4}         # 学习率 (大 batch: 3e-4)
DATA_SOURCE=${DATA_SOURCE:-real}             # 数据源: real (真实) 或 synthetic (合成)
NUM_WORKERS=${NUM_WORKERS:-8}                # 数据加载线程

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
echo -e "${YELLOW}[1/6] 环境检查和驱动安装...${NC}"

# ============================================================
# 子步骤 1.0: 自动安装 NVIDIA 驱动（如果未安装）
# ============================================================

# 检查 NVIDIA 驱动
if ! command -v nvidia-smi &> /dev/null; then
    echo -e "${YELLOW}未检测到 NVIDIA 驱动，正在自动安装...${NC}"
    
    # 检查 Linux 发行版
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
    fi
    
    # 根据系统类型安装驱动
    case "$OS" in
        ubuntu|debian)
            echo "检测到基于 Debian 的系统，使用 apt 安装..."
            sudo apt-get update
            echo "安装 NVIDIA 驱动 (版本 >= 535，支持 V100 + CUDA 11.8)..."
            sudo apt-get install -y nvidia-driver-535
            
            # 重新加载驱动
            echo "重新加载 NVIDIA 驱动模块..."
            sudo modprobe nvidia
            sudo modprobe nvidia-uvm
            ;;
            
        rhel|centos|fedora)
            echo "检测到基于 RedHat 的系统，使用 yum 安装..."
            sudo yum update -y
            echo "安装 NVIDIA 驱动 (版本 >= 535)..."
            sudo yum install -y gcc kernel-devel
            sudo yum groupinstall -y "Development Tools"
            sudo yum install -y nvidia-driver-latest-dkms nvidia-utils
            ;;
            
        *)
            echo -e "${RED}未支持的 Linux 发行版: $OS${NC}"
            echo "请手动从以下网址下载并安装 NVIDIA 驱动:"
            echo "https://www.nvidia.com/Download/driverDetails.aspx/178898"
            exit 1
            ;;
    esac
    
    # 验证驱动安装
    if ! command -v nvidia-smi &> /dev/null; then
        echo -e "${RED}NVIDIA 驱动安装失败，请手动访问:"
        echo "https://www.nvidia.com/Download/driverDetails.aspx/178898"
        echo "选择 V100 并下载对应驱动"
        exit 1
    fi
    
    echo -e "${GREEN}NVIDIA 驱动安装成功!${NC}"
    echo ""
fi

# 验证驱动版本（V100 建议驱动版本 >= 450）
DRIVER_VERSION=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)
MAJOR_VERSION=$(echo $DRIVER_VERSION | cut -d. -f1)

echo "检查驱动版本..."
if [ "$MAJOR_VERSION" -lt 450 ]; then
    echo -e "${YELLOW}警告: 驱动版本较老 (${DRIVER_VERSION})，建议升级到 >= 535 版本${NC}"
    echo "可以运行以下命令升级:"
    echo "  sudo apt-get install -y --only-upgrade nvidia-driver-535"
    echo ""
fi

# 检查 GPU
echo -e "${GREEN}GPU 信息:${NC}"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader

# ============================================================
# 子步骤 1.1: 自动安装 CUDA Toolkit（如果未安装）
# ============================================================

# 检查 CUDA
if ! command -v nvcc &> /dev/null; then
    echo -e "${YELLOW}nvcc 未找到，正在自动安装 CUDA 11.8...${NC}"
    
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
    fi
    
    case "$OS" in
        ubuntu|debian)
            # 对于 Ubuntu 22.04 / 20.04
            UBUNTU_VERSION=$(lsb_release -rs)
            
            # 添加 NVIDIA CUDA 仓库
            ARCH=$(dpkg --print-architecture)
            distro=$(lsb_release -is | tr '[:upper:]' '[:lower:]')
            
            echo "添加 NVIDIA CUDA 仓库..."
            sudo apt-key adv --fetch-keys https://developer.download.nvidia.com/compute/cuda/repos/$distro$UBUNTU_VERSION/$ARCH/3bf863cc.pub || true
            sudo add-apt-repository "deb https://developer.download.nvidia.com/compute/cuda/repos/$distro$UBUNTU_VERSION/$ARCH /" || true
            
            echo "安装 CUDA 11.8..."
            sudo apt-get update
            sudo apt-get install -y cuda-11-8
            
            # 设置环境变量
            export PATH=/usr/local/cuda-11.8/bin:$PATH
            export LD_LIBRARY_PATH=/usr/local/cuda-11.8/lib64:$LD_LIBRARY_PATH
            
            # 写入 .bashrc（持久化）
            if ! grep -q "CUDA_11.8" ~/.bashrc; then
                echo '# CUDA 11.8' >> ~/.bashrc
                echo 'export PATH=/usr/local/cuda-11.8/bin:$PATH' >> ~/.bashrc
                echo 'export LD_LIBRARY_PATH=/usr/local/cuda-11.8/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
            fi
            ;;
            
        rhel|centos|fedora)
            echo "安装 CUDA 11.8..."
            sudo yum install -y cuda-11-8
            
            # 设置环境变量
            export PATH=/usr/local/cuda-11.8/bin:$PATH
            export LD_LIBRARY_PATH=/usr/local/cuda-11.8/lib64:$LD_LIBRARY_PATH
            ;;
            
        *)
            echo -e "${YELLOW}警告: 无法自动安装 CUDA，请手动从以下网址下载:${NC}"
            echo "https://developer.nvidia.com/cuda-11-8-0-download-archive"
            ;;
    esac
fi

# 验证 CUDA 安装
if command -v nvcc &> /dev/null; then
    CUDA_VERSION=$(nvcc --version | grep "release" | awk '{print $6}' | cut -c2-)
    echo -e "${GREEN}CUDA 版本: $CUDA_VERSION${NC}"
    
    # 检查版本是否兼容（建议 11.8）
    CUDA_MAJOR=$(echo $CUDA_VERSION | cut -d. -f1)
    CUDA_MINOR=$(echo $CUDA_VERSION | cut -d. -f2)
    
    if [ "$CUDA_MAJOR" -lt 11 ] || ([ "$CUDA_MAJOR" -eq 11 ] && [ "$CUDA_MINOR" -lt 8 ]); then
        echo -e "${YELLOW}警告: CUDA 版本较低 ($CUDA_VERSION)，建议升级到 11.8 或更高版本${NC}"
    fi
else
    echo -e "${YELLOW}警告: 无法自动安装 CUDA，PyTorch 将尝试使用自带的 CUDA${NC}"
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

# 创建虚拟环境（如果不存在）
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    if ! python3 -m venv venv 2>/dev/null; then
        echo "python3-venv 未安装，正在安装..."
        sudo apt-get update
        sudo apt-get install -y python3-venv python3-dev python3-pip
        python3 -m venv venv
    fi
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
# 步骤 3: 准备数据集
# ============================================================
cd "$PROJECT_ROOT"

if [ "$DATA_SOURCE" = "real" ]; then
    echo -e "${YELLOW}[3/6] 下载真实书法数据集...${NC}"
    
    # 检查是否已有真实数据
    REAL_COUNT=$(find data/real -name "*.png" 2>/dev/null | wc -l)
    
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
    echo -e "${YELLOW}[3/6] 生成合成数据集...${NC}"
    
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

echo ""

# ============================================================
# 步骤 4: 训练模型
# ============================================================
echo -e "${YELLOW}[4/6] 开始训练模型...${NC}"

cd "$PROJECT_ROOT"

# 记录开始时间
START_TIME=$(date +%s)

# 运行训练 (V100 优化: AMP + 大 batch + 多线程)
python3 training/train_siamese.py \
    --data $DATA_DIR \
    --epochs $EPOCHS \
    --batch-size $BATCH_SIZE \
    --lr $LEARNING_RATE \
    --device cuda \
    --pretrained \
    --amp \
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
# 步骤 5: 导出 ONNX
# ============================================================
echo -e "${YELLOW}[5/6] 导出 ONNX 模型...${NC}"

cd "$PROJECT_ROOT"

# 检查模型文件
if [ ! -f "$PROJECT_ROOT/models/siamese_calligraphy_best.pth" ]; then
    echo -e "${RED}错误: 训练后的模型文件不存在${NC}"
    exit 1
fi

# 验证 ONNX 模型
if [ -f "$PROJECT_ROOT/models/siamese_calligraphy.onnx" ]; then
    echo -e "${GREEN}ONNX 模型已导出: models/siamese_calligraphy.onnx${NC}"
    
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
echo -e "${BLUE}部署到树莓派:${NC}"
echo "  scp models/siamese_calligraphy.onnx pi@raspberrypi:~/.inkpi/data/models/"
echo ""
echo "或复制到项目目录:"
echo "  cp models/siamese_calligraphy.onnx ~/.inkpi/data/models/ch_recognize_mobile_int8.onnx"
echo ""
echo "============================================================"

# 退出虚拟环境
deactivate