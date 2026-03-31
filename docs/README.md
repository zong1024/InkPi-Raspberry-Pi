# 文档索引

## 先看什么

如果你现在要理解这条新主线，建议按这个顺序看：

1. [README.md](C:/Users/zongrui/Documents/2/README.md)
2. [training/README.md](C:/Users/zongrui/Documents/2/training/README.md)
3. [cloud_api/app.py](C:/Users/zongrui/Documents/2/cloud_api/app.py)
4. [web_ui/app.py](C:/Users/zongrui/Documents/2/web_ui/app.py)

## 当前主线

当前项目已经改成单链路自动评测：

`预处理 -> 本地官方 OCR -> 单个 ONNX 评分模型 -> 结果展示与云端同步`

与旧版本不同的是：

- 不再依赖模板库评分
- 不再依赖 Siamese 双图比较
- 不再保留手动锁定评测字作为主流程
- 不再区分模板评分和兜底评分

## 代码入口

- [main.py](C:/Users/zongrui/Documents/2/main.py)
- [views/main_window.py](C:/Users/zongrui/Documents/2/views/main_window.py)
- [views/camera_view.py](C:/Users/zongrui/Documents/2/views/camera_view.py)
- [services/evaluation_service.py](C:/Users/zongrui/Documents/2/services/evaluation_service.py)
- [services/local_ocr_service.py](C:/Users/zongrui/Documents/2/services/local_ocr_service.py)
- [services/quality_scorer_service.py](C:/Users/zongrui/Documents/2/services/quality_scorer_service.py)
- [services/database_service.py](C:/Users/zongrui/Documents/2/services/database_service.py)

## 相关文档

- [training/README.md](C:/Users/zongrui/Documents/2/training/README.md)
- [docs/TRAINING.md](C:/Users/zongrui/Documents/2/docs/TRAINING.md)
