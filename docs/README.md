# 文档索引

建议按下面的顺序阅读当前项目文档：

1. [项目总览](../README.md)
2. [评价依据与验证计划](./evaluation-basis-and-validation.md)
3. [参考项目与论文](./reference-projects-and-papers.md)
4. [项目流程图（draw.io）](./inkpi-project-flow.drawio)
5. [训练说明](../training/README.md)

## 当前主链路

`图像采集/上传 -> 预处理 -> OCR -> 手动选择书体 -> 对应 ONNX 主评分 -> 四维解释 -> 本地存储 -> 云同步 -> 小程序 / 运维后台查看`

## 当前项目边界

- 正式支持：楷书、行书单字
- 不支持：隶书、草书、篆书、多字作品
- 不做：自动书体识别
- 主分 `total_score` 为统一口径
- 四维分用于解释与教学反馈，不直接替代教师终评

## 重点入口文件

- [`../main.py`](../main.py)
- [`../views/main_window.py`](../views/main_window.py)
- [`../views/camera_view.py`](../views/camera_view.py)
- [`../services/evaluation_service.py`](../services/evaluation_service.py)
- [`../services/quality_scorer_service.py`](../services/quality_scorer_service.py)
- [`../cloud_api/app.py`](../cloud_api/app.py)
- [`../web_ui/app.py`](../web_ui/app.py)

## 这轮文档重写的目的

这次文档不是单纯做“功能说明”，而是把项目重新写成更接近正式工程和正式论文的表达方式：

- 先说明支持边界，而不是先夸能力
- 先给系统链路，再讲算法模块
- 把“评价依据”和“量化验证”写成正式资产
- 把公开可查的参考项目与论文单独列出，方便答辩与后续扩写
