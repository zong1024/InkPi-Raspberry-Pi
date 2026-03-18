# InkPi 训练脚本修复说明

## 问题描述

运行 `train_v100.sh` 时报错找不到真实训练集文件夹：
```
❌ 数据目录不存在: data/real
```

## 根本原因

`train_v100.sh` 中使用了 **相对路径** 来指定数据目录和模型文件路径：

```bash
# 原始代码（错误）
DATA_DIR="data/real"              # 相对路径
DATA_DIR="data/synthetic"         # 相对路径
```

### 为什么会出错？

当 shell 脚本传递路径参数给 Python 脚本时：

1. Shell 脚本中设置的相对路径 `data/real` 是相对于 **shell 脚本执行时的当前目录**
2. `train_siamese.py` 内部使用 `Path(__file__).parent.parent` 计算项目根目录，期望接收 **绝对路径**
3. 相对路径在被传递到不同工作目录时会失效，导致文件找不到

## 解决方案

修改所有路径为 **绝对路径**，使用 `$PROJECT_ROOT` 变量：

### 修改清单

#### 1. 真实数据集路径 (第 151 行)
```bash
# ✗ 原始（错误）
DATA_DIR="data/real"

# ✓ 修改后（正确）
DATA_DIR="$PROJECT_ROOT/data/real"
```

#### 2. 真实数据集统计 (第 150 行)
```bash
# ✗ 原始
TOTAL_COUNT=$(find data/real -name "*.png" 2>/dev/null | wc -l)

# ✓ 修改后
TOTAL_COUNT=$(find "$PROJECT_ROOT/data/real" -name "*.png" 2>/dev/null | wc -l)
```

#### 3. 合成数据集路径 (第 176 行)
```bash
# ✗ 原始
EXISTING_SAMPLES=$(find data/synthetic/good -name "*.png" 2>/dev/null | wc -l)
python3 training/dataset_builder.py --output data/synthetic ...

# ✓ 修改后
EXISTING_SAMPLES=$(find "$PROJECT_ROOT/data/synthetic/good" -name "*.png" 2>/dev/null | wc -l)
python3 training/dataset_builder.py --output "$PROJECT_ROOT/data/synthetic" ...
```

#### 4. 模型文件检查 (第 225 行)
```bash
# ✗ 原始
if [ ! -f "models/siamese_calligraphy_best.pth" ]; then
if [ -f "models/siamese_calligraphy.onnx" ]; then

# ✓ 修改后
if [ ! -f "$PROJECT_ROOT/models/siamese_calligraphy_best.pth" ]; then
if [ -f "$PROJECT_ROOT/models/siamese_calligraphy.onnx" ]; then
```

#### 5. 模型统计输出 (第 278-293 行)
```bash
# ✗ 原始
if [ -f "models/siamese_calligraphy_best.pth" ]; then

# ✓ 修改后
if [ -f "$PROJECT_ROOT/models/siamese_calligraphy_best.pth" ]; then
```

## 验证修复

修改后，运行脚本时应该正确找到数据目录：

```bash
cd /path/to/InkPi-Raspberry-Pi-2
bash training/train_v100.sh
```

预期输出：
```
[3/6] 下载真实书法数据集...
真实数据集统计:
  - 总计: XXX 张

或

[3/6] 生成合成数据集...
已存在 500 个样本，跳过数据集生成
合成数据集统计:
  - good: 500 张
  - medium: 500 张
  - poor: 500 张
```

## 最佳实践建议

1. **始终使用绝对路径** 在 shell 脚本中传递给 Python 程序
2. **引用变量时加引号** `"$PROJECT_ROOT"` 防止路径包含空格时出错
3. **验证路径存在** 在使用前进行检查
4. **打印调试信息** 在日志中输出使用的完整路径

## 相关文件

- `training/train_v100.sh` - 已修复 ✓
- `training/train_siamese.py` - 无需修改（已正确处理）
- `training/download_real_dataset.py` - 无需修改（已正确处理）
