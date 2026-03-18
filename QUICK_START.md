# 🚀 快速开始指南

## ⚡ 30 秒快速开始

### 选择你的硬件

#### 💻 无 GPU （任何 CPU）
```bash
cd /path/to/InkPi-Raspberry-Pi-2
bash training/train_cpu.sh
# ⏱️ 约 2-4 小时完成
# ✅ models/siamese_calligraphy.onnx 已生成
```

#### 🎮 有 NVIDIA GPU
```bash
cd /path/to/InkPi-Raspberry-Pi-2
bash training/train_v100.sh
# ⏱️ 约 1-2 小时完成
# ✅ models/siamese_calligraphy.onnx 已生成
```

---

## 🎯 快速选择表

| 场景 | 命令 | 时间 |
|------|------|------|
| 快速验证 (5分钟) | `SAMPLES_PER_LEVEL=20 EPOCHS=2 bash training/train_cpu.sh` | ⚡ |
| 本地开发 (30分钟) | `SAMPLES_PER_LEVEL=50 EPOCHS=10 NUM_WORKERS=4 bash training/train_cpu.sh` | ⚙️ |
| 标准训练 (2-3h) | `bash training/train_cpu.sh` | ⏱️ |
| 高质量 (4-5h) | `SAMPLES_PER_LEVEL=200 EPOCHS=50 bash training/train_cpu.sh` | 📊 |
| GPU 训练 (1-2h) | `bash training/train_v100.sh` | 🚀 |

---

## 📂 关键文件说明

### 训练脚本

- **`training/train_cpu.sh`** - CPU 优化训练（推荐新手）
- **`training/train_v100.sh`** - GPU 优化训练（推荐有 GPU）

### 详细文档

- **`training/CPU_TRAINING_GUIDE.md`** - CPU 完整指南（2500+ 字）
- **`training/GPU_CPU_COMPARISON.md`** - 版本对比分析（2000+ 字）
- **`COMPLETION_REPORT.md`** - 实现完成报告
- **`CPU_VERSION_SUMMARY.md`** - CPU 版本总结

---

## ❓ 常见问题

### Q1: 我没有 GPU，能训练吗？
✅ 完全可以！运行：
```bash
bash training/train_cpu.sh
```

### Q2: 我很赶时间，最快多快？
⚡ 5 分钟快速验证：
```bash
SAMPLES_PER_LEVEL=20 EPOCHS=2 bash training/train_cpu.sh
```

### Q3: 我想用 GPU 加速，怎么做？
🎮 如果有 NVIDIA GPU，运行：
```bash
bash training/train_v100.sh
```

### Q4: 脚本找不到文件怎么办？
📁 确保从项目根目录运行：
```bash
cd /path/to/InkPi-Raspberry-Pi-2
bash training/train_cpu.sh
```

### Q5: 训练失败了怎么排查？
🔧 查看完整故障排查指南：
```bash
# 查看 CPU 训练指南中的故障排查部分
less training/CPU_TRAINING_GUIDE.md
```

---

## 📊 性能参考

| CPU 类型 | 时间 | 样本数 |
|---------|------|--------|
| Intel i7 (8核) | 3h | 300 |
| AMD Ryzen (6核) | 2h | 300 |
| 树莓派 4B | 12h+ | 150 |

---

## 🎓 详细学习路径

### 第一步：理解选择
👉 花 5 分钟阅读：[GPU vs CPU 对比](training/GPU_CPU_COMPARISON.md)

### 第二步：选择方案
- ✅ 有 GPU → `bash training/train_v100.sh`
- ✅ 无 GPU → `bash training/train_cpu.sh`

### 第三步：开始训练
```bash
bash training/train_cpu.sh
# 或
bash training/train_v100.sh
```

### 第四步：查看结果
```bash
ls -lh models/
# siamese_calligraphy_best.pth
# siamese_calligraphy_final.pth
# siamese_calligraphy.onnx ← 推荐用于部署
# training_history.json
```

---

## 🚀 高级用法

### 自定义所有参数
```bash
SAMPLES_PER_LEVEL=150 \
EPOCHS=40 \
BATCH_SIZE=16 \
LEARNING_RATE=1e-3 \
NUM_WORKERS=4 \
DATA_SOURCE=synthetic \
bash training/train_cpu.sh
```

### 后台训练（不中断）
```bash
nohup bash training/train_cpu.sh > training.log 2>&1 &
# 查看进度
tail -f training.log
```

### 使用真实数据集
```bash
DATA_SOURCE=real bash training/train_cpu.sh
```

---

## 📚 文档速查

| 场景 | 查阅文档 |
|------|---------|
| 想快速验证 | [CPU 指南 - 快速开始](training/CPU_TRAINING_GUIDE.md#-快速开始) |
| 想优化性能 | [CPU 指南 - 优化建议](training/CPU_TRAINING_GUIDE.md#-优化建议) |
| 想选择版本 | [GPU vs CPU](training/GPU_CPU_COMPARISON.md) |
| 遇到问题了 | [CPU 指南 - 故障排查](training/CPU_TRAINING_GUIDE.md#-故障排查) |
| 想了解全貌 | [完成报告](COMPLETION_REPORT.md) |

---

## ✅ 使用检查清单

- [ ] 已阅读快速开始指南（本文件）
- [ ] 已选择 CPU 或 GPU 版本
- [ ] 已进入项目根目录
- [ ] 已运行训练脚本
- [ ] 已生成 ONNX 模型
- [ ] 已验证模型可用

---

## 🎯 输出验证

训练完成后，检查是否生成了这些文件：

```bash
models/
├── siamese_calligraphy_best.pth    # ✓ 应该存在
├── siamese_calligraphy_final.pth   # ✓ 应该存在
├── siamese_calligraphy.onnx        # ✓ 应该存在 (推荐)
└── training_history.json           # ✓ 应该存在
```

验证模型：
```bash
python3 -c "import onnxruntime; sess = onnxruntime.InferenceSession('models/siamese_calligraphy.onnx'); print('✓ 模型有效')"
```

---

## 💡 贴士

1. **开发时用 CPU**：本地快速测试，不占用 GPU
2. **生产时用 GPU**：快速训练，提高效率
3. **卡住了？**：查看详细文档，不要跳过故障排查
4. **想更深入？**：阅读训练核心代码 `train_siamese.py`

---

## 🔗 更多资源

- 📖 [CPU 训练完整指南](training/CPU_TRAINING_GUIDE.md)
- 📖 [GPU vs CPU 对比](training/GPU_CPU_COMPARISON.md)
- 📖 [实现总结](CPU_VERSION_SUMMARY.md)
- 📖 [完成报告](COMPLETION_REPORT.md)
- 📖 [训练问题修复](TRAINING_FIX.md)
- 📖 [训练模块 README](training/README.md)

---

**现在就开始训练吧！** 🎉

选择你的方案，运行脚本，然后享受模型训练的魔力！

