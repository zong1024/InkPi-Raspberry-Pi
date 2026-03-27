# InkPi

基于树莓派的书法智能评测系统，面向离线演示、触控交互和云端结果同步场景。

[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-EE4C2C?logo=pytorch&logoColor=white)](https://pytorch.org/)
[![ONNX](https://img.shields.io/badge/ONNX-1.14+-005CED?logo=onnx&logoColor=white)](https://onnx.ai/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 项目定位

InkPi 不是单纯的算法实验仓库，而是一套可以真正在树莓派上跑起来、可用于比赛演示的书法评测 Demo。

当前仓库同时维护两条能力线：

- `master`
  - 稳定演示版
  - 更适合比赛现场、可控流程和固定字表演示
- `codex/full-recognition-v2`
  - 完全体开发线
  - 自动 OCR 优先，识别范围不再局限于少量模板字
  - 对无模板字符可走通用评分，而不是直接报“不支持字库”

## 和 DeepVision 的关系

- 有参考：本项目在配置组织、服务分层、相机抽象等思路上借鉴了 [DeepVision](https://github.com/zong1024/DeepVision)
- 非直接依赖：当前运行时不会 `import DeepVision`
- 当前主链路：
  - `main.py -> views/* -> services/*`
- `core/` 和 `data/` 更多承担算法分层、训练支持和后续架构演进职责

## 当前能力

- 拍照或导入图片进行单字毛笔字评测
- 四维评分：
  - 结构
  - 笔画
  - 平衡
  - 韵律
- 本地 SQLite 历史记录
- 树莓派 kiosk 启动
- 云端结果同步和微信小程序查看历史结果
- 全字识别开发线中的自动 OCR 候选识别与通用评分

## 识别与评测逻辑

### 稳定演示版

稳定演示版更强调“可控、稳定、可复现”：

- 可以手动锁定评测字
- 适合比赛现场演示固定字
- 模板评分路径更稳定

### 完全体开发线

完全体开发线已经不是“先选字才能评测”的逻辑，而是：

1. 先自动 OCR 识别字符
2. 如果本地有模板：
   - 进入模板评分
3. 如果识别到了字，但本地暂无模板：
   - 进入通用评分
4. 如果 OCR 结果不稳定：
   - 明确提示重拍或手动锁定

这意味着：

- 手动锁字现在只是兜底模式，不再是主流程
- “不在当前支持字库中”这类旧说法只适用于早期封闭字库版本，不再代表完全体方向

详细说明见：

- [docs/FULL_RECOGNITION_V2.md](C:/Users/zongrui/Documents/2/docs/FULL_RECOGNITION_V2.md)

## 真实运行链路

```text
main.py
  -> views/main_window.py
  -> views/camera_view.py
  -> services/preprocessing_service.py
  -> services/recognition_flow_service.py
  -> services/evaluation_service.py
  -> services/database_service.py
```

WebUI 路线：

```text
web_ui/app.py
  -> services/*
  -> local sqlite / cloud sync
```

## 模型说明

### 主评测模型

- `siamese_calligraphy.onnx`
  - 当前主评测模型
  - 双输入：`input1`, `input2`
  - 双输出：`feature1`, `feature2`

### 可选增强模型

- `ch_recognize_mobile_int8.onnx`
  - 旧的可选汉字识别模型
- `style_classifier_int8.onnx`
  - 旧的可选书体分类模型

### 完全体识别前端

完全体分支中已经接入“大字表 OCR 前端 + 本地重排”的新路线：

- 本地或远端 OCR 提供 top-k 候选
- 本地 Siamese / 几何特征进行重排
- 对无模板字符走通用评分

## 快速开始

### 本地运行

```bash
git clone https://github.com/zong1024/InkPi-Raspberry-Pi.git
cd InkPi-Raspberry-Pi
pip install -r requirements.txt
python main.py
```

### 运行测试

```bash
python test_all.py
```

### 启动 WebUI

```bash
python -m web_ui.app
```

默认访问：

- [http://127.0.0.1:5000](http://127.0.0.1:5000)

### 树莓派部署

```bash
chmod +x deploy_rpi.sh
RUN_SELF_TEST=1 ./deploy_rpi.sh
```

如已有训练好的 ONNX：

```bash
MODEL_SOURCE=/path/to/siamese_calligraphy.onnx RUN_SELF_TEST=1 ./deploy_rpi.sh
```

如需安装 kiosk：

```bash
INSTALL_KIOSK=1 ./deploy_rpi.sh
```

## 训练建议

当前推荐优先使用字符级公开书法数据，而不是早期的风格分组数据。

推荐链路：

1. 使用公开字符级书法数据整理成 `public_character`
2. 先运行 `training/audit_dataset.py`
3. 再运行 `training/train_v100.sh`
4. 导出 `siamese_calligraphy.onnx`

示例：

```bash
DATA_SOURCE=public_character \
DATA_DIR=/path/to/data/public_character \
EPOCHS=30 \
BATCH_SIZE=128 \
NUM_WORKERS=8 \
USE_PRETRAINED=1 \
USE_AMP=1 \
bash training/train_v100.sh
```

## 项目结构

```text
InkPi-Raspberry-Pi/
├── config/                  # 配置
├── core/                    # 算法分层与推理封装
├── data/                    # 数据与运行产物
├── docs/                    # 文档
├── full_recognition_v2/     # 完全体识别隔离实现
├── models/                  # 模型、模板、结果对象
├── scripts/                 # kiosk 与启动脚本
├── services/                # 当前主业务逻辑
├── tools/                   # 转换与辅助工具
├── training/                # 训练脚本与数据审计
├── views/                   # PyQt6 UI
├── web_ui/                  # 本地 WebUI
├── cloud_api/               # 云端 API
├── deploy_rpi.sh            # 树莓派部署脚本
├── main.py                  # 应用入口
└── test_all.py              # 回归测试
```

## 文档索引

- [docs/README.md](C:/Users/zongrui/Documents/2/docs/README.md)
- [docs/TRAINING.md](C:/Users/zongrui/Documents/2/docs/TRAINING.md)
- [docs/FULL_RECOGNITION_V2.md](C:/Users/zongrui/Documents/2/docs/FULL_RECOGNITION_V2.md)
- [training/README.md](C:/Users/zongrui/Documents/2/training/README.md)
- [training/PUBLIC_DATASET_WORKFLOW.md](C:/Users/zongrui/Documents/2/training/PUBLIC_DATASET_WORKFLOW.md)
