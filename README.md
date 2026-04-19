# InkPi

InkPi 是一套面向 **毛笔楷书 / 行书单字练习** 的书法辅助评测系统。项目把树莓派设备端、Qt 小屏正式界面、Cloud API、运维后台、微信小程序、本机 V100 训练链路串成一条完整链路，用于完成：

- 单字拍摄或上传
- 图像预处理与 OCR 识别
- 按书体路由的 ONNX 主评分
- 基于公开标准的五维正式评审项
- 本地存储、云同步、移动端查看
- 设备状态、模型状态与流程状态监控

项目当前定位是：

- 面向初学者和课堂练习的 **辅助评测系统**
- 正式支持 **楷书** 与 **行书** 单字
- `total_score` 继续作为当前统一主分
- 新的五维 `rubric` 作为 **来源明确的正式评审标准层**
- 不替代教师终评，不宣称等同于考级结论

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

OCR 与预处理逻辑在两种书体之间共享；系统在 OCR 之后根据用户手动选择的 `script` 路由到对应评分模型与对应评审标准。

## 2. 当前主链路

当前主链路如下：

`capture/upload -> preprocessing -> OCR -> user-selected script -> script-specific ONNX total_score -> source-backed rubric engine -> EvaluationResult -> local SQLite -> cloud sync -> miniapp / ops console`

其中：

- OCR 与预处理保持统一入口
- 用户必须显式选择书体
- `regular` 只走楷书模型
- `running` 只走行书模型
- 新记录写入 `rubric_*`
- 旧记录保留为 `legacy_v0`

## 3. 评测标准来源

InkPi 当前的五维正式评审标准只使用可公开引用、且能落到单字练习场景的来源：

