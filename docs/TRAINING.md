# InkPi 模型训练指南

本文档详细介绍如何训练 InkPi 书法评测系统的孪生网络模型。

## 目录

- [环境准备](#环境准备)
- [数据集准备](#数据集准备)
- [模型架构](#模型架构)
- [训练流程](#训练流程)
- [模型评估](#模型评估)
- [模型导出与部署](#模型导出与部署)
- [常见问题](#常见问题)

---

## 环境准备

### 硬件要求

| 配置 | 最低要求 | 推荐配置 |
|------|----------|----------|
| CPU | 4核 | 8核+ |
| 内存 | 8GB | 16GB+ |
| GPU | - | NVIDIA RTX 3060+ |
| 显存 | - | 8GB+ |
| 存储 | 10GB | 50GB+ SSD |

### 软件环境

```bash
# 创建虚拟环境
python -m venv inkpi_env
source inkpi_env/bin/activate  # Linux/Mac
# 或
inkpi_env\Scripts\activate  # Windows

# 安装依赖
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
pip install opencv-python numpy scipy pillow matplotlib tqdm
pip install onnx onnxruntime onnxscript  # 用于模型导出
```

更推荐直接使用仓库内置脚本，它们会自动安装训练所需依赖并处理 CPU / GPU 环境差异：

```bash
bash training/train_cpu.sh
# 或
bash training/train_v100.sh
```

### 验证环境

```python
import torch
print(f"PyTorch 版本: {torch.__version__}")
print(f"CUDA 可用: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU 设备: {torch.cuda.get_device_name(0)}")
```

---

## 数据集准备

### 1. 数据集结构

```
data/
├── synthetic/           # 合成数据集
│   ├── originals/       # 原始标准字
│   │   ├── 永.png
│   │   ├── 山.png
│   │   └── ...
│   ├── good/           # 优质样本
│   │   ├── yong_good_0000.png
│   │   └── ...
│   ├── medium/         # 中等样本
│   │   ├── yong_medium_0000.png
│   │   └── ...
│   └── poor/           # 较差样本
│       ├── yong_poor_0000.png
│       └── ...
├── dataset/            # 训练数据集
│   ├── train/
│   └── val/
└── real/               # 真实手写数据
    ├── 永/
    │   ├── 001.jpg
    │   └── ...
    └── ...
```

### 2. 生成合成数据

```bash
# 使用数据集构建工具
python training/dataset_builder.py \
    --output data/synthetic \
    --chars 永,山,水,火,土,金,木,人,大,小 \
    --samples-per-char 50
```

### 3. 下载真实数据（可选）

```bash
# 从云端下载真实手写数据
python training/download_real_dataset.py \
    --output data/real \
    --chars 永,山,水
```

### 4. 数据预处理

图像预处理流程：
1. **灰度转换** - RGB → 灰度图
2. **尺寸归一化** - 统一缩放到 224×224
3. **对比度增强** - CLAHE 自适应直方图均衡
4. **二值化** - Otsu 自适应阈值
5. **数据增强** - 旋转、平移、缩放、噪声

```python
# 预处理示例
from data.preprocessing import PreprocessingService

preprocessor = PreprocessingService()
processed = preprocessor.preprocess(raw_image)
```

---

## 模型架构

### Siamese Network 孪生网络

```
┌─────────────────────────────────────────────────────────────┐
│                    Siamese Network                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   输入 A (224×224)        输入 B (224×224)                  │
│        │                       │                           │
│        ▼                       ▼                           │
│   ┌─────────┐             ┌─────────┐                      │
│   │ Mobile  │             │ Mobile  │  ← 共享权重          │
│   │ NetV3   │             │ NetV3   │                      │
│   │ Small   │             │ Small   │                      │
│   └────┬────┘             └────┬────┘                      │
│        │                       │                           │
│        ▼                       ▼                           │
│   128维向量               128维向量                        │
│   (L2归一化)              (L2归一化)                       │
│        │                       │                           │
│        └───────────┬───────────┘                           │
│                    │                                       │
│                    ▼                                       │
│              余弦相似度                                     │
│                    │                                       │
│                    ▼                                       │
│              相似度分数 (0-1)                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### MobileNetV3-Small 特征提取器

| 层 | 输出通道 | 分辨率 | 说明 |
|----|----------|--------|------|
| Conv2d | 16 | 112×112 | 初始卷积 |
| InvertedResidual × 9 | 96 | 7×7 | MBConv 块 |
| AvgPool | 96 | 1×1 | 全局池化 |
| FC | 128 | - | 嵌入向量 |

### 代码实现

```python
# core/models/siamese_net.py
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision.models import mobilenet_v3_small

class SiameseNet(nn.Module):
    """孪生网络 - 基于 MobileNetV3-Small"""
    
    def __init__(self, embedding_dim=128, pretrained=True):
        super().__init__()
        
        # 加载预训练 MobileNetV3
        backbone = mobilenet_v3_small(pretrained=pretrained)
        
        # 移除分类头
        self.features = backbone.features
        
        # 嵌入层
        self.avgpool = backbone.avgpool
        self.classifier = nn.Sequential(
            nn.Linear(576, embedding_dim),
            nn.ReLU(inplace=True)
        )
    
    def forward_one(self, x):
        """提取单个图像的特征"""
        x = self.features(x)
        x = self.avgpool(x)
        x = torch.flatten(x, 1)
        x = self.classifier(x)
        # L2 归一化
        x = F.normalize(x, p=2, dim=1)
        return x
    
    def forward(self, x1, x2):
        """前向传播 - 返回两个特征向量"""
        feat1 = self.forward_one(x1)
        feat2 = self.forward_one(x2)
        return feat1, feat2
    
    def compute_similarity(self, x1, x2):
        """计算相似度"""
        feat1, feat2 = self.forward(x1, x2)
        # 余弦相似度（已归一化，直接点积）
        similarity = (feat1 * feat2).sum(dim=1)
        return similarity
```

---

## 训练流程

### 1. 训练脚本

```bash
# GPU 训练（推荐）
python training/train_siamese.py \
    --data data/dataset \
    --epochs 100 \
    --batch-size 32 \
    --lr 0.001 \
    --device cuda

# CPU 训练
bash training/train_cpu.sh

# Windows GPU
training/train_windows_gpu.bat
```

### 2. 训练参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--data` | data/dataset | 数据集路径 |
| `--epochs` | 100 | 训练轮数 |
| `--batch-size` | 32 | 批次大小 |
| `--lr` | 0.001 | 学习率 |
| `--weight-decay` | 1e-5 | 权重衰减 |
| `--device` | cuda | 设备 (cuda/cpu) |
| `--save-dir` | models/ | 模型保存目录 |
| `--log-interval` | 10 | 日志间隔 |

### 3. 损失函数

使用 **对比损失 (Contrastive Loss)**：

$$L = \frac{1}{2N} \sum_{i=1}^{N} \left[ y_i \cdot d_i^2 + (1-y_i) \cdot \max(0, m - d_i)^2 \right]$$

其中：
- $y_i \in \{0, 1\}$ - 标签（1=相似，0=不相似）
- $d_i = ||f_A - f_B||_2$ - 欧氏距离
- $m$ - 边界阈值（默认 1.0）

```python
class ContrastiveLoss(nn.Module):
    """对比损失函数"""
    
    def __init__(self, margin=1.0):
        super().__init__()
        self.margin = margin
    
    def forward(self, feat1, feat2, label):
        # 欧氏距离
        distance = F.pairwise_distance(feat1, feat2)
        
        # 对比损失
        loss = label * distance.pow(2) + \
               (1 - label) * F.relu(self.margin - distance).pow(2)
        
        return loss.mean()
```

### 4. 训练循环

```python
def train_epoch(model, dataloader, criterion, optimizer, device):
    """训练一个 epoch"""
    model.train()
    total_loss = 0
    
    for batch in dataloader:
        img1, img2, label = batch
        img1, img2, label = img1.to(device), img2.to(device), label.to(device)
        
        # 前向传播
        feat1, feat2 = model(img1, img2)
        
        # 计算损失
        loss = criterion(feat1, feat2, label.float())
        
        # 反向传播
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        
        total_loss += loss.item()
    
    return total_loss / len(dataloader)
```

### 5. 监控训练

```bash
# 使用 TensorBoard 监控
tensorboard --logdir runs/

# 或查看训练日志
tail -f training.log
```

---

## 模型评估

### 1. 评估指标

| 指标 | 说明 | 公式 |
|------|------|------|
| 准确率 | 正确预测比例 | $\frac{TP+TN}{Total}$ |
| 精确率 | 预测为相似中正确的比例 | $\frac{TP}{TP+FP}$ |
| 召回率 | 实际相似中被正确预测的比例 | $\frac{TP}{TP+FN}$ |
| F1分数 | 精确率和召回率的调和平均 | $\frac{2 \cdot P \cdot R}{P+R}$ |
| AUC | ROC 曲线下面积 | - |

### 2. 运行评估

```bash
# 评估模型
python training/evaluate.py \
    --model models/best.pth \
    --data data/dataset/val \
    --output results/
```

### 3. 评估结果示例

```
===========================================
          InkPi Siamese Model 评估报告
===========================================
模型路径: models/best.pth
数据集: data/dataset/val
样本数: 500

--- 准确率指标 ---
准确率 (Accuracy):  0.872
精确率 (Precision): 0.891
召回率 (Recall):    0.853
F1 分数:           0.872

--- 相似度分布 ---
正样本平均相似度: 0.823
负样本平均相似度: 0.412
最佳阈值: 0.650

--- ROC/AUC ---
AUC: 0.923
```

---

## 模型导出与部署

### 1. 导出 ONNX

```bash
python tools/conversion/converter.py \
    --model models/best.pth \
    --format onnx \
    --output models/siamese.onnx
```

### 2. 导出 TFLite

```bash
# 先转 ONNX，再转 TFLite
python tools/conversion/converter.py \
    --model models/best.pth \
    --format tflite \
    --output models/siamese.tflite
```

### 3. INT8 量化

```bash
# 量化为 INT8 以减小模型大小和提升速度
python tools/conversion/converter.py \
    --model models/best.pth \
    --format tflite \
    --quantize \
    --output models/siamese_int8.tflite
```

### 4. 模型对比

| 格式 | 大小 | 延迟 (树莓派5) | 精度损失 |
|------|------|----------------|----------|
| PyTorch (.pth) | 9.2MB | ~500ms | - |
| ONNX (.onnx) | 8.1MB | ~150ms | 0% |
| TFLite (.tflite) | 7.8MB | ~80ms | 0% |
| TFLite INT8 | 2.0MB | ~50ms | <1% |

---

## 常见问题

### Q1: 训练时显存不足怎么办？

```bash
# 减小 batch size
python training/train_siamese.py --batch-size 16

# 使用混合精度训练
python training/train_siamese.py --amp
```

### Q2: 如何增加新的字符？

1. 准备新字符的标准字模板
2. 生成合成数据或收集真实手写样本
3. 重新训练模型或增量训练

```bash
# 增量训练
python training/train_siamese.py \
    --data data/new_chars \
    --resume models/best.pth \
    --epochs 20
```

### Q3: 模型在树莓派上推理太慢？

1. 使用 ONNX Runtime 替代 PyTorch
2. 使用 TFLite 格式
3. 启用 INT8 量化
4. 减少输入图像分辨率

### Q4: 如何调试数据集问题？

```python
# 可视化数据增强效果
from training.dataset_builder import visualize_augmentations
visualize_augmentations(data_path, output_dir="debug/")
```

---

## 参考资料

- [Siamese Neural Networks for One-shot Image Recognition](https://www.cs.cmu.edu/~rsalakhu/papers/oneshot1.pdf)
- [MobileNetV3 Paper](https://arxiv.org/abs/1905.02244)
- [Contrastive Learning Survey](https://arxiv.org/abs/2011.00376)

---

[返回主页](../README.md)
