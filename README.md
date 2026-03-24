# InkPi：基于树莓派的书法智能评测系统

[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-EE4C2C?logo=pytorch&logoColor=white)](https://pytorch.org/)
[![ONNX](https://img.shields.io/badge/ONNX-1.14+-005CED?logo=onnx&logoColor=white)](https://onnx.ai/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 前言

一个书法AI产品的落地需要经历从算法任务确立，到方法调研、模型选型和优化、数据采集标定、模型训练、边缘设备部署验证等一整个pipeline。其中对于绝大多数的算法工程师，模型的训练和输出是没有问题的，但是要快速地进行模型在树莓派等边缘设备上的效果验证，则需要嵌入式开发人员的配合才能完成。

为了解决模型边缘部署验证困难的问题，本项目实现了一套完整的书法评测系统框架，旨在提供从模型训练到边缘部署的一站式解决方案。框架经过一年多的开发和维护，目前已经完成核心API的开发，实现包括实时视频流采集、图像预处理、多后端推理引擎、四维评测算法等众多功能。

> **本项目架构参考了 [DeepVision](https://github.com/zong1024/DeepVision) CV算法验证框架的设计思想。当前仓库并不把 DeepVision 作为运行时依赖直接导入，而是在本仓库内部按类似分层思路实现了 `config/`、`data/`、`core/`、`services/`、`views/` 等模块。**

## 系统设计

构建包含推理的书法评测应用所涉及的不仅仅是运行深度学习推理模型，开发者还需要做到以下几点：

- 利用树莓派等边缘设备的摄像头功能
- 平衡设备资源使用和推理结果的质量
- 通过流水线并行运行多个操作（图像采集→预处理→推理→评分→反馈）
- 确保实时性和用户体验

本系统解决了这些挑战，将软件框架解耦为 `核心算法层`、`数据流控制层`、`推理引擎层`，以及 `UI层` 进行框架实现：

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           InkPi v2.0 架构设计                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌──────────┐ │
│  │   摄像头    │───▶│  预处理     │───▶│  推理引擎   │───▶│  评测    │ │
│  │  Camera     │    │ Preprocess  │    │  Inference  │    │ Evaluate │ │
│  └─────────────┘    └─────────────┘    └─────────────┘    └──────────┘ │
│         │                  │                  │                  │      │
│         ▼                  ▼                  ▼                  ▼      │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │                        数据流控制层 (data/)                          ││
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              ││
│  │  │ PiCamera SVC │  │ OpenCV SVC   │  │ Preprocess   │              ││
│  │  └──────────────┘  └──────────────┘  └──────────────┘              ││
│  └─────────────────────────────────────────────────────────────────────┘│
│         │                  │                  │                  │      │
│         ▼                  ▼                  ▼                  ▼      │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │                        核心算法层 (core/)                            ││
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              ││
│  │  │ SiameseNet   │  │ Evaluator    │  │ Inference    │              ││
│  │  │ MobileNetV3  │  │ 4D Scoring   │  │ Multi-backend│              ││
│  │  └──────────────┘  └──────────────┘  └──────────────┘              ││
│  └─────────────────────────────────────────────────────────────────────┘│
│         │                  │                  │                  │      │
│         ▼                  ▼                  ▼                  ▼      │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │                        推理引擎层 (core/inference/)                  ││
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              ││
│  │  │ PyTorch      │  │ ONNX Runtime │  │ TFLite       │              ││
│  │  │ .pth         │  │ .onnx        │  │ .tflite      │              ││
│  │  └──────────────┘  └──────────────┘  └──────────────┘              ││
│  └─────────────────────────────────────────────────────────────────────┘│
│         │                  │                  │                  │      │
│         ▼                  ▼                  ▼                  ▼      │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │                        UI层 (views/)                                ││
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              ││
│  │  │ PyQt6 GUI    │  │ 语音播报     │  │ LED灯效      │              ││
│  │  │ 桌面应用     │  │ TTS反馈      │  │ GPIO控制     │              ││
│  │  └──────────────┘  └──────────────┘  └──────────────┘              ││
│  └─────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────┘
```

### 与 DeepVision 的关系

- **设计来源**：`config/`、`data/`、`core/` 的分层方式，以及相机监听器、配置集中管理等思路，来自对 DeepVision 的借鉴。
- **当前现状**：InkPi 当前运行时不会 `import DeepVision`，而是将这些能力本地化到本仓库中维护。
- **阅读建议**：如果你是第一次读这个项目，先看桌面应用真实入口链路，再回头看 `data/` 和 `core/` 的分层设计会更容易理解。

### 当前真实运行链路

当前桌面应用主链路以 `views/ + services/` 为主：

`main.py` -> `views/main_window.py` -> `views/camera_view.py` -> `services/preprocessing_service.py` -> `services/evaluation_service.py` -> `services/database_service.py`

其中：

- `views/` 负责桌面端 UI、页面跳转和用户交互
- `services/` 负责当前应用实际使用的相机、预处理、评分、存储、语音、LED 等能力
- `data/` 和 `core/` 保留了更偏 DeepVision 风格的底层分层实现，可用于训练、推理封装和后续架构收敛

### 核心算法层 (core/)

包含项目的核心算法实现：

- **models/** - 神经网络模型定义
  - `siamese_net.py` - 基于 MobileNetV3-Small 的孪生网络
  - 支持 128 维 L2 归一化特征向量
  
- **evaluation/** - 评测算法
  - `evaluator.py` - 四维评测系统（结构、笔画、平衡、韵律）
  - 针对毛笔字优化的特征提取
  
- **inference/** - 推理引擎
  - `engine.py` - 多后端推理支持（PyTorch/ONNX/TFLite）
  - 自动格式检测和加载

### 数据流控制层 (data/)

处理图像数据的采集和预处理：

- **camera/** - 相机服务
  - `PiCameraService` - 树莓派相机后端
  - `OpenCVCameraService` - USB 摄像头后端
  - 参考 DeepVision 的 `CameraFrameListener` 接口设计
  
- **preprocessing/** - 图像预处理
  - 灰度转换、去噪、对比度增强
  - 二值化（Otsu/自适应）
  - 透视校正、内容裁剪

### 推理引擎层 (core/inference/)

集成多种推理框架并提供统一模板：

| 后端 | 模型格式 | 延迟 (树莓派5) | 使用场景 |
|------|----------|----------------|----------|
| PyTorch | .pth | ~500ms | 开发调试 |
| ONNX Runtime | .onnx | ~150ms | 生产环境 |
| TFLite | .tflite | ~80ms | 优化部署 |
| TFLite INT8 | .tflite | ~50ms | 边缘设备 |

## API 接口说明

本框架提供了简洁的 Python API，算法模型在代码中的初始化和使用方式如下：

### 孪生网络模型

```python
from core.models import SiameseNet

# 加载预训练模型
model = SiameseNet(pretrained=True, embedding_dim=128)

# 提取特征向量
feature1, feature2 = model(image1, image2)

# 计算余弦相似度
similarity = (feature1 * feature2).sum(dim=1)
```

### 四维评测系统

```python
from core.evaluation import evaluate_image

# 执行评测
result = evaluate_image(image, character_name="永")

# 获取分数
print(f"总分: {result.total_score}")  # 0-100
print(result.detail_scores)
# {'结构': 85, '笔画': 78, '平衡': 88, '韵律': 77}

# 获取反馈
print(result.feedback)
# "良好！注意字的重心位置"
```

### 多后端推理

```python
from core.inference import create_engine

# 自动检测模型格式并加载
engine = create_engine("models/siamese.onnx")

# 计算相似度
score = engine.compute_similarity(template, user_input)
```

### 相机服务

```python
from data.camera import CameraService, CameraFrameListener

# 定义帧监听器
class MyListener(CameraFrameListener):
    def on_frame(self, frame):
        # 处理每一帧
        return frame

# 启动相机
camera = CameraService()
camera.add_frame_listener(MyListener())
camera.start()
```

## 模型训练与部署工具

> 📖 **详细训练指南**: [docs/TRAINING.md](docs/TRAINING.md) - 包含完整的环境配置、数据准备、训练流程、模型导出等内容

除了推理框架外，本项目提供了一套配套的模型训练和部署工具：

### 训练脚本 (training/)

```bash
# 数据集构建
python training/dataset_builder.py --output data/dataset --chars 永,山,水

# GPU 训练
python training/train_siamese.py --data data/dataset --epochs 100

# CPU 训练
bash training/train_cpu.sh
```

### 模型转换工具 (tools/conversion/)

```bash
# 导出 ONNX
python tools/conversion/converter.py --model best.pth --format onnx

# 导出 TFLite 并量化
python tools/conversion/converter.py --model best.pth --format tflite --quantize
```

支持的转换链：
```
PyTorch (.pth) → ONNX (.onnx) → TFLite (.tflite) → INT8 Quantized
```

## 四维评测体系

系统评测四个维度，每个维度对应传统书法的美学法则：

| 维度 | 评价标准 | 关键指标 |
|------|----------|----------|
| **结构** | 字形匀称程度 | 凸包矩形度、留白分布、墨迹占比 |
| **笔画** | 起收笔到位程度 | 骨架分析、边缘复杂度、连通性 |
| **平衡** | 重心稳定性 | 精确重心坐标、对称性分析 |
| **韵律** | 行笔流畅度 | 连通分量、骨架流畅度、飞白效果 |

**数学公式：**

重心计算：
$$C_x = \frac{\sum x \cdot B(x,y)}{\sum B(x,y)}, \quad C_y = \frac{\sum y \cdot B(x,y)}{\sum B(x,y)}$$

凸包矩形度：
$$R = \frac{P_{hull}}{P_{rect}}$$

总分计算：
$$Score_{total} = \frac{1}{4} \sum_{i=1}^{4} Score_i$$

## 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/zong1024/InkPi-Raspberry-Pi.git
cd InkPi-Raspberry-Pi

# 安装依赖
pip install -r requirements.txt
```

### 运行

```bash
# 桌面应用（主入口链路: main.py -> views/* -> services/*）
python main.py

# 运行测试
python test_all.py
```

### 树莓派部署

```bash
chmod +x build_rpi.sh
./build_rpi.sh
./dist/InkPi
```

## 性能指标

| 指标 | 数值 |
|------|------|
| 推理延迟 | 50-150ms (树莓派5) |
| 内存占用 | ~200MB |
| 模型大小 | 8MB (ONNX) / 4MB (INT8 TFLite) |
| 评测准确率 | 与专家评审一致度 85% |
| 支持字符 | 10 个基础汉字（可扩展） |

## 项目结构

```
InkPi-Raspberry-Pi/
├── core/                    # 核心算法层
│   ├── models/              # 模型定义 (SiameseNet)
│   ├── evaluation/          # 评测算法 (4D Scoring)
│   └── inference/           # 推理引擎 (Multi-backend)
├── data/                    # 数据流控制层
│   ├── camera/              # 相机服务 (PiCamera/OpenCV)
│   └── preprocessing/       # 图像预处理
├── config/                  # 配置管理
├── services/                # 业务服务 (TTS/LED)
├── tools/                   # 工具集
│   └── conversion/          # 模型转换
├── training/                # 训练脚本
├── models/                  # 模型权重
│   └── templates/           # 标准字模板
├── views/                   # UI层 (PyQt6)
└── docs/                    # 文档
```

## 技术栈

| 类别 | 技术 |
|------|------|
| 深度学习 | PyTorch 2.0+, MobileNetV3-Small |
| 推理引擎 | ONNX Runtime, TensorFlow Lite |
| 图像处理 | OpenCV, NumPy |
| GUI | PyQt6 |
| 硬件 | Raspberry Pi 5, PiCamera |
| 语音 | pyttsx3 TTS |

## 参考文献

1. Orbbec SDK v2 Python Binding - GitHub
2. Aesthetic Visual Quality Evaluation of Chinese Handwritings - IJCAI
3. Intelligent Evaluation of Chinese Hard-Pen Calligraphy Using a Siamese Transformer Network - MDPI
4. Fully Convolutional Network Based Skeletonization for Handwritten Chinese Characters - AAAI
5. Siamese Networks for One-shot Learning (Koch et al., 2015)

## 引用

如果本项目对您的研究有帮助，请引用：

```bibtex
@software{inkpi2026,
  title = {InkPi: Intelligent Calligraphy Evaluation System},
  author = {ZongRui},
  year = {2026},
  url = {https://github.com/zong1024/InkPi-Raspberry-Pi}
}
```

## 许可证

[MIT License](LICENSE) © 2026 ZongRui

---

<p align="center">
  <sub>为书法爱好者打造 | Built for calligraphy enthusiasts</sub>
</p>
