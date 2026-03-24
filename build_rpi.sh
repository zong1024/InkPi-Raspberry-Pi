#!/bin/bash
# InkPi 书法评测系统 - Raspberry Pi 打包脚本
# 在 Raspberry Pi 上运行此脚本生成单一可执行文件

set -e

echo "=========================================="
echo "  InkPi 书法评测系统 - Raspberry Pi 打包"
echo "=========================================="

# 检查是否在 Raspberry Pi 上运行
if [ ! -f /proc/device-tree/model ]; then
    echo "警告: 此脚本应在 Raspberry Pi 上运行"
fi

# 安装系统依赖
echo "[1/5] 安装系统依赖..."
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
    libespeak-dev \
    spi-tools

for pkg in python3-picamera2 python3-libcamera libcamera-apps; do
    sudo apt-get install -y "$pkg" 2>/dev/null || echo "警告: 可选包 $pkg 安装失败，继续部署"
done

# 启用 SPI 接口 (用于 WS2812B LED 灯带)
echo "启用 SPI 接口..."
sudo raspi-config nonint do_spi 0

# 添加用户到 spi 组
sudo usermod -a -G spi $USER

# 创建虚拟环境
echo "[2/5] 创建虚拟环境..."
python3 -m venv venv
source venv/bin/activate

# 安装 Python 依赖
echo "[3/5] 安装 Python 依赖..."
pip install --upgrade pip
pip install pyinstaller
pip install -r requirements.txt
pip install spidev

# 创建模型目录结构
echo "[4/5] 准备模型文件..."
mkdir -p models
if [ -n "${MODEL_SOURCE:-}" ] && [ -f "${MODEL_SOURCE}" ]; then
    cp "${MODEL_SOURCE}" "models/siamese_calligraphy.onnx"
fi

if [ ! -f "models/siamese_calligraphy.onnx" ]; then
    echo "警告: 孪生网络模型不存在，请先复制 siamese_calligraphy.onnx 到 models/ 目录"
else
    echo "检测到孪生网络模型: models/siamese_calligraphy.onnx"
fi

# 打包应用
echo "[5/5] 打包应用..."
pyinstaller \
    --onefile \
    --windowed \
    --name InkPi \
    --add-data "config:config" \
    --add-data "models:models" \
    --add-data "models/templates:models/templates" \
    --add-data "services:services" \
    --add-data "views:views" \
    --add-data "core:core" \
    --add-data "data:data" \
    --hidden-import PyQt6 \
    --hidden-import PyQt6.QtCore \
    --hidden-import PyQt6.QtWidgets \
    --hidden-import PyQt6.QtGui \
    --hidden-import cv2 \
    --hidden-import numpy \
    --hidden-import matplotlib \
    --hidden-import matplotlib.backends.backend_qtagg \
    --hidden-import pyttsx3 \
    --hidden-import sqlite3 \
    --hidden-import requests \
    --hidden-import onnxruntime \
    --hidden-import PIL \
    --hidden-import scipy \
    --collect-all PyQt6 \
    --exclude-module tkinter \
    main.py

# 完成
echo ""
echo "=========================================="
echo "  打包完成！"
echo "=========================================="
echo ""
echo "可执行文件位置: dist/InkPi"
echo "文件大小: $(du -h dist/InkPi | cut -f1)"
echo ""
echo "运行方式: ./dist/InkPi"
echo "=========================================="
