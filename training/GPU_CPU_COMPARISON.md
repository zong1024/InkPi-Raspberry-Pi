# GPU vs CPU 训练版本对比

## 📊 快速对比表

### Linux/macOS

| 维度 | V100 GPU 版本 | CPU 版本 |
|------|-------------|---------|
| **脚本文件** | `train_v100.sh` | `train_cpu.sh` |
| **硬件要求** | NVIDIA V100/RTX 显卡 | 任何 CPU |
| **适用场景** | 企业训练、大规模数据 | 本地开发、CPU 服务器 |
| **PyTorch** | CUDA 11.8 版本 | CPU 只版本 |
| **混合精度 (AMP)** | 启用 ✓ | 禁用 ✗ |
| **批大小** | 128 | 16 |
| **样本数** | 500×3 级别 | 100×3 级别 |
| **训练轮数** | 100 | 30 |
| **学习率** | 3e-4 | 1e-3 |
| **数据线程** | 8 | 1 |
| **预计时间** | 1-2 小时 | 2-4 小时 |
| **推荐数据源** | 真实/合成 | 合成 |

### Windows

| 维度 | GPU 版本 | CPU 版本 |
|------|---------|---------|
| **脚本文件** | `train_windows_gpu.bat` | `train_windows_cpu.bat` |
| **硬件要求** | NVIDIA V100/RTX 显卡 | 任何 CPU |
| **适用场景** | Windows 开发、大规模数据 | Windows 开发、快速测试 |
| **PyTorch** | CUDA 11.8 版本 | CPU 只版本 |
| **混合精度 (AMP)** | 启用 ✓ | 禁用 ✗ |
| **批大小** | 64 | 16 |
| **样本数** | 500×3 级别 | 100×3 级别 |
| **训练轮数** | 100 | 30 |
| **学习率** | 3e-4 | 1e-3 |
| **数据线程** | 4 | 0 |
| **预计时间** | 1-2 小时 | 2-4 小时 |
| **推荐数据源** | 真实/合成 | 合成 |

---

## 🎯 如何选择

### 选择 V100 GPU 版本 ✓

- ✅ 有 NVIDIA GPU（V100/RTX 3090/4090 等）
- ✅ 需要快速训练（1-2 小时）
- ✅ 处理大规模数据集（1000+ 样本）
- ✅ 企业生产环境

```bash
bash training/train_v100.sh
```

### 选择 CPU 版本 ✓

- ✅ 无 GPU 或 GPU 被占用
- ✅ 本地开发调试
- ✅ 云服务器 CPU 实例
- ✅ 快速验证模型效果
- ✅ 资源受限的环境

```bash
bash training/train_cpu.sh
```

---

## 🔧 核心配置差异

### PyTorch 依赖

**V100 版本** (GPU):
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

**CPU 版本**:
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

### 混合精度训练 (AMP)

**V100 版本**:
```python
# 自动启用 AMP
scaler = GradScaler()  # CUDA 设备上启用

# 在训练循环中
with autocast():
    outputs = model(inputs)
    loss = criterion(outputs, targets)
```

**CPU 版本**:
```python
# AMP 在 CPU 上禁用
scaler = None  # CPU 不支持

# 正常浮点运算
outputs = model(inputs)
loss = criterion(outputs, targets)
```

### 数据加载优化

**V100 版本**:
```python
DataLoader(
    dataset,
    batch_size=128,      # 大批大小
    num_workers=8,       # 8 个工作进程
    pin_memory=True,     # GPU 固定内存
    prefetch_factor=4    # 预取缓冲区
)
```

**CPU 版本**:
```python
DataLoader(
    dataset,
    batch_size=16,       # 小批大小
    num_workers=1,       # 1 个工作进程（CPU 限制）
    pin_memory=False     # CPU 不需要
)
```

---

## 📈 性能表现

### 训练速度

```
V100 GPU:     ■■■■■■■■■■ 1-2h (100% 性能)
CPU (i7):     ■■■■■■■□□□ 2-4h (50% 性能)
树莓派 4B:    ■□□□□□□□□□ 12h+ (10% 性能)
```

### 内存占用

```
V100 GPU (16GB VRAM):  7-10GB 显存
CPU 8GB RAM:           4-6GB 内存
树莓派 4GB RAM:        2-3GB 内存
```

---

## 🚀 迁移指南

### 从 CPU 升级到 GPU

如果已在 CPU 上完成训练，想要升级到 GPU：

1. **检查 GPU 可用性**:
   ```bash
   python3 -c "import torch; print(torch.cuda.is_available())"
   ```

2. **直接运行 GPU 版本**:
   ```bash
   bash training/train_v100.sh
   ```

3. **或使用命令行参数**:
   ```bash
   python3 training/train_siamese.py --device cuda --epochs 100 --batch-size 128 --amp
   ```

### 从 GPU 降级到 CPU

如果在 GPU 上训练的模型无法在 CPU 上运行：

1. **重新加载模型**:
   ```python
   model = SiameseNet()
   checkpoint = torch.load('models/siamese_calligraphy_best.pth', 
                          map_location='cpu')  # 关键！
   model.load_state_dict(checkpoint['model_state_dict'])
   model = model.to('cpu')
   ```

2. **导出为 ONNX**（推荐）:
   ```bash
   python3 training/train_siamese.py --device cpu
   ```

---

## 💻 硬件推荐

### 用于 CPU 训练的推荐配置

**最小配置**:
- CPU: Intel i5 或 AMD Ryzen 5 (4核)
- RAM: 8GB
- 存储: 20GB SSD

