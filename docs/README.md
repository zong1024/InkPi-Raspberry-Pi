# InkPi 文档索引

## 先看哪份

如果你第一次接触这个项目，推荐按下面顺序读：

1. [README.md](../README.md)
2. [docs/TRAINING.md](./TRAINING.md)
3. [training/README.md](../training/README.md)

## 文档说明

### 项目总览

- [README.md](../README.md)
  - 项目定位
  - 当前真实运行链路
  - DeepVision 关系说明
  - 树莓派部署入口

### 训练与模型

- [docs/TRAINING.md](./TRAINING.md)
  - 当前推荐训练方案
  - 公开字符级数据集整理
  - 审计、训练、导出与部署注意事项

- [training/README.md](../training/README.md)
  - 训练目录说明
  - 常用训练命令
  - 输出文件说明

- [training/PUBLIC_DATASET_WORKFLOW.md](../training/PUBLIC_DATASET_WORKFLOW.md)
  - 公开字符级书法数据集工作流

## 当前代码阅读建议

如果你要理解应用实际怎么跑，建议从这里开始：

1. `main.py`
2. `views/main_window.py`
3. `views/camera_view.py`
4. `services/preprocessing_service.py`
5. `services/evaluation_service.py`
6. `services/database_service.py`

`core/` 和 `data/` 不是没用，而是它们更偏向算法分层和架构演进，不是桌面端当前最短理解路径。
