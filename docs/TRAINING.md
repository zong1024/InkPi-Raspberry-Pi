# 训练说明

当前这条分支的训练目标已经变成：

- OCR：直接使用官方 PaddleOCR 本地识别
- 评分：训练单图 ONNX 质量评分模型

不再使用旧的模板对比和 Siamese 双图评分主线。

## 当前训练脚本

- [training/build_quality_manifest.py](C:/Users/zongrui/Documents/2/training/build_quality_manifest.py)
- [training/train_quality_scorer.py](C:/Users/zongrui/Documents/2/training/train_quality_scorer.py)
- [training/train_quality_scorer.sh](C:/Users/zongrui/Documents/2/training/train_quality_scorer.sh)

## 训练数据

第一版质量评分模型使用真实字符图构建三档清单：

- `good`
- `medium`
- `bad`

清单来自真实图片，不使用运行时模板库。

当前本地仓库中的清单摘要：

- [training/quality_manifest.summary.json](C:/Users/zongrui/Documents/2/training/quality_manifest.summary.json)

## 导出产物

训练完成后会生成：

- [models/quality_scorer.onnx](C:/Users/zongrui/Documents/2/models/quality_scorer.onnx)
- [models/quality_scorer.metrics.json](C:/Users/zongrui/Documents/2/models/quality_scorer.metrics.json)

## 当前指标

当前质量评分模型验证集结果：

- `val_accuracy`: `0.9589`
- `bad`: `57.72`
- `medium`: `74.37`
- `good`: `91.81`

这三组均值已经单调拉开，可以直接作为当前演示版的评分模型。
