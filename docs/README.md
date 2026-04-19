# 文档索引

建议按下面的顺序阅读当前项目文档：

1. [项目总览](../README.md)
2. [评价依据与验证计划](./evaluation-basis-and-validation.md)
3. [参考项目、论文与官方标准](./reference-projects-and-papers.md)
4. [项目流程图（draw.io）](./inkpi-project-flow.drawio)
5. [训练说明](../training/README.md)

## 当前主链路

`图像采集/上传 -> 预处理 -> OCR -> 手动选择书体 -> 对应 ONNX 主评分 -> 来源化五维 rubric -> 本地存储 -> 云同步 -> 小程序 / 运维后台查看`

## 当前项目边界

- 正式支持：楷书、行书单字
- 不支持：隶书、草书、篆书、多字作品
- 不做：自动书体识别
- 主分 `total_score` 继续为统一口径
- 五维 rubric 已直接替换旧四维正式展示层
- `rubric_preview_total` 仅用于内部验证，不对外展示
- 旧记录保留为 `legacy_v0`

## 重点入口文件

- [`../main.py`](../main.py)
- [`../views/main_window.py`](../views/main_window.py)
- [`../views/result_view.py`](../views/result_view.py)
- [`../services/evaluation_service.py`](../services/evaluation_service.py)
- [`../services/dimension_scorer_service.py`](../services/dimension_scorer_service.py)
- [`../models/evaluation_framework.py`](../models/evaluation_framework.py)
- [`../models/evaluation_result.py`](../models/evaluation_result.py)
- [`../cloud_api/app.py`](../cloud_api/app.py)
- [`../cloud_api/storage.py`](../cloud_api/storage.py)

## 这轮文档重写的目的

这轮文档不是单纯做“功能说明”，而是把项目统一写成更接近正式工程和正式论文的表达：

- 先说明支持边界，而不是先夸能力
- 先给出有来源的评审标准，再讲实现映射
- 明确“标准先立、主分后切”的过渡策略
- 把 `rubric_source_catalog` 和验证路线写成正式资产
- 让 README、流程图、训练说明和 paper 口径完全一致
