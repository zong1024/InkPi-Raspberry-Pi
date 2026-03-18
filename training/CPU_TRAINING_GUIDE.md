# CPU 版本训练指南

## 📋 概述

`train_cpu.sh` 是针对**无 GPU 设备**优化的训练脚本，支持在普通 CPU 上进行模型训练。

### 适用场景

- ✅ 开发者本地测试（Mac/Linux/Windows WSL）
- ✅ 云服务器 CPU 实例（AWS/阿里云/腾讯云）
- ✅ 树莓派等边缘设备
- ✅ 无 NVIDIA GPU 的服务器

### 特点

| 特点 | V100 版本 | CPU 版本 |
|------|----------|---------|
| **硬件要求** | NVIDIA V100 GPU | 任何 CPU (推荐 4+ 核) |
| **批大小** | 128 | 16 |
| **每级样本** | 500 | 100 |
| **训练轮数** | 100 | 30 |
| **学习率** | 3e-4 | 1e-3 |
| **预计时间** | 1-2 小时 | 2-4 小时 |
| **推荐数据源** | 真实/合成 | 合成 (更快) |

---

## 🚀 快速开始

### 基础使用

```bash
cd /path/to/InkPi-Raspberry-Pi-2
bash training/train_cpu.sh
```

### 自定义参数

```bash
# 生成更多样本，训练更久（推荐）
SAMPLES_PER_LEVEL=200 EPOCHS=50 bash training/train_cpu.sh

# 使用真实数据集
DATA_SOURCE=real bash training/train_cpu.sh

# 增加数据加载线程（多核 CPU）
NUM_WORKERS=4 bash training/train_cpu.sh

# 组合参数
SAMPLES_PER_LEVEL=150 EPOCHS=40 NUM_WORKERS=4 bash training/train_cpu.sh
```

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SAMPLES_PER_LEVEL` | 100 | 每个质量等级的样本数 (good/medium/poor) |
| `EPOCHS` | 30 | 训练轮数 |
| `BATCH_SIZE` | 16 | 批大小 |
| `LEARNING_RATE` | 1e-3 | 学习率 |
| `DATA_SOURCE` | synthetic | 数据源 (real/synthetic) |
| `NUM_WORKERS` | 1 | 数据加载线程数 |

---

## 📊 性能预期

### CPU 计算时间参考

基于不同 CPU 类型的预计训练时间：

| CPU 类型 | 核心数 | 内存 | 样本 | 轮数 | 预计时间 |
|---------|--------|------|------|------|---------|
| Intel i5-10400 | 6 | 16GB | 100×3 | 30 | 2.5h |
| Intel i7-12700 | 12 | 32GB | 200×3 | 50 | 3h |
| AMD Ryzen 5 5600X | 6 | 16GB | 100×3 | 30 | 2h |
| Intel i9-13900K | 24 | 64GB | 300×3 | 50 | 1.5h |
| 树莓派 4B | 4 | 4GB | 50×3 | 10 | 12h+ |

### 内存要求

- **最小**：4GB RAM
- **推荐**：8GB+ RAM
- **样本数 × 批大小** 影响内存占用

---

## 🔧 优化建议

### 1. 减少训练时间

```bash
# 方案 A: 减少样本和轮数（快速验证）
SAMPLES_PER_LEVEL=50 EPOCHS=10 bash training/train_cpu.sh

# 方案 B: 使用合成数据 + 较少轮数
SAMPLES_PER_LEVEL=100 EPOCHS=20 DATA_SOURCE=synthetic bash training/train_cpu.sh
```

### 2. 改善模型质量

```bash
# 方案 A: 增加样本 + 更多轮数（需要时间）
SAMPLES_PER_LEVEL=200 EPOCHS=50 bash training/train_cpu.sh

# 方案 B: 使用真实数据 + 较少轮数
SAMPLES_PER_LEVEL=100 EPOCHS=30 DATA_SOURCE=real bash training/train_cpu.sh
```

### 3. 充分利用多核 CPU

```bash
# 检查 CPU 核心数
nproc

# 如果有 8 核，设置 NUM_WORKERS=4（通常是核心数/2）
NUM_WORKERS=4 bash training/train_cpu.sh
```

### 4. 监控资源占用

```bash
# macOS
top -l 1 | head -n 10

# Linux
top -b -n 1 | head -n 20

# 查看内存占用
free -h  # Linux
```

---

## 📁 训练流程详解

### 7 个步骤

```
[1/7] 环境检查          → 验证 Python 3、pip
      ↓
[2/7] 安装依赖          → 创建虚拟环境、安装 PyTorch CPU 版本
      ↓
[3/7] 准备数据集        → 生成/下载训练数据
      ↓
[4/7] 开始训练          → 运行 train_siamese.py
      ↓
[5/7] 验证模型          → 检查 PyTorch 模型文件
      ↓
[6/7] 导出 ONNX         → 转换为 ONNX 格式
      ↓
