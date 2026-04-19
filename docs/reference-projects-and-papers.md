# 参考项目、论文与官方标准

这份索引用来记录当前项目文档、论文和答辩口径的外部依据。它分成两类：

- **官方标准 / 协会 / 展赛语境**：用于支撑“为什么这样定义评审维度”
- **公开项目 / 论文 / 工程文档**：用于支撑“为什么这样组织系统和产品链路”

## 1. 官方标准与协会来源

### 1.1 教育部《中小学书法教育指导纲要》

- 链接：[教育部原文](https://hudong.moe.gov.cn/srcsite/A26/s8001/201301/t20130125_147389.html)
- 参考点：
  - 书法教育具有基础性、实践性、阶段性和规范性
  - 项目应强调规范书写与技能训练边界
- 对 InkPi 的启发：
  - 不把系统写成自动考级器
  - `规范完整`、`规范识别` 必须成为正式维度

### 1.2 教育部 2025 答复（2022 课标口径）

- 链接：[教育部答复](https://hudong.moe.gov.cn/jyb_xxgk/xxgk_jyta/jyta_jiaocaiju/202501/t20250113_1175495.html)
- 参考点：
  - 小学到初中的书法 progression 明确涉及楷书与规范、通行的行楷/行书
- 对 InkPi 的启发：
  - 正式支持范围收敛到楷书与行书更有依据

### 1.3 四川省书法水平测试毛笔书法测试大纲

- 链接：[四川省教育考试院](https://www.sceeo.com/Html/201809/Newsdetail_817.html)
- 参考点：
  - 初段强调笔法、基本结构
  - 中高段强调笔法熟练、点画准确、结构合理、章法规范
  - 标准有明确权重意识
- 对 InkPi 的启发：
  - 五维标准的权重骨架优先参考这类可量化考试大纲

### 1.4 中国美术学院社会美术水平考级中心软笔书法考试与培训标准

- 链接：[中国美院考级中心](https://mskj.caa.edu.cn/bkzn/kjdg/201809/33247.html)
- 参考点：
  - 提按顿挫
  - 线条力度
  - 结构准确度
  - 章法完善
  - 点画有力
- 对 InkPi 的启发：
  - 楷书与行书都需要把“线质/笔力”从抽象好看落到可描述的评审项上

### 1.5 中国书法家协会全国第十三届书法篆刻展评审评议

- 链接：[中国文艺网](https://www.cflac.org.cn/ys/sf/sfht/202405/t20240517_1316199.html)
- 参考点：
  - 笔法、结构、章法、墨法、笔力是正式评审话语
  - 反对形式大于书法本体
  - 强调文字规范、写法不规范等问题
- 对 InkPi 的启发：
  - 新标准需要把“墨法 / 笔力 / 规范识别”纳入，而不只谈结构和识别置信度

## 2. 系统型参考

### 2.1 An Intelligent System for Chinese Calligraphy

- 来源：AAAI 2007
- 链接：[AAAI PDF](https://cdn.aaai.org/AAAI/2007/AAAI07-250.pdf)
- 参考点：
  - 把书法问题写成完整系统，而不只是单个算法模块
- 对 InkPi 的启发：
  - 论文结构要先交代系统链路，再讲评分方法

### 2.2 A Study of Raspberry Pi Applications to Calligraphy

- 来源：Okayama University, 2020
- 链接：[论文 PDF](https://ousar.lib.okayama-u.ac.jp/files/public/6/60936/20201203155610533257/K0006259_fulltext.pdf)
- 参考点：
  - Raspberry Pi 适合作为低成本边缘设备承载书法学习辅助系统
- 对 InkPi 的启发：
  - 设备部署、使用场景和硬件约束应进入正文，而不是只放代码仓库

## 3. 评测型参考

### 3.1 Intelligent Evaluation of Chinese Hard-Pen Calligraphy Using a Siamese Transformer Network

- 来源：Applied Sciences, 2024
- 链接：[MDPI 页面](https://www.mdpi.com/2076-3417/14/5/2051)
- 参考点：
  - 数据采集、标准样本、检测识别和评分流程可以写成完整链路
- 对 InkPi 的启发：
  - 主链路、数据口径、验证过程要一起写

### 3.2 Assessing penmanship of Chinese handwriting: a deep learning-based approach

- 来源：Reading and Writing, 2024
- 链接：[DOI 页面](https://doi.org/10.1007/s11145-024-10531-w)
- 参考点：
  - 使用人工评分作为监督信号
  - 强调样本规模、评分者数量和误差指标
- 对 InkPi 的启发：
  - 评委关心的数据支撑，必须落到量化验证

## 4. 反馈型参考

### 4.1 System Report for CCL25-Eval Task 11

- 来源：CCL 2025
- 链接：[ACL Anthology](https://aclanthology.org/2025.ccl-2.53/)
- 参考点：
  - 仅给分数不足以支持学习改进
- 对 InkPi 的启发：
  - 详情页、统计页、方法论页必须成为正式功能，而不是装饰

## 5. 工程底座参考

### 5.1 PaddleOCR

- 链接：[PaddleOCR GitHub](https://github.com/PaddlePaddle/PaddleOCR)
- 作用：
  - 提供共享 OCR 工程能力

### 5.2 ONNX Runtime

- 链接：[ONNX Runtime](https://onnxruntime.ai/)
- 作用：
  - 支持训练与推理解耦
  - 让本机 V100 训练、树莓派 / 公网后端推理成为稳定组合

## 6. InkPi 与这些来源的关系

InkPi 并不是简单复刻现有公开工作。当前版本的明确差异在于：

- **标准更有出处**：维度、权重、依据都能追溯到官方或协会语境
- **边界更明确**：只正式支持楷书与行书单字
- **工程链路更完整**：树莓派 Qt、Cloud API、运维后台、小程序在同一项目内协同
- **结果结构更正式**：`rubric_*` 进入正式结果对象，而不是停留在说明文档里
- **过渡策略更清楚**：先上线新标准，后切主分，不把结构改造和模型重训绑死在同一轮
