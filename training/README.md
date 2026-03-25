# InkPi 训练目录说明

`training/` 目录包含当前项目的训练、数据整理和数据审计脚本。

## 核心文件

- `train_v100.sh`
  - Linux GPU 训练入口
  - 推荐用于 V100 / RTX 环境

- `train_cpu.sh`
  - Linux CPU 训练入口

- `train_windows_gpu.bat`
  - Windows GPU 训练入口

- `train_windows_cpu.bat`
  - Windows CPU 训练入口

- `train_siamese.py`
  - Siamese 主训练脚本

- `prepare_character_dataset.py`
  - 把公开字符级数据整理成 InkPi 可训练格式

- `audit_dataset.py`
  - 训练前严格审计数据质量

- `dataset_builder.py`
  - 生成合成样本

- `download_real_dataset.py`
  - 旧的真实数据下载入口
  - 更适合作为辅助参考，不再推荐直接当主训练集

## 推荐用法

### V100 训练

```bash
DATA_SOURCE=public_character \
DATA_DIR=/path/to/data/public_character \
EPOCHS=30 \
BATCH_SIZE=128 \
NUM_WORKERS=8 \
USE_PRETRAINED=1 \
USE_AMP=1 \
bash training/train_v100.sh
```

### CPU 训练

```bash
bash training/train_cpu.sh
```

### Windows GPU 训练

```cmd
training\train_windows_gpu.bat
```

## 当前推荐数据源

优先级建议：

1. 字符级公开书法数据集
2. 审计通过后的 `public_character`
3. 合成数据作补充

不建议再直接把旧的风格数据当成当前 Siamese 主模型训练集。

## 训练输出

默认输出到项目根目录下的 `models/`：

```text
models/
├── siamese_calligraphy_best.pth
├── siamese_calligraphy_final.pth
├── siamese_calligraphy.onnx
└── training_history.json
```

## 部署提示

树莓派端最关键的是：

- `models/siamese_calligraphy.onnx`

部署时可直接使用：

```bash
MODEL_SOURCE=/path/to/siamese_calligraphy.onnx ./deploy_rpi.sh
```

## 注意事项

- 不要并发启动两条训练写同一输出目录。
- 不要在训练未结束时拿中间产物直接部署。
- 训练前先跑 `audit_dataset.py`，这一步非常值。
