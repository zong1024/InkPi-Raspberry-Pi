# InkPi

InkPi 是一套面向 **楷书 / 行书单字练习** 的书法辅助评测系统。项目把树莓派设备端、Qt 小屏正式界面、云端 API、运维后台和微信小程序串成一条完整链路，用于完成：

- 单字拍摄或上传
- 图像预处理与 OCR 识别
- 按书体路由的 ONNX 主评分
- 四维解释分与练习建议
- 本地存储、云同步、移动端查看
- 设备状态与模型状态监控

项目当前定位是：

- 面向初学者和课堂练习的 **辅助评测系统**
- 正式支持 **楷书** 与 **行书** 单字
- 主分 `total_score` 作为统一口径
- 四维分 `structure / stroke / integrity / stability` 作为解释层

它不是自动书法考级系统，也不替代教师终评。

## 1. 正式支持范围

当前正式支持：

- `regular` / `楷书`
- `running` / `行书`

当前不支持：

- 隶书
- 草书
- 篆书
- 多字作品
- 自动书体识别

OCR 与预处理逻辑在两种书体之间共享；系统在 OCR 之后根据用户手动选择的 `script` 路由到对应评分模型。

## 2. 核心链路

当前主链路如下：

`capture/upload -> preprocessing -> OCR -> user-selected script -> script-specific ONNX scorer -> four-dimension explanation -> local SQLite -> cloud sync -> miniapp / ops console`

其中：

- OCR 与预处理保持统一入口
- 用户必须显式选择书体
- `regular` 只走楷书模型
- `running` 只走行书模型
- 历史旧数据迁移时统一补为 `regular`

## 3. 系统组成

### 3.1 Qt 正式端

树莓派设备端使用 `PyQt6`，面向 `480x320` 的 3.5 寸小屏。它负责：

- 拍照 / 上传
- 书体选择
- 结果展示
- 历史记录浏览

Qt 只展示面向用户的正式结果，不暴露调试字段。

### 3.2 Cloud API

Cloud API 使用 Flask 构建，负责：

- 登录与设备认证
- 设备结果上传
- 历史列表 / 详情 / 删除
- 方法论说明与验证快照
- 远程 OCR 回退

### 3.3 运维后台

Web 端已经从“重复评测页”重构为 **运维后台**。它负责：

- 监控主机温度、内存、磁盘、网络
- 监控 OCR / 双书体模型 readiness
- 监控评测流程事件与日志输出
- 区分最近结果中的楷书 / 行书记录

### 3.4 微信小程序

小程序现在承担：

- 历史查看
- 详情查看
- 按书体统计
- 删除管理
- 练习建议与依据卡片查看

## 4. 评测方法

### 4.1 主分

主分由 ONNX 评分模型输出：

- `total_score`
- `quality_level`
- `quality_confidence`

这仍是系统唯一统一口径的“官方分”。

### 4.2 四维解释层

为了回答“为什么是这个分”，项目引入四维解释分：

- `structure` / 结构
- `stroke` / 笔画
- `integrity` / 完整
- `stability` / 稳定

四维分不反推主分，而是服务于：

- 结果解释
- 教学反馈
- 小程序练习建议
- 运维与调试分析

### 4.3 双书体方法论

两种正式支持书体采用不同解释口径：

- 楷书：强调结构规范、重心、比例和起收笔稳定
- 行书：强调连带、节奏、流动性下的结构完整与识别稳定

这意味着四维名称不变，但说明文本、练习建议和边界声明都按 `script` 输出。

## 5. 在线参考项目与论文

这次文档和论文重写，重点参考了几类公开项目和论文的写法：

- **集成式书法智能系统**：Hui 等人在 AAAI 2007 的工作把“分解、评价、生成”组合成一个完整系统，给了我们“不要只写模型，要写完整系统链路”的结构参考。
- **树莓派书法学习辅助系统**：Huda 在 2020 年的博士论文中，把 Raspberry Pi 用在 calligraphy learning assistant system（CLAS）上，验证了边缘设备承载书法学习产品的可行性。
- **中文书写质量自动评测**：Yan 等人 2024 年使用检测+标准样本+Siamese Transformer 做硬笔书法评价，给了我们“数据采集、标准样本、整体流程图”的写法参考。
- **中文书写分数回归与移动端应用**：Xu 等人 2024 年做了基于 CNN 的中文书写工整度评测，并做成移动应用，给了我们“人类评分对照、量化指标、产品出口”的写法参考。
- **从 score-only 到可解释反馈**：Zheng 等人 2025 年在 CCL 任务中强调，仅给分数不足以支撑学习反馈，这和我们把四维解释层、小程序建议页纳入正式链路的方向一致。

详细索引见：

- [参考项目与论文](./docs/reference-projects-and-papers.md)

## 6. 目录结构

- `views/`: PyQt6 页面
- `services/`: 预处理、OCR、评分、数据库、云同步、监控等服务
- `models/`: 结果结构、方法论结构与 ONNX 模型资产
- `cloud_api/`: 云端 Flask API
- `web_ui/`: 本地 Web 路由与运维后台静态资源
- `web_console/`: React 运维后台前端源码
- `miniapp/`: 微信小程序
- `training/`: 双书体训练与导出脚本
- `docs/`: 流程图、方法论、参考资料与补充文档
- `paper/overleaf/`: Overleaf 论文工程

## 7. 快速启动

安装依赖：

```bash
pip install -r requirements.txt
```

运行 Qt 正式端：

```bash
python main.py
```

运行本地运维后台：

```bash
python -m web_ui.app
```

运行 Cloud API：

```bash
python cloud_api/app.py
```

默认端口：

- WebUI：`http://127.0.0.1:5000`
- Cloud API：`http://127.0.0.1:5001`

## 8. 训练与导出

双书体训练在本机 V100 上完成，运行时只消费导出的 ONNX 文件，不在树莓派或公网后端训练。

当前导出目标固定为：

- `models/quality_scorer_regular.onnx`
- `models/quality_scorer_regular.metrics.json`
- `models/quality_scorer_running.onnx`
- `models/quality_scorer_running.metrics.json`

训练说明见：

- [training/README.md](./training/README.md)

## 9. 文档索引

- [文档索引](./docs/README.md)
- [评价依据与验证计划](./docs/evaluation-basis-and-validation.md)
- [参考项目与论文](./docs/reference-projects-and-papers.md)
- [项目流程图（draw.io）](./docs/inkpi-project-flow.drawio)
- [项目流程图预览](./docs/inkpi-project-flow.png)

## 10. 论文与展示材料

论文 Overleaf 工程位于：

- [paper/overleaf/main.tex](./paper/overleaf/main.tex)

打包上传文件位于：

- [paper/inkpi-overleaf.zip](./paper/inkpi-overleaf.zip)

本地编译后的 PDF 会同步输出到桌面：

- `C:\Users\zongrui\Desktop\InkPi-paper.pdf`
