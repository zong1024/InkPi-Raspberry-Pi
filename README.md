# InkPi

基于树莓派的书法智能评测系统，面向离线演示与触控交互场景。项目采用 `PyQt6 + OpenCV + ONNX Runtime + SQLite`，结合孪生网络与传统图像分析，对单字毛笔字进行结构化评分与反馈。

[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-EE4C2C?logo=pytorch&logoColor=white)](https://pytorch.org/)
[![ONNX](https://img.shields.io/badge/ONNX-1.14+-005CED?logo=onnx&logoColor=white)](https://onnx.ai/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 项目定位

InkPi 的目标不是做一个纯研究代码仓库，而是做一套可以真正跑在树莓派上的书法评测 Demo。当前仓库已经覆盖：

- 桌面/树莓派端触控 UI
- 图像采集、预处理、模板匹配与混合评测
- SQLite 历史记录与结果展示
- kiosk 自启动部署
- V100 训练、ONNX 导出与树莓派部署链路

## 和 DeepVision 的关系

- **有参考**：本项目在配置组织、分层思路、相机服务抽象等方面借鉴了 [DeepVision](https://github.com/zong1024/DeepVision)。
- **不是直接依赖**：当前仓库运行时不会 `import DeepVision`，也不需要额外安装 DeepVision。
- **当前真实主链路**：桌面应用实际走的是 `main.py -> views/* -> services/*`。
- **`core/` 与 `data/` 的角色**：更多承担算法分层、训练支持和后续架构演进职责。

## 当前真实运行链路

```text
main.py
  -> views/main_window.py
  -> views/camera_view.py
  -> services/preprocessing_service.py
  -> services/evaluation_service.py
  -> services/database_service.py
```

其中：

- `views/`：页面与触控交互
- `services/`：当前应用真正使用的业务逻辑
- `models/`：结果对象、模板、模型权重
- `training/`：训练、审计、公开数据集整理
- `scripts/`：kiosk 启动与部署辅助脚本

## 功能概览

- 单字毛笔字拍照评测
- 四维评分：结构、笔画、平衡、韵律
- 空白画面、非汉字、碎片过多等失败拦截
- 书体风格回退识别
- 评测历史查看与删除
- 树莓派自动开机进入全屏应用

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

### 树莓派部署

推荐使用部署脚本，而不是手工拼环境：

```bash
chmod +x deploy_rpi.sh
RUN_SELF_TEST=1 ./deploy_rpi.sh
```

如果已经有训练好的 ONNX 模型：

```bash
MODEL_SOURCE=/path/to/siamese_calligraphy.onnx RUN_SELF_TEST=1 ./deploy_rpi.sh
```

如需安装 kiosk 自启动：

```bash
INSTALL_KIOSK=1 ./deploy_rpi.sh
```

## 模型说明

当前项目里有三类模型概念：

- `siamese_calligraphy.onnx`
  - 主评测模型
  - 双输入：`input1`, `input2`
  - 双输出：`feature1`, `feature2`
- `ch_recognize_mobile_int8.onnx`
  - 可选汉字识别模型
  - 缺失时会回退到模板匹配
- `style_classifier_int8.onnx`
  - 可选书体分类模型
  - 缺失时会回退到模板风格

当前 Demo 的主可用链路依赖的是 `siamese_calligraphy.onnx`。另外两份模型缺失时不会阻塞主流程。

## 训练建议

当前推荐优先使用**公开字符级书法数据集**训练，而不是旧的风格数据。

推荐顺序：

1. `public_character` 格式的字符级书法数据
2. `training/prepare_character_dataset.py` 整理公开数据
3. `training/audit_dataset.py` 先审计再训练
4. `training/train_v100.sh` 或 `training/train_siamese.py` 开训

V100 正式训练示例：

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

详细训练说明见：

- [docs/TRAINING.md](docs/TRAINING.md)
- [training/README.md](training/README.md)
- [training/PUBLIC_DATASET_WORKFLOW.md](training/PUBLIC_DATASET_WORKFLOW.md)

## 项目结构

```text
InkPi-Raspberry-Pi/
├── config/                  # 配置
├── core/                    # 算法分层与推理封装
├── data/                    # 数据流控制层
├── docs/                    # 文档
├── models/                  # 模型、模板、结果对象
├── scripts/                 # kiosk 与启动脚本
├── services/                # 当前主业务逻辑
├── tools/                   # 转换与辅助工具
├── training/                # 训练脚本与数据审计
├── views/                   # PyQt6 UI
├── build_rpi.sh             # 打包脚本
├── deploy_rpi.sh            # 部署脚本
├── main.py                  # 应用入口
└── test_all.py              # 回归测试
```

## 当前状态说明

这个仓库现在更像“可演示的产品 Demo + 可继续演进的算法工程”，而不是只停留在论文验证阶段。当前重点是：

- 保持树莓派端稳定可演示
- 持续优化识别、评测和 UI 成品感
- 把训练产物稳定接回部署流程

## 文档索引

- [docs/README.md](docs/README.md)
- [docs/TRAINING.md](docs/TRAINING.md)
- [training/README.md](training/README.md)
- [training/PUBLIC_DATASET_WORKFLOW.md](training/PUBLIC_DATASET_WORKFLOW.md)
