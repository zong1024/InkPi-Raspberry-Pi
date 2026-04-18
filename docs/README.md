# 文档索引

推荐按下面顺序阅读当前工作区文档：

1. [项目总览](../README.md)
2. [项目总流程图（draw.io）](./inkpi-project-flow.drawio)
3. [评价依据与验证计划](./evaluation-basis-and-validation.md)
4. [训练说明](../training/README.md)

当前工作区主链路：

`图像预处理 -> OCR -> 手动选择书体 -> 对应 ONNX 主评分 -> 四维解释 -> 本地存储 -> 云端同步 -> 小程序 / 运维后台查看`

重点入口文件：

- [`../main.py`](../main.py)
- [`../views/main_window.py`](../views/main_window.py)
- [`../views/camera_view.py`](../views/camera_view.py)
- [`../services/evaluation_service.py`](../services/evaluation_service.py)
- [`../web_ui/app.py`](../web_ui/app.py)
- [`../cloud_api/app.py`](../cloud_api/app.py)