1. [教育部《中小学书法教育指导纲要》](https://hudong.moe.gov.cn/srcsite/A26/s8001/201301/t20130125_147389.html)
2. [教育部 2025 答复（2022 课标口径）](https://hudong.moe.gov.cn/jyb_xxgk/xxgk_jyta/jyta_jiaocaiju/202501/t20250113_1175495.html)
3. [四川省书法水平测试毛笔书法测试大纲](https://www.sceeo.com/Html/201809/Newsdetail_817.html)
4. [中国美术学院社会美术水平考级中心软笔书法考试与培训标准](https://mskj.caa.edu.cn/bkzn/kjdg/201809/33247.html)
5. [中国书法家协会全国第十三届书法篆刻展评审评议](https://www.cflac.org.cn/ys/sf/sfht/202405/t20240517_1316199.html)

这 5 类来源共同承担 3 个作用：

- 给出教育边界，避免把系统包装成自动考级器
- 给出可量化的评审骨架，尤其是笔法、结构、章法、规范等维度
- 给出协会和展赛语境下对笔法、墨法、笔力、规范识别的正式表述

## 4. 双书体正式评审标准

### 4.1 楷书 `regular_rubric_v1`

| 维度 key | 展示名称 | 权重 | 主要依据 |
| --- | --- | ---: | --- |
| `bifa_dianhua` | 笔法点画 | 30 | 四川“笔法”、国美“提按顿挫及线条力度”、中书协“笔法/笔力” |
| `jieti_zifa` | 结体字法 | 30 | 四川“字法”、国美“结构准确度”、教育部“规范书写/间架结构” |
| `bubai_zhangfa` | 布白章法 | 15 | 四川“章法”、中书协“章法/主次/不过度形式化” |
| `mofa_bili` | 墨法笔力 | 15 | 中书协“墨法、笔力”、国美“点画有力” |
| `guifan_wanzheng` | 规范完整 | 10 | 教育部“规范书写”、中书协“文字正误/写法不规范”、四川“卷面整洁” |

### 4.2 行书 `running_rubric_v1`

| 维度 key | 展示名称 | 权重 | 主要依据 |
| --- | --- | ---: | --- |
| `yongbi_xianzhi` | 用笔线质 | 25 | 国美“提按顿挫、线条力度”、中书协“笔墨控制力” |
| `jieti_qushi` | 结体取势 | 20 | 教育部“规范、通行的行楷/行书”、中书协“结体与气息” |
| `liandai_jiezou` | 连带节奏 | 25 | 行书书体特征、中书协“气韵贯通” |
| `moqi_bili` | 墨气笔力 | 20 | 中书协“墨法、笔力、气息”、国美“点画有力” |
| `guifan_shibie` | 规范识别 | 10 | 教育部规范书写边界、中书协“文字正误/写法不规范” |

### 4.3 评分机制

- 每个评审项输出 `0-100`
- 当前采用 5 档锚点：`20 / 40 / 60 / 80 / 100`
- 每档都绑定来源化描述，不使用“好/一般/差”这类无源表述
- 系统内部会计算 `rubric_preview_total`
- **过渡期不对外展示 `rubric_preview_total`**

## 5. 过渡策略

这轮重构采用“标准先立、主分后切”的策略：

- 现有 ONNX 继续输出 `total_score`
- 当前正式主分 **不变**
- 新的五维正式评审项直接替换旧四维解释层
- `rubric_preview_total` 只用于内部验证和后续训练准备
- 只有在按新标准完成重标注、重训练并通过人工对照后，才考虑切换正式主分来源

## 6. 结果结构

当前标准结果对象以 `EvaluationResult` 为中心，核心字段包括：

- `script`
- `script_label`
- `total_score`
- `quality_level`
- `rubric_version`
- `rubric_family`
- `rubric_items`
- `rubric_summary`
- `rubric_source_refs`
- `score_debug`

其中：

- 新记录写 `rubric_*`
- 旧记录标记为 `legacy_v0`
- 旧的 `dimension_scores` 只作为兼容旧记录的只读遗留字段

## 7. 系统组成

### 7.1 Qt 正式端

树莓派设备端使用 `PyQt6`，面向 `480x320` 的 3.5 寸小屏。它负责：

- 拍照 / 上传
- 书体选择
- 结果展示
- 历史记录浏览

Qt 现在显示的是新的五维正式评审项，不再把旧四维作为正式标准展示。

### 7.2 Cloud API

Cloud API 使用 Flask 构建，负责：

- 登录与设备认证
- 设备结果上传
- 历史列表 / 详情 / 删除
- 方法论说明与验证快照
- 专家复评与验证总览
- 远程 OCR 回退

### 7.3 运维后台

Web 端已经从“重复评测页”重构为 **运维后台**。它负责：

- 监控主机温度、内存、磁盘、网络
- 监控 OCR / 双书体模型 readiness
- 监控评测流程事件与日志输出
- 区分最近结果中的楷书 / 行书记录
- 展示结果对应的 `rubric_family`

### 7.4 微信小程序

小程序现在承担：

- 历史查看
- 详情查看
- 按书体统计
- 删除管理
- 练习建议与依据卡片查看

小程序详情页显示的是新五维评审项与来源依据，不显示 `rubric_preview_total`。

## 8. 训练与部署

双书体训练在本机 V100 上完成，运行时只消费导出的 ONNX 文件，不在树莓派或公网后端训练。

当前导出目标固定为：

- `models/quality_scorer_regular.onnx`
- `models/quality_scorer_regular.metrics.json`
- `models/quality_scorer_running.onnx`
- `models/quality_scorer_running.metrics.json`

训练链路本轮新增了 rubric 预备字段，但仍处于“为后续重训做准备”的阶段：

- `rubric_version`
- `rubric_family`
- `rubric_items`
- `rubric_preview_total`
- 人工评分对照字段

## 9. 快速启动

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

## 10. 文档索引

- [文档索引](./docs/README.md)
- [评价依据与验证计划](./docs/evaluation-basis-and-validation.md)
- [参考项目、论文与官方标准](./docs/reference-projects-and-papers.md)
- [项目流程图（draw.io）](./docs/inkpi-project-flow.drawio)
- [训练说明](./training/README.md)
- [论文主文件](./paper/overleaf/main.tex)

## 11. 论文与展示材料

论文 Overleaf 工程位于：

- [paper/overleaf/main.tex](./paper/overleaf/main.tex)

打包上传文件位于：

- [paper/inkpi-overleaf.zip](./paper/inkpi-overleaf.zip)

本地编译后的 PDF 会同步输出到桌面：

- `C:\Users\zongrui\Desktop\InkPi-paper.pdf`
