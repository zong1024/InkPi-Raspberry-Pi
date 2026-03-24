#!/bin/bash
# InkPi 书法评测系统 - 树莓派完整部署脚本
# 使用方法: ./deploy_rpi.sh

set -e

echo "=========================================="
echo "  InkPi 书法评测系统 - 完整部署"
echo "=========================================="

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 步骤1: 清理旧的打包文件
echo ""
echo "[1/6] 清理旧文件..."
rm -rf build dist *.spec __pycache__ */__pycache__ */*/__pycache__
rm -rf venv
echo "清理完成"

# 步骤2: 拉取最新代码
echo ""
echo "[2/6] 拉取最新代码..."
git fetch origin
git reset --hard origin/master
git pull origin master
echo "代码已更新"

# 步骤3: 安装系统依赖
echo ""
echo "[3/6] 安装系统依赖..."
sudo apt-get update
sudo apt-get install -y \
    python3-dev \
    python3-pip \
    python3-venv \
    libopencv-dev \
    python3-opencv \
    espeak-ng \
    portaudio19-dev \
    libespeak1 \
    spi-tools

for pkg in python3-picamera2 python3-libcamera libcamera-apps; do
    sudo apt-get install -y "$pkg" 2>/dev/null || echo "警告: 可选包 $pkg 安装失败，继续部署"
done

# 启用 SPI (用于 LED 灯带)
sudo raspi-config nonint do_spi 0 2>/dev/null || true
sudo usermod -a -G spi $USER 2>/dev/null || true
echo "系统依赖安装完成"

# 步骤4: 创建虚拟环境
echo ""
echo "[4/6] 创建虚拟环境..."
python3 -m venv venv
source venv/bin/activate
echo "虚拟环境创建完成"

# 步骤5: 安装 Python 依赖
echo ""
echo "[5/6] 安装 Python 依赖..."
pip install --upgrade pip
pip install -r requirements.txt
pip install spidev
echo "Python 依赖安装完成"

if [ -n "${MODEL_SOURCE:-}" ] && [ -f "${MODEL_SOURCE}" ]; then
    mkdir -p models
    cp "${MODEL_SOURCE}" "models/siamese_calligraphy.onnx"
fi

if [ -f "models/siamese_calligraphy.onnx" ]; then
    echo "检测到孪生网络模型: models/siamese_calligraphy.onnx"
else
    echo "警告: 未检测到 models/siamese_calligraphy.onnx，程序将回退到传统评分逻辑"
fi

# 步骤6: 运行程序
echo ""
echo "[6/6] 启动程序..."
echo ""
echo "=========================================="
echo "  部署完成！"
echo "=========================================="
echo ""
echo "运行方式:"
echo "  source venv/bin/activate"
echo "  python main.py"
echo ""
echo "=========================================="

# 直接运行
python main.py
