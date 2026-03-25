# InkPi 训练说明

## 当前推荐路线

当前项目最推荐的训练主线是：

1. 使用**字符级书法数据集**
2. 先整理成 `public_character` 结构
3. 用 `audit_dataset.py` 做严格审计
4. 再启动 V100 训练
5. 导出 `siamese_calligraphy.onnx`
6. 部署到树莓派

不建议继续把“按风格归类”的旧真实数据直接拿来训练当前 Siamese 主模型，因为它不适合当前的字符匹配任务。

## 推荐数据格式

训练脚本当前最适配的是：

```text
data/public_character/
├── originals/
├── good/
├── medium/
└── poor/
```

其中：

- `originals/`：每个字符的标准模板
- `good/`：能与模板字符稳定对齐的真实或公开样本
- `medium/poor/`：如果没有，可以为空

当前训练链路已经支持只有 `good/` 的字符级数据集，只要模板和字符匹配率足够高。

## 整理公开字符级数据

如果原始数据是“按字符分文件夹”的结构，可以先执行：

```bash
python training/prepare_character_dataset.py \
  --input /path/to/public_dataset \
  --output data/public_character \
  --min-images-per-char 4 \
  --max-images-per-char 24 \
  --seed 42 \
  --clear-output
```

## 训练前审计

强烈建议先审计：

```bash
python training/audit_dataset.py \
  --data data/public_character \
  --strict \
  --min-match-ratio 0.95 \
  --min-matched-samples 1000
```

审计主要检查：

- 模板是否存在
- 样本是否能按字符名与模板对齐
- 匹配率是否足够高
- 训练是否会因为坏数据产生虚高指标

## V100 训练

推荐直接用封装脚本：

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

脚本会自动完成：

- CUDA 环境检查
- Python 依赖安装
- 数据集准备与审计
- 训练启动
- 输出文件检查

## 直接调用训练脚本

如果你需要手工控制参数：

```bash
python training/train_siamese.py \
  --data data/public_character \
  --output models \
  --epochs 30 \
  --batch-size 128 \
  --lr 3e-4 \
  --weight-decay 1e-5 \
  --margin 0.0 \
  --train-ratio 0.8 \
  --image-size 224 \
  --embedding-dim 128 \
  --workers 8 \
  --seed 42 \
  --device cuda \
  --negative-ratio 1 \
  --min-match-ratio 0.95 \
  --min-matched-samples 1000 \
  --pretrained \
  --amp
```

## 当前训练逻辑说明

当前版本已经不再推荐“同字质量标签直接映射成损失标签”的旧思路。现在更强调：

- 同字正样本
- 异字负样本
- 审计优先
- 验证集不要被模板衍生样本污染

## 输出文件

训练完成后通常会在 `models/` 下生成：

```text
siamese_calligraphy_best.pth
siamese_calligraphy_final.pth
siamese_calligraphy.onnx
training_history.json
```

其中部署到树莓派最关键的是：

- `siamese_calligraphy.onnx`

## 部署到树莓派

你可以用两种方式让树莓派拿到模型：

### 方式 1：部署脚本复制

```bash
MODEL_SOURCE=/path/to/siamese_calligraphy.onnx RUN_SELF_TEST=1 ./deploy_rpi.sh
```

### 方式 2：手工放到模型目录

```bash
cp /path/to/siamese_calligraphy.onnx models/siamese_calligraphy.onnx
RUN_SELF_TEST=1 ./deploy_rpi.sh
```

运行时也支持环境变量：

```bash
export INKPI_SIAMESE_MODEL=/path/to/siamese_calligraphy.onnx
```

## 注意事项

- 不要同时启动两条训练写同一个 `models/` 目录。
- 训练未结束前，不要把 `models/` 下的权重当最终结果部署。
- 树莓派端当前主评测只强依赖 `siamese_calligraphy.onnx`。
- `ch_recognize_mobile_int8.onnx` 和 `style_classifier_int8.onnx` 属于可选增强模型，缺失时会回退。
