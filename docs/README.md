# InkPi 文档索引

## 建议阅读顺序

如果你是第一次接触这个项目，推荐按下面顺序阅读：

1. [README.md](C:/Users/zongrui/Documents/2/README.md)
2. [docs/FULL_RECOGNITION_V2.md](C:/Users/zongrui/Documents/2/docs/FULL_RECOGNITION_V2.md)
3. [docs/TRAINING.md](C:/Users/zongrui/Documents/2/docs/TRAINING.md)
4. [training/README.md](C:/Users/zongrui/Documents/2/training/README.md)

## 文档说明

### 项目总览

- [README.md](C:/Users/zongrui/Documents/2/README.md)
  - 项目定位
  - 当前运行链路
  - DeepVision 关系
  - 演示版与完全体分支区别

### 完全体识别

- [docs/FULL_RECOGNITION_V2.md](C:/Users/zongrui/Documents/2/docs/FULL_RECOGNITION_V2.md)
  - 自动 OCR 优先的识别路线
  - 模板评分与通用评分的切换逻辑
  - 远端 OCR 候选服务
  - 当前已实现状态和下一步方向

### 训练与模型

- [docs/TRAINING.md](C:/Users/zongrui/Documents/2/docs/TRAINING.md)
  - 推荐训练链路
  - 数据集审计和导出
  - 部署注意事项

- [training/README.md](C:/Users/zongrui/Documents/2/training/README.md)
  - 训练目录说明
  - 常用命令
  - 产物说明

- [training/PUBLIC_DATASET_WORKFLOW.md](C:/Users/zongrui/Documents/2/training/PUBLIC_DATASET_WORKFLOW.md)
  - 公开字符级书法数据整理流程

## 读代码建议

如果你想快速理解“现在系统实际怎么跑”，建议优先看：

1. [main.py](C:/Users/zongrui/Documents/2/main.py)
2. [views/main_window.py](C:/Users/zongrui/Documents/2/views/main_window.py)
3. [views/camera_view.py](C:/Users/zongrui/Documents/2/views/camera_view.py)
4. [services/recognition_flow_service.py](C:/Users/zongrui/Documents/2/services/recognition_flow_service.py)
5. [services/evaluation_service.py](C:/Users/zongrui/Documents/2/services/evaluation_service.py)
6. [services/database_service.py](C:/Users/zongrui/Documents/2/services/database_service.py)
7. [web_ui/app.py](C:/Users/zongrui/Documents/2/web_ui/app.py)

如果你想理解“完全体识别怎么扩出来”，再接着看：

1. [full_recognition_v2/pipeline.py](C:/Users/zongrui/Documents/2/full_recognition_v2/pipeline.py)
2. [full_recognition_v2/service.py](C:/Users/zongrui/Documents/2/full_recognition_v2/service.py)
3. [full_recognition_v2/http_provider.py](C:/Users/zongrui/Documents/2/full_recognition_v2/http_provider.py)
4. [cloud_api/app.py](C:/Users/zongrui/Documents/2/cloud_api/app.py)
