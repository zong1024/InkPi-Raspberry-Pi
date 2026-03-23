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
pip install -r requirements.txt

# 创建模型目录结构
echo "[4/6] 准备模型文件..."
mkdir -p models
# 如果模型文件不存在，创建占位符（用户需要自行下载或训练）
if [ ! -f "models/ch_recognize_mobile_int8.onnx" ]; then
    echo "警告: 汉字识别模型不存在，请运行 python training/train_siamese.py 训练或下载预训练模型"
fi

# 打包应用
echo "[5/6] 打包应用..."
pyinstaller \
    --onefile \
    --windowed \
    --name InkPi \
    --add-data "config.py:." \
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
    --hidden-import torch \
    --hidden-import torchvision \
    --hidden-import PIL \
    --hidden-import scipy \
    --collect-all PyQt6 \
    --exclude-module tkinter \
    main.py

# 完成
echo "[5/5] 打包完成！"
echo ""
echo "可执行文件位置: dist/InkPi"
echo "文件大小: $(du -h dist/InkPi | cut -f1)"
echo ""
echo "运行方式: ./dist/InkPi"
echo "=========================================="