# InkPi 训练说明

当前训练链路已经重构为按书体拆分的双模型流程，并为新的来源化 rubric 做好了标签准备：

`script=regular/running -> 构建各自 manifest -> 训练各自主评分模型 -> 导出各自 ONNX + metrics`

## 1. 当前支持范围

- 正式支持书体：`regular` / `running`
- 对应展示名称：`楷书` / `行书`
- 训练环境：本机 `V100`
- 部署方式：只分发导出的 `ONNX` 与 `metrics`，树莓派和公网后端只负责推理

## 2. 当前训练与标准的关系

本轮重构的关键点是：

- 新的五维正式评审标准已经进入结果结构和方法论层
- 现有 ONNX 仍然负责输出当前正式主分 `total_score`
- 训练链路本轮先做 **rubric 标签准备**
- 暂不要求立刻产出“新标准主分模型”

也就是说，当前是：

- **标准先立**
- **manifest 先带新标签**
- **主分后切**

## 2.1 当前 bootstrap 训练状态

2026-04-20 已在本机完成一轮实际 bootstrap 训练，并导出：

- `models/quality_scorer_regular.onnx`
- `models/quality_scorer_regular.metrics.json`
- `models/quality_scorer_running.onnx`
- `models/quality_scorer_running.metrics.json`

这轮训练使用的是从树莓派样本目录回收的 160 张共享合成单字样本：

- `good=60`
- `medium=50`
- `bad=50`

说明：

- 当前 `regular / running` 两套模型文件已经真实存在，可直接用于运行时装载
- 当前 `running` 仍是 **共享合成样本 bootstrap 版本**
- 这轮训练的目标是先把双模型运行链、部署链和测试链打通
- 后续仍需要引入真实行书样本、人工评分对照和专家复核，再做正式重训

## 3. 关键脚本

- [`quality_model_layout.py`](./quality_model_layout.py)
  统一管理书体、manifest 和模型产物路径。
- [`build_quality_manifest.py`](./build_quality_manifest.py)
  按 `--script` 构建对应书体的训练清单，并生成新 rubric 预备字段。
- [`train_quality_scorer.py`](./train_quality_scorer.py)
  按 `--script` 训练对应书体的当前主评分模型。
- [`train_quality_scorer.sh`](./train_quality_scorer.sh)
  一键跑完 `regular + running` 两套训练与导出。

## 4. manifest 新增字段

当前 manifest 已新增这些字段，用于未来按新标准重训：

- `rubric_version`
- `rubric_family`
- `rubric_items`
- `rubric_preview_total`
- `manual_review_score`
- `manual_review_level`
- `manual_review_notes`

说明：

- `rubric_items` 用于保存来源化五维评审项标签
- `rubric_preview_total` 是内部预览总分，不是当前对外正式总分
- `manual_review_*` 用于后续引入人工评分与专家校核

## 5. 使用方式

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

## 6. 主要环境变量

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

## 7. 导出产物

- `models/quality_scorer_regular.onnx`
- `models/quality_scorer_regular.metrics.json`
- `models/quality_scorer_running.onnx`
- `models/quality_scorer_running.metrics.json`
- manifest 默认落在 `data/quality_manifests/<script>/quality_manifest.jsonl`

## 8. 与运行时的关系

- `OCR` 与预处理链路保持不变，仍由运行时负责
- 运行时会根据用户手动选择的 `script` 路由到对应 ONNX 模型
- 运行时已经切到新的五维 rubric 展示层
- 当前正式主分仍来自现有 ONNX
- 新标准主分切换要等到：
  - 楷书与行书都完成新标准打标训练
  - 人工评分对照通过
  - 双书体验证稳定

## 9. CI / CD 口径

当前 CI / CD 不训练模型，只做这些事情：

- 校验双模型产物是否存在
- 校验接口与结构是否一致
- 校验训练脚本、manifest、测试是否通过

训练仍然属于本机 V100 的手动 / 半自动流程，不进入默认 GitHub CI。
