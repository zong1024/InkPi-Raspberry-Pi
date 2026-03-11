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
    libespeak-dev

# 创建虚拟环境
echo "[2/5] 创建虚拟环境..."
python3 -m venv venv
source venv/bin/activate

# 安装 Python 依赖
echo "[3/5] 安装 Python 依赖..."
pip install --upgrade pip
pip install -r requirements.txt

# 打包应用
echo "[4/5] 打包应用..."
pyinstaller \
    --onefile \
    --windowed \
    --name InkPi \
    --add-data "config.py:." \
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
    --collect-all PyQt6 \
    main.py

# 完成
echo "[5/5] 打包完成！"
echo ""
echo "可执行文件位置: dist/InkPi"
echo "文件大小: $(du -h dist/InkPi | cut -f1)"
echo ""
echo "运行方式: ./dist/InkPi"
echo "=========================================="