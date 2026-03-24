# InkPi 书法评测系统 | Calligraphy Evaluation System

[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-EE4C2C?logo=pytorch&logoColor=white)](https://pytorch.org/)
[![ONNX](https://img.shields.io/badge/ONNX-1.14+-005CED?logo=onnx&logoColor=white)](https://onnx.ai/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[English](#english) | [中文](#中文)

---

## 中文

基于树莓派的智能书法评测系统，采用孪生网络架构，支持毛笔字四维度评分。

### 概述

InkPi 通过深度学习与传统图像处理相结合的混合方法，实现实时书法评测：

- **孪生网络**：学习用户书写与标准字帖的视觉相似度
- **规则分析**：提取几何特征，提供可解释的反馈
- **边缘优化**：在树莓派 5 上完全离线运行，推理时间小于 1 秒

### 与 DeepVision 的关系

- **架构灵感**：本项目参考了 DeepVision 的分层方式与接口设计。
- **不是直接依赖**：当前仓库不会把 DeepVision 当作第三方包直接导入运行，相关能力已经在本仓库中本地实现。
- **当前主链路**：桌面应用真实入口主要走 `main.py -> views/* -> services/*`，`core/` 与 `data/` 更多承担算法分层和后续架构演进职责。

### 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         InkPi v2.0                              │
├─────────────────────────────────────────────────────────────────┤
│  core/                                                          │
│  ├── models/siamese_net.py      # MobileNetV3-Small 孪生网络    │
│  ├── evaluation/evaluator.py    # 四维评分算法                  │
│  └── inference/engine.py        # 多后端推理引擎                │
├─────────────────────────────────────────────────────────────────┤
│  data/                                                          │
│  ├── camera/service.py          # PiCamera/OpenCV 后端          │
│  └── preprocessing/service.py   # 图像预处理流水线              │
├─────────────────────────────────────────────────────────────────┤
│  config/settings.py             # 统一配置管理                  │
├─────────────────────────────────────────────────────────────────┤
│  tools/conversion/              # 模型导出与量化                │
├─────────────────────────────────────────────────────────────────┤
│  training/                      # 训练脚本                      │
└─────────────────────────────────────────────────────────────────┘
```

### 当前代码阅读顺序

如果你是第一次进入代码，建议按下面顺序阅读：

1. `main.py`
2. `views/main_window.py`
3. `views/camera_view.py`
4. `services/preprocessing_service.py`
5. `services/evaluation_service.py`
6. `services/database_service.py`

这样会比直接从 `core/` 或 `data/` 开始更容易看清当前实际运行链路。

### 快速开始

#### 安装

```bash
# 克隆仓库
git clone https://github.com/zong1024/InkPi-Raspberry-Pi.git
cd InkPi-Raspberry-Pi

# 安装依赖
pip install -r requirements.txt
```

#### 运行

```bash
# 桌面应用（当前主链路基于 views/ + services/）
python main.py

# 运行测试
python test_all.py
```

#### 树莓派部署

```bash
chmod +x build_rpi.sh
./build_rpi.sh
./dist/InkPi
```

### 核心组件

#### 1. 孪生网络模型

基于 MobileNetV3-Small 的轻量级架构，专为边缘设备优化：

```python
from core.models import SiameseNet

model = SiameseNet(pretrained=True, embedding_dim=128)
feature1, feature2 = model(image1, image2)

# 计算余弦相似度
similarity = (feature1 * feature2).sum(dim=1)
```

**模型规格：**
| 属性 | 数值 |
|------|------|
| 骨干网络 | MobileNetV3-Small |
| 嵌入维度 | 128 (L2 归一化) |
| 输入尺寸 | 224 × 224 灰度图 |
| 参数量 | ~1.5M |
| 模型大小 | 8MB (ONNX) / 4MB (INT8 TFLite) |

#### 2. 四维评测系统

针对毛笔字优化：

| 维度 | 指标 | 描述 |
|------|------|------|
| **结构** | 凸包矩形度、留白方差、墨迹占比 | 字形比例与平衡 |
| **笔画** | 骨架分析、边缘复杂度、连通性 | 笔画质量 |
| **平衡** | 重心位置、对称性分析 | 视觉稳定性 |
| **韵律** | 流畅度、端点数量、平滑度 | 行笔节奏 |

```python
from core.evaluation import evaluate_image

result = evaluate_image(image, character_name="永")

print(f"总分: {result.total_score}")
# 输出: 总分: 82

print(result.detail_scores)
# 输出: {'结构': 85, '笔画': 78, '平衡': 88, '韵律': 77}
```

#### 3. 多后端推理

支持多种推理后端，适配不同部署场景：

```python
from core.inference import create_engine

# 根据文件扩展名自动检测
engine = create_engine("models/siamese.onnx")  # ONNX
engine = create_engine("models/siamese.tflite")  # TFLite
engine = create_engine("models/siamese.pth")  # PyTorch

# 计算相似度
score = engine.compute_similarity(template, user_input)
```

| 后端 | 使用场景 | 延迟 (树莓派5) |
|------|----------|----------------|
| PyTorch | 开发调试 | ~500ms |
| ONNX Runtime | 生产环境 | ~150ms |
| TFLite | 优化部署 | ~80ms |
| TFLite INT8 | 边缘设备 | ~50ms |

### 模型训练

#### 数据集准备

```bash
python training/dataset_builder.py --output data/dataset --chars 永,山,水
```

#### 训练模型

```bash
# GPU 训练
python training/train_siamese.py \
    --data data/dataset \
    --epochs 100 \
    --batch-size 32 \
    --lr 0.001

# CPU 训练
bash training/train_cpu.sh
```

#### 导出模型

```bash
# 导出 ONNX
python tools/conversion/converter.py \
    --model models/best.pth \
    --format onnx \
    --output models/

# 导出 TFLite 并量化
python tools/conversion/converter.py \
    --model models/best.pth \
    --format tflite \
    --quantize
```

### 配置

所有设置集中在 `config/settings.py`：

```python
from config import CAMERA_CONFIG, MODEL_CONFIG, EVALUATION_CONFIG

# 相机设置
CAMERA_CONFIG["preview_width"] = 640
CAMERA_CONFIG["preview_height"] = 480

# 模型设置
MODEL_CONFIG["inference"]["engine"] = "onnx"
MODEL_CONFIG["inference"]["device"] = "cpu"

# 评测阈值
EVALUATION_CONFIG["excellent_threshold"] = 85
```

### 性能指标

| 指标 | 数值 |
|------|------|
| 推理延迟 | 50-150ms (树莓派5) |
| 内存占用 | ~200MB |
| 模型大小 | 8MB (ONNX) |
| 准确率 | 与专家评审一致度 85% |

---

## English

An intelligent Chinese calligraphy evaluation system designed for Raspberry Pi, featuring Siamese network-based similarity scoring and multi-dimensional analysis optimized for brush calligraphy.

### Overview

InkPi provides real-time calligraphy evaluation through a hybrid approach combining deep learning and traditional image processing:

- **Siamese Network**: Learns visual similarity between user input and standard templates
- **Rule-based Analysis**: Extracts geometric features for interpretable feedback
- **Edge-optimized**: Runs entirely offline on Raspberry Pi 5 with sub-second inference

### Quick Start

#### Installation

```bash
git clone https://github.com/zong1024/InkPi-Raspberry-Pi.git
cd InkPi-Raspberry-Pi
pip install -r requirements.txt
```

#### Run

```bash
python main.py        # Desktop application
python test_all.py    # Run tests
```

### Core Components

#### Siamese Network Model

Lightweight MobileNetV3-Small architecture for edge deployment:
- Embedding: 128-dim L2 normalized vectors
- Input: 224×224 grayscale images
- Size: 8MB (ONNX) / 4MB (INT8 TFLite)

#### Four-Dimensional Evaluation

| Dimension | Metrics |
|-----------|---------|
| Structure | Convex rectangularity, whitespace variance |
| Stroke | Skeleton analysis, edge complexity |
| Balance | Center of gravity, symmetry |
| Rhythm | Flow score, smoothness |

#### Multi-Backend Inference

Supports PyTorch, ONNX Runtime, and TFLite with automatic format detection.

### Performance

| Metric | Value |
|--------|-------|
| Latency | 50-150ms (RPi5) |
| Memory | ~200MB |
| Accuracy | 85% expert agreement |

---

## 项目结构 | Project Structure

```
InkPi-Raspberry-Pi/
├── core/                    # 核心算法 | Core algorithms
│   ├── models/              # 模型定义 | Neural network definitions
│   ├── evaluation/          # 评测算法 | Scoring algorithms
│   └── inference/           # 推理引擎 | Inference engines
├── config/                  # 配置管理 | Configuration
├── data/                    # 数据流 | Data pipeline
│   ├── camera/              # 相机服务 | Camera services
│   └── preprocessing/       # 预处理 | Image preprocessing
├── services/                # 业务服务 | Business services
├── tools/                   # 工具 | Utilities
│   └── conversion/          # 模型转换 | Model conversion
├── training/                # 训练脚本 | Training scripts
├── models/                  # 模型权重 | Model weights
├── views/                   # GUI界面 | GUI (PyQt6)
├── miniprogram/             # 微信小程序 | WeChat Mini Program
└── docs/                    # 文档 | Documentation
```

---

## 引用 | Citation

```bibtex
@software{inkpi2026,
  title = {InkPi: Intelligent Calligraphy Evaluation System},
  author = {ZongRui},
  year = {2026},
  url = {https://github.com/zong1024/InkPi-Raspberry-Pi}
}
```

## 许可证 | License

[MIT License](LICENSE)

---

<p align="center">
  <sub>为书法爱好者打造 | Built for calligraphy enthusiasts</sub>
</p>
