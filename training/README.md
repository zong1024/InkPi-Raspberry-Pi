# InkPi 训练说明

当前训练链路已经收敛为：

`真实样本清单 -> 单图质量模型训练 -> 导出 ONNX -> 运行时加载评分`

## 当前训练资产

- [`build_quality_manifest.py`](build_quality_manifest.py)：从真实单字样本构建三档质量清单
- [`train_quality_scorer.py`](train_quality_scorer.py)：训练单图质量评分模型
- [`train_quality_scorer.sh`](train_quality_scorer.sh)：一键执行清单构建、训练和导出

## 运行方式

```bash
bash training/train_quality_scorer.sh
```

也可以单独运行脚本：

```bash
python training/build_quality_manifest.py
python training/train_quality_scorer.py
```

## 主要环境变量

- `DATA_DIR`
- `MANIFEST_PATH`
- `OUTPUT_DIR`
- `INPUT_SIZE`
- `LIMIT_GOOD`
- `LIMIT_MEDIUM`
- `LIMIT_BAD`
- `MAX_ITER`

## 导出产物

- [`../models/quality_scorer.onnx`](../models/quality_scorer.onnx)
- [`../models/quality_scorer.metrics.json`](../models/quality_scorer.metrics.json)

## 与运行时的关系

- 运行时 OCR 由 [`../services/local_ocr_service.py`](../services/local_ocr_service.py) 负责
- 运行时质量评分由 [`../services/quality_scorer_service.py`](../services/quality_scorer_service.py) 加载 ONNX 模型完成
- 当前运行时不再把模板库对比或 Siamese 双图评分作为主链路
