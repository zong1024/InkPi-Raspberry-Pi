# InkPi 新训练主线

当前分支的训练目标已经改成单链路：

`预处理 -> 官方 OCR -> 单图 ONNX 评分模型`

## 当前训练资产

- `training/build_quality_manifest.py`
  - 从真实字符图片构建质量评分清单
  - `good` 来自 `public_character/originals`
  - `medium` 与 `bad` 来自 `public_character/good` 中的真实样本筛选
- `training/train_quality_scorer.py`
  - 训练单图质量评分模型
  - 输入为 `32x32` 灰度单字图 + 字符编码
  - 输出为 `bad / medium / good` 概率
  - 导出 `quality_scorer.onnx`
- `training/train_quality_scorer.sh`
  - 一键构建清单、训练并导出 ONNX

## 运行方法

```bash
bash training/train_quality_scorer.sh
```

可用环境变量：

- `DATA_DIR`
- `MANIFEST_PATH`
- `OUTPUT_DIR`
- `INPUT_SIZE`
- `LIMIT_GOOD`
- `LIMIT_MEDIUM`
- `LIMIT_BAD`
- `MAX_ITER`

## OCR 说明

- 第一阶段直接使用官方 PaddleOCR 模型做本地识别
- OCR 不再通过旧的模板重排链路
- 后续如果要自训 OCR，可以单独增加 `train_ocr_recognizer.py`，但不影响当前单链路运行

## 旧脚本状态

旧的 Siamese / 模板比对训练脚本在这个分支上已经退出主线，不再用于当前运行时评测。
