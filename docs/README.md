# InkPi 书法评测系统 v2.0

基于树莓派的智能书法评测系统，采用孪生网络架构，支持毛笔字四维度评分。

## 🏗️ 项目结构

```
InkPi-Raspberry-Pi/
├── core/                    # 核心算法模块
│   ├── models/              # 模型定义
│   │   └── siamese_net.py   # 孪生网络模型
│   ├── evaluation/          # 评测算法
│   │   └── evaluator.py     # 四维评测服务
│   └── inference/           # 推理引擎
│       └── engine.py        # 多后端推理 (PyTorch/ONNX/TFLite)
│
├── config/                  # 配置模块
│   └── settings.py          # 统一配置管理
│
├── data/                    # 数据流控制层
│   ├── camera/              # 相机服务
│   │   └── service.py       # picamera/OpenCV 后端
│   ├── preprocessing/       # 图像预处理
│   │   └── service.py       # 去噪/二值化/增强
│   └── dataset/             # 数据集管理
│
├── services/                # 业务服务层
│   ├── cloud/               # 云服务
│   ├── speech/              # 语音播报
│   └── hardware/            # 硬件控制 (LED/按钮)
│
├── tools/                   # 工具模块
│   ├── conversion/          # 模型转换
│   │   └── converter.py     # PyTorch -> ONNX -> TFLite
│   └── optimization/        # 模型优化
│
├── training/                # 训练脚本
│   ├── train_siamese.py     # 孪生网络训练
│   ├── dataset_builder.py   # 数据集构建
│   └── README.md            # 训练文档
│
├── models/                  # 模型文件
│   ├── templates/           # 标准字模板
│   └── siamese_calligraphy_best.pth
│
├── miniprogram/             # 微信小程序
│
└── views/                   # GUI 视图
```

## 🚀 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行主程序

```bash
python main.py
```

### 运行测试

```bash
python test_all.py
```

## 🎯 核心功能

### 1. 孪生网络模型

- 基于 MobileNetV3-Small 的轻量级架构
- 128 维 L2 归一化特征向量
- 支持余弦相似度计算

```python
from core.models import SiameseNet

model = SiameseNet(pretrained=True)
feat1, feat2 = model(img1, img2)
similarity = (feat1 * feat2).sum(dim=1)
```

### 2. 四维评测系统

- **结构**: 字形匀称、凸包矩形度、留白分布
- **笔画**: 骨架分析、边缘复杂度、连通性
- **平衡**: 重心计算、中轴线偏移
- **韵律**: 行笔流畅度、飞白效果

```python
from core.evaluation import evaluate_image

result = evaluate_image(image, character_name="永")
print(result.total_score)  # 0-100
print(result.detail_scores)  # {"结构": 85, "笔画": 78, ...}
```

### 3. 多后端推理

```python
from core.inference import create_engine

# 自动检测格式
engine = create_engine("model.onnx")
similarity = engine.compute_similarity(img1, img2)
```

## 📦 模型训练

### 准备数据集

```bash
python training/dataset_builder.py --output data/dataset
```

### 训练模型

```bash
# GPU 训练
python training/train_siamese.py --data data/dataset --epochs 100

# CPU 训练
bash training/train_cpu.sh
```

### 导出模型

```bash
# 导出 ONNX
python tools/conversion/converter.py --model models/best.pth --format onnx

# 导出 TFLite (用于树莓派)
python tools/conversion/converter.py --model models/best.pth --format tflite --quantize
```

## 📖 参考

本项目架构参考了 [DeepVision](https://github.com/zong1024/DeepVision) 的设计模式：

- `core/` - 核心算法模块
- `data/` - 数据流控制层
- `config/` - 统一配置管理
- `tools/` - 工具链

## 📄 许可证

MIT License