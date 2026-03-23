# InkPi Calligraphy Evaluation System

[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-EE4C2C?logo=pytorch&logoColor=white)](https://pytorch.org/)
[![ONNX](https://img.shields.io/badge/ONNX-1.14+-005CED6?logo=onnx&logoColor=white)](https://onnx.ai/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An intelligent Chinese calligraphy evaluation system designed for Raspberry Pi, featuring Siamese network-based similarity scoring and multi-dimensional analysis optimized for brush calligraphy.

## Overview

InkPi provides real-time calligraphy evaluation through a hybrid approach combining deep learning and traditional image processing:

- **Siamese Network**: Learns visual similarity between user input and standard templates
- **Rule-based Analysis**: Extracts geometric features for interpretable feedback
- **Edge-optimized**: Runs entirely offline on Raspberry Pi 5 with sub-second inference

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         InkPi v2.0                              │
├─────────────────────────────────────────────────────────────────┤
│  core/                                                          │
│  ├── models/siamese_net.py      # MobileNetV3-Small Siamese     │
│  ├── evaluation/evaluator.py    # 4D scoring algorithm          │
│  └── inference/engine.py        # Multi-backend inference       │
├─────────────────────────────────────────────────────────────────┤
│  data/                                                          │
│  ├── camera/service.py          # PiCamera/OpenCV backend       │
│  └── preprocessing/service.py   # Image preprocessing pipeline  │
├─────────────────────────────────────────────────────────────────┤
│  config/settings.py             # Centralized configuration     │
├─────────────────────────────────────────────────────────────────┤
│  tools/conversion/              # Model export & quantization   │
├─────────────────────────────────────────────────────────────────┤
│  training/                      # Training scripts              │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/zong1024/InkPi-Raspberry-Pi.git
cd InkPi-Raspberry-Pi

# Install dependencies
pip install -r requirements.txt
```

### Run Application

```bash
# Desktop application
python main.py

# Run tests
python test_all.py
```

### Raspberry Pi Deployment

```bash
chmod +x build_rpi.sh
./build_rpi.sh
./dist/InkPi
```

## Core Components

### 1. Siamese Network Model

Lightweight architecture based on MobileNetV3-Small, optimized for edge deployment:

```python
from core.models import SiameseNet

model = SiameseNet(pretrained=True, embedding_dim=128)
feature1, feature2 = model(image1, image2)

# Compute cosine similarity
similarity = (feature1 * feature2).sum(dim=1)
```

**Model Specifications:**
| Property | Value |
|----------|-------|
| Backbone | MobileNetV3-Small |
| Embedding Dim | 128 (L2 normalized) |
| Input Size | 224 × 224 grayscale |
| Parameters | ~1.5M |
| Model Size | 8MB (ONNX) / 4MB (INT8 TFLite) |

### 2. Four-Dimensional Evaluation

Optimized for brush calligraphy (毛笔字):

| Dimension | Metrics | Description |
|-----------|---------|-------------|
| **Structure** | Convex rectangularity, whitespace variance, ink ratio | Character proportion and balance |
| **Stroke** | Skeleton analysis, edge complexity, connectivity | Brush stroke quality |
| **Balance** | Center of gravity, symmetry analysis | Visual stability |
| **Rhythm** | Flow score, endpoint count, smoothness | Brush movement fluency |

```python
from core.evaluation import evaluate_image

result = evaluate_image(image, character_name="永")

print(f"Total Score: {result.total_score}")
# Output: Total Score: 82

print(result.detail_scores)
# Output: {'结构': 85, '笔画': 78, '平衡': 88, '韵律': 77}
```

### 3. Multi-Backend Inference

Supports multiple inference backends for different deployment scenarios:

```python
from core.inference import create_engine

# Auto-detect from file extension
engine = create_engine("models/siamese.onnx")  # ONNX
engine = create_engine("models/siamese.tflite")  # TFLite
engine = create_engine("models/siamese.pth")  # PyTorch

# Compute similarity
score = engine.compute_similarity(template, user_input)
```

| Backend | Use Case | Latency (RPi5) |
|---------|----------|----------------|
| PyTorch | Development | ~500ms |
| ONNX Runtime | Production | ~150ms |
| TFLite | Optimized | ~80ms |
| TFLite INT8 | Edge | ~50ms |

## Training

### Dataset Preparation

```bash
python training/dataset_builder.py --output data/dataset --chars 永,山,水
```

### Train Model

```bash
# GPU training
python training/train_siamese.py \
    --data data/dataset \
    --epochs 100 \
    --batch-size 32 \
    --lr 0.001

# CPU training
bash training/train_cpu.sh
```

### Export Models

```bash
# Export to ONNX
python tools/conversion/converter.py \
    --model models/best.pth \
    --format onnx \
    --output models/

# Export to TFLite with INT8 quantization
python tools/conversion/converter.py \
    --model models/best.pth \
    --format tflite \
    --quantize
```

## Configuration

All settings are centralized in `config/settings.py`:

```python
from config import CAMERA_CONFIG, MODEL_CONFIG, EVALUATION_CONFIG

# Camera settings
CAMERA_CONFIG["preview_width"] = 640
CAMERA_CONFIG["preview_height"] = 480

# Model settings
MODEL_CONFIG["inference"]["engine"] = "onnx"
MODEL_CONFIG["inference"]["device"] = "cpu"

# Evaluation thresholds
EVALUATION_CONFIG["excellent_threshold"] = 85
```

## Performance

| Metric | Value |
|--------|-------|
| Inference Latency | 50-150ms (RPi5) |
| Memory Usage | ~200MB |
| Model Size | 8MB (ONNX) |
| Accuracy | 85% agreement with experts |

## Project Structure

```
InkPi-Raspberry-Pi/
├── core/                    # Core algorithms
│   ├── models/              # Neural network definitions
│   ├── evaluation/          # Scoring algorithms
│   └── inference/           # Inference engines
├── config/                  # Configuration
├── data/                    # Data pipeline
│   ├── camera/              # Camera services
│   ├── preprocessing/       # Image preprocessing
│   └── dataset/             # Dataset management
├── services/                # Business services
│   ├── cloud/               # Cloud sync
│   ├── speech/              # TTS service
│   └── hardware/            # GPIO control
├── tools/                   # Utilities
│   ├── conversion/          # Model conversion
│   └── optimization/        # Model optimization
├── training/                # Training scripts
├── models/                  # Model weights
│   └── templates/           # Standard templates
├── views/                   # GUI (PyQt6)
├── miniprogram/             # WeChat Mini Program
└── docs/                    # Documentation
```

## References

This project architecture is inspired by [DeepVision](https://github.com/zong1024/DeepVision):

- Modular core/ structure for algorithms
- Data pipeline abstraction layer
- Unified configuration management
- Tool chain for model deployment

## Citation

If you use this project in your research, please cite:

```bibtex
@software{inkpi2026,
  title = {InkPi: Intelligent Calligraphy Evaluation System},
  author = {ZongRui},
  year = {2026},
  url = {https://github.com/zong1024/InkPi-Raspberry-Pi}
}
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <sub>Built with ❤️ for calligraphy enthusiasts</sub>
</p>