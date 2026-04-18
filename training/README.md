# InkPi 训练说明

当前训练链路已经重构为按书体拆分的双模型流程：

`script=regular/running -> 构建各自 manifest -> 训练各自主评分模型 -> 导出各自 ONNX + metrics`

## 当前支持范围

- 正式支持书体：`regular` / `running`
- 对应展示名称：`楷书` / `行书`
- 训练环境：本机 `V100`
- 部署方式：只分发导出的 `ONNX` 与 `metrics`，树莓派和公网后端只负责推理

## 关键脚本

- [`quality_model_layout.py`](./quality_model_layout.py)：统一管理书体、manifest 和模型产物路径
- [`build_quality_manifest.py`](./build_quality_manifest.py)：按 `--script` 构建对应书体的训练清单
- [`train_quality_scorer.py`](./train_quality_scorer.py)：按 `--script` 训练对应书体的主评分模型
- [`train_quality_scorer.sh`](./train_quality_scorer.sh)：一键跑完 `regular + running` 两套训练与导出

## 使用方式

完整训练：

```bash
bash training/train_quality_scorer.sh
```

只训练单一书体：

```bash
bash training/train_quality_scorer.sh --script regular
bash training/train_quality_scorer.sh --script running
```

单独执行：

```bash
python training/build_quality_manifest.py --script regular
python training/train_quality_scorer.py --script regular
```

## 主要环境变量

- `DATA_DIR`
- `MANIFEST_ROOT`
- `MANIFEST_PATH`
- `OUTPUT_DIR`
- `SCRIPT`
- `INPUT_SIZE`
- `LIMIT_GOOD`
- `LIMIT_MEDIUM`
- `LIMIT_BAD`
- `MAX_ITER`

## 导出产物

- `models/quality_scorer_regular.onnx`
- `models/quality_scorer_regular.metrics.json`
- `models/quality_scorer_running.onnx`
- `models/quality_scorer_running.metrics.json`
- manifest 默认落在 `data/quality_manifests/<script>/quality_manifest.jsonl`

## 与运行时的关系

- `OCR` 与预处理链路保持不变，仍由运行时负责
- 运行时会根据用户手动选择的 `script` 路由到对应 ONNX 模型
- 本轮不引入自动书体识别，不在树莓派或公网后端进行训练