[7/7] 结果汇总          → 显示输出文件和部署说明
```

### 输出文件

训练完成后生成的文件：

```
models/
  ├── siamese_calligraphy_best.pth    # 最佳模型 (PyTorch)
  ├── siamese_calligraphy_final.pth   # 最终模型 (PyTorch)
  ├── siamese_calligraphy.onnx        # ONNX 模型（推荐用于推理）
  └── training_history.json           # 训练历史
```

---

## 🐛 故障排查

### 问题 1: 内存不足 (OOM)

**症状**: `RuntimeError: CUDA out of memory` 或系统卡死

**解决方案**:
```bash
# 减小批大小
BATCH_SIZE=8 bash training/train_cpu.sh

# 减少样本数
SAMPLES_PER_LEVEL=50 bash training/train_cpu.sh
```

### 问题 2: 找不到数据

**症状**: `FileNotFoundError: 数据目录不存在`

**解决方案**:
```bash
# 先生成数据
python3 training/dataset_builder.py --samples 100

# 再运行训练
bash training/train_cpu.sh
```

### 问题 3: Python 依赖问题

**症状**: `ModuleNotFoundError: No module named 'torch'`

**解决方案**:
```bash
# 手动激活虚拟环境
source venv/bin/activate

# 重新安装依赖
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

### 问题 4: 脚本权限问题

**症状**: `Permission denied`

**解决方案**:
```bash
# 添加执行权限
chmod +x training/train_cpu.sh

# 再运行
bash training/train_cpu.sh
```

---

## 📈 训练监控

### 实时日志

训练期间会输出类似信息：

```
[4/7] 开始训练模型...
⏱️  预计训练时间: 2-4 小时 (取决于 CPU 性能)

============================================================
🚀 开始训练 (CPU 优化)
============================================================
训练样本: 300
验证样本: 75
Epochs: 30
Batch Size: 16
Learning Rate: 0.001
AMP: False
Workers: 1
============================================================

Epoch 1/30 - Train Loss: 0.4521, Acc: 0.6234 | Val Loss: 0.3892, Acc: 0.6789 | LR: 0.001000
Epoch 2/30 - Train Loss: 0.3845, Acc: 0.7012 | Val Loss: 0.3456, Acc: 0.7234 | LR: 0.001000
...
```

### 保存中间结果

训练过程中每个 epoch 的最佳模型会被自动保存：

```bash
# 查看保存的检查点
ls -lh models/siamese_calligraphy_*.pth
```

---

## 🔄 与 V100 版本的区别

### 配置对比

| 方面 | V100 | CPU |
|------|------|-----|
| **PyTorch 版本** | CUDA 11.8 | CPU Only |
| **AMP (混合精度)** | 启用 ✓ | 禁用 ✗ |
| **批大小** | 128 | 16 |
| **数据加载线程** | 8 | 1 |
| **学习率调度** | OneCycleLR | OneCycleLR |
| **模型编译** | torch.compile | 禁用 |

### 何时选择

- **使用 V100 版本**：有 NVIDIA GPU、需要快速训练、样本数据多
- **使用 CPU 版本**：无 GPU、本地开发、快速验证、成本敏感

---

## 💡 最佳实践

### 1. 逐步增加复杂度

```bash
# 第一步: 快速验证
SAMPLES_PER_LEVEL=50 EPOCHS=10 bash training/train_cpu.sh

# 第二步: 中等规模
SAMPLES_PER_LEVEL=100 EPOCHS=20 bash training/train_cpu.sh

# 第三步: 完整训练
SAMPLES_PER_LEVEL=200 EPOCHS=40 bash training/train_cpu.sh
```

### 2. 数据源选择

```bash
# 快速测试：合成数据
DATA_SOURCE=synthetic bash training/train_cpu.sh

# 最终训练：真实数据
DATA_SOURCE=real bash training/train_cpu.sh
```

### 3. 多核 CPU 优化

```bash
# 查看 CPU 信息
cat /proc/cpuinfo | grep processor | wc -l  # Linux
sysctl -n hw.ncpu  # macOS

# 设置 workers = CPU核心数 / 2
NUM_WORKERS=4 bash training/train_cpu.sh
```

### 4. 后台训练

```bash
# 后台运行（不中断）
nohup bash training/train_cpu.sh > training.log 2>&1 &

# 实时监控
tail -f training.log
```

---

## 📚 相关文档

- [train_v100.sh](train_v100.sh) - GPU 版本训练脚本
- [train_siamese.py](train_siamese.py) - 训练核心代码
- [dataset_builder.py](dataset_builder.py) - 数据集生成
- [TRAINING_FIX.md](../TRAINING_FIX.md) - 训练问题修复记录

---

## 🎯 下一步

1. **模型评估**: 查看 `training_history.json` 了解训练过程
2. **模型部署**: 将 ONNX 模型部署到树莓派
3. **性能优化**: 基于训练结果调整超参数
4. **GPU 升级**: 如果需要更快速度，升级到 V100 或 RTX 系列

---

## 📞 支持

如遇到问题，请检查：
1. Python 版本 ≥ 3.8
2. 数据集是否正确生成
3. 磁盘空间是否充足（建议 10GB+）
4. 网络连接（用于下载真实数据）