**推荐配置**:
- CPU: Intel i7/i9 或 AMD Ryzen 7/9 (8+ 核)
- RAM: 16GB+
- 存储: 50GB+ SSD

**高性能配置**:
- CPU: Intel Xeon 或 AMD EPYC (24+ 核)
- RAM: 64GB+
- 存储: 200GB+ NVMe SSD

### 用于 GPU 训练的推荐配置

**最小配置**:
- GPU: NVIDIA RTX 3060 (12GB VRAM)
- CPU: Intel i7 (8核)
- RAM: 16GB

**推荐配置**:
- GPU: NVIDIA V100 或 RTX 4080 (24GB VRAM)
- CPU: Intel i9 或 Xeon (16+ 核)
- RAM: 64GB+

---

## ⚙️ 参数调整建议

### CPU 训练参数

```bash
# 快速验证（5-10分钟）
SAMPLES_PER_LEVEL=50 EPOCHS=5 NUM_WORKERS=1 bash training/train_cpu.sh

# 标准训练（2-3小时）
SAMPLES_PER_LEVEL=100 EPOCHS=30 NUM_WORKERS=2 bash training/train_cpu.sh

# 高质量训练（4-5小时）
SAMPLES_PER_LEVEL=200 EPOCHS=50 NUM_WORKERS=4 bash training/train_cpu.sh
```

### GPU 训练参数

```bash
# 快速验证（5-10分钟）
SAMPLES_PER_LEVEL=100 EPOCHS=5 BATCH_SIZE=64 bash training/train_v100.sh

# 标准训练（30-45分钟）
SAMPLES_PER_LEVEL=300 EPOCHS=50 BATCH_SIZE=128 bash training/train_v100.sh

# 高质量训练（1-2小时）
SAMPLES_PER_LEVEL=500 EPOCHS=100 BATCH_SIZE=128 bash training/train_v100.sh
```

---

## 🔄 模型兼容性

### 模型文件格式

| 格式 | 设备支持 | 文件大小 | 推理速度 |
|------|---------|---------|---------|
| PyTorch (.pth) | CPU/GPU | ~10MB | 快 |
| ONNX (.onnx) | CPU/GPU/树莓派 | ~5MB | 中等 |
| TensorRT (.trt) | GPU 专用 | ~3MB | 最快 |

### 跨设备模型转换

```python
# GPU 训练的模型在 CPU 上运行
import torch

# 加载时指定 CPU
checkpoint = torch.load('model.pth', map_location=torch.device('cpu'))

# 或者转换设备
model.to('cpu')

# 导出为 ONNX（通用格式）
torch.onnx.export(model, dummy_input, 'model.onnx')
```

---

## 📚 文档导航

- [CPU 训练完整指南](CPU_TRAINING_GUIDE.md)
- [V100 GPU 训练脚本](train_v100.sh)
- [CPU 训练脚本](train_cpu.sh)
- [训练问题修复](../TRAINING_FIX.md)

---

## 🎓 学习路径

1. **初学者**: CPU 版本快速验证 → 理解训练流程
2. **开发者**: CPU 版本调试 → GPU 版本优化
3. **研究员**: GPU 版本大规模训练 → 模型优化
4. **工程师**: 完整流程 → 生产部署 → 模型压缩

---

## 📝 示例脚本集合

### Linux/macOS 快速启动

```bash
# 最快验证（3 分钟）
SAMPLES_PER_LEVEL=10 EPOCHS=1 bash training/train_cpu.sh

# 快速测试（30 分钟）
SAMPLES_PER_LEVEL=50 EPOCHS=10 bash training/train_cpu.sh

# 标准训练（3 小时）
bash training/train_cpu.sh

# GPU 快速测试（5 分钟）
SAMPLES_PER_LEVEL=100 EPOCHS=5 bash training/train_v100.sh

# GPU 完整训练（1.5 小时）
bash training/train_v100.sh
```

### Windows 快速启动

```cmd
REM 最快验证（3 分钟）
set SAMPLES_PER_LEVEL=10
set EPOCHS=1
training\train_windows_cpu.bat

REM 快速测试（30 分钟）
set SAMPLES_PER_LEVEL=50
set EPOCHS=10
training\train_windows_cpu.bat

REM 标准 CPU 训练（3 小时）
training\train_windows_cpu.bat

REM GPU 快速测试（5 分钟）
set SAMPLES_PER_LEVEL=100
set EPOCHS=5
training\train_windows_gpu.bat

REM GPU 完整训练（1.5 小时）
training\train_windows_gpu.bat
```

### Windows PowerShell 快速启动

```powershell
# 最快验证（3 分钟）
$env:SAMPLES_PER_LEVEL=10; $env:EPOCHS=1; .\training\train_windows_cpu.bat

# GPU 完整训练（1.5 小时）
.\training\train_windows_gpu.bat
```

### 后台训练

```bash
# CPU 后台训练
nohup bash training/train_cpu.sh > cpu_training.log 2>&1 &

# GPU 后台训练
nohup bash training/train_v100.sh > gpu_training.log 2>&1 &

# 监控日志
tail -f cpu_training.log
tail -f gpu_training.log
```

---

## 🎯 总结

- **快速验证**: 使用 CPU 版本
- **日常开发**: 使用 CPU 版本 + NUM_WORKERS=4
- **最终交付**: 使用 GPU 版本获得最佳性能
- **部署生产**: 转换为 ONNX 格式实现跨平台兼容

