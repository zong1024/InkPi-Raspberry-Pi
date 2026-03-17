# InkPi 孪生网络训练流水线

本目录包含 InkPi 书法评测系统的孪生网络训练代码。

## 📁 文件结构

```
training/
├── download_real_dataset.py  # 🆕 真实数据集下载器
├── dataset_builder.py        # 合成数据集生成器
├── train_siamese.py          # 孪生网络训练脚本
├── train_v100.sh             # V100 一键训练脚本
└── README.md                 # 本文件
```

---

## 🔄 训练流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                        Step 1: 数据准备                          │
├─────────────────────────────────────────────────────────────────┤
│  方式A: 真实数据 (推荐)          方式B: 合成数据 (快速测试)       │
│  ┌─────────────────┐          ┌─────────────────┐              │
│  │download_real_   │          │dataset_builder  │              │
│  │  dataset.py     │          │     .py         │              │
│  └────────┬────────┘          └────────┬────────┘              │
│           │                            │                        │
│           ▼                            ▼                        │
│     data/real/                  data/synthetic/                 │
│     ├── originals/              ├── originals/                  │
│     ├── good/                   ├── good/                       │
│     ├── medium/                 ├── medium/                     │
│     └── poor/                   └── poor/                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Step 2: 模型训练                             │
├─────────────────────────────────────────────────────────────────┤
│                     train_siamese.py                            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  SiameseNet (MobileNetV3-Small 骨干)                    │   │
│  │  ├── 输入: [B, 1, 224, 224] 灰度图                      │   │
│  │  ├── 骨干: MobileNetV3-Small (第一层改为单通道)         │   │
│  │  └── 输出: [B, 128] 特征向量 (L2归一化)                 │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  损失函数: CosineEmbeddingLoss  |  优化器: Adam (lr=1e-4)      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Step 3: 输出模型                             │
├─────────────────────────────────────────────────────────────────┤
│  models/                                                        │
│  ├── siamese_calligraphy_best.pth   # 最佳模型权重              │
│  ├── siamese_calligraphy.onnx       # ONNX (树莓派推理)         │
│  └── training_history.json          # 训练历史                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Step 4: 部署到树莓派                         │
├─────────────────────────────────────────────────────────────────┤
│  scp models/siamese_calligraphy.onnx pi@raspberrypi:~/.inkpi/   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🆕 真实数据集支持 (推荐)

合成数据集无法完全模拟真实书法特征，建议使用真实数据集训练。

### 下载真实书法数据集

```bash
# 方式1: 从 GitHub 下载 (推荐，约 200MB)
python training/download_real_dataset.py --source github

# 方式2: 从 Kaggle 下载 (需要 Kaggle API，约 1GB)
pip install kaggle
python training/download_real_dataset.py --source kaggle_styles

# 方式3: 导入本地数据
python training/download_real_dataset.py --source local --input /path/to/images --style kaishu
```

### 使用真实数据训练

```bash
# 使用真实数据集训练
python training/train_siamese.py --data data/real --epochs 100 --pretrained

# 在 V100 服务器上一键训练 (默认使用真实数据)
DATA_SOURCE=real ./training/train_v100.sh
```

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install torch torchvision opencv-python albumentations tqdm onnx
```

### 2. 生成合成数据集

```bash
# 使用默认参数（每个质量级别 100 个样本）
python training/dataset_builder.py

# 自定义参数
python training/dataset_builder.py \
    --templates models/templates \
    --output data/synthetic \
    --samples 200 \
    --quality good medium poor
```

**输出结构：**
```
data/synthetic/
├── originals/    # 原始字帖（参考图像）
├── good/         # 优秀样本（目标值 1.0）
├── medium/       # 中等样本（目标值 0.3）
└── poor/         # 差样本（目标值 -1.0）
```

### 3. 训练模型

```bash
# 基础训练（CPU 或 GPU 自动检测）
python training/train_siamese.py

# 指定 GPU 训练
python training/train_siamese.py --device cuda

# 自定义参数（V100 推荐）
python training/train_siamese.py \
    --epochs 50 \
    --batch-size 64 \
    --lr 1e-4 \
    --pretrained
```

### 4. 训练输出

```
models/
├── siamese_calligraphy_best.pth    # 最佳模型权重
├── siamese_calligraphy_final.pth   # 最终模型权重
├── siamese_calligraphy.onnx        # ONNX 导出模型
└── training_history.json           # 训练历史
```

## 🔧 数据增强策略

| 级别 | 变换 | 模拟效果 | 目标值 |
|------|------|----------|--------|
| `good` | 轻微仿射（±5°旋转，±3%缩放） | 优秀书写 | 1.0 |
| `medium` | 弹性形变 + 轻微腐蚀/膨胀 | 结构微塌、手抖 | 0.3 |
| `poor` | 严重仿射 + 随机擦除 + 透视变换 | 严重变形 | -1.0 |

## 🏗️ 模型架构

```
SiameseNet(
  backbone: MobileNetV3-Small (
    features[0][0]: Conv2d(1, 16, 3, stride=2)  # 修改：单通道输入
    ...
  )
  classifier: Sequential(
    Linear(576, 256)
    Hardswish
    Dropout
    Linear(256, 128)  # 输出 128 维特征
  )
)
```

**训练配置：**
- 损失函数：`CosineEmbeddingLoss`
- 优化器：Adam (lr=1e-4, weight_decay=1e-5)
- 调度器：CosineAnnealingLR
- Batch Size：32（V100 可用 64）
- Epochs：50

## 📊 ONNX 导出

导出的 ONNX 模型规格：

```python
# 输入
input1: [1, 1, 224, 224]  # 字帖图像
input2: [1, 1, 224, 224]  # 用户书写图像

# 输出
feature1: [1, 128]  # 字帖特征（L2 归一化）
feature2: [1, 128]  # 用户特征（L2 归一化）

# 相似度计算
similarity = dot(feature1, feature2)  # 范围 [-1, 1]
```

## 🧪 测试

```bash
# 测试数据集生成
python training/dataset_builder.py --samples 10

# 快速训练测试
python training/train_siamese.py --epochs 2 --batch-size 8
```

## 📝 使用示例

训练完成后，将 `siamese_calligraphy.onnx` 复制到树莓派：

```bash
scp models/siamese_calligraphy.onnx pi@raspberrypi:~/.inkpi/data/models/
```

然后在 InkPi 系统中，`siamese_engine.py` 会自动加载该模型进行推理。

## 🔍 性能优化建议

1. **数据增强**：可以添加更多真实的用户书写数据
2. **难例挖掘**：在线难例负样本挖掘（Online Hard Negative Mining）
3. **模型量化**：训练后量化到 INT8 以提升推理速度
4. **多尺度**：添加多尺度训练增强泛化能力

## ⚠️ 注意事项

- 确保字帖图像为 **224x224** 的灰度图（二值化效果更佳）
- 训练数据需要足够的多样性（建议每个字符至少 100 个样本）
- 如果 Loss 不收敛，尝试降低学习率或增加 Batch Size