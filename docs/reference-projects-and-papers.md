# 参考项目与论文

这份索引用来记录这次文档和论文重写时重点参考的公开项目、论文和官方文档。它们不是 InkPi 的“直接来源”，而是帮助我们把项目写得更像正式工程和正式论文。

## 1. 系统型参考

### 1.1 An Intelligent System for Chinese Calligraphy

- 来源：AAAI 2007
- 链接：[AAAI PDF](https://cdn.aaai.org/AAAI/2007/AAAI07-250.pdf)
- 参考点：
  - 把书法问题写成完整系统，而不只是单个算法模块
  - 把“评价”放在系统功能的一部分来讲
- 对 InkPi 的启发：
  - 论文结构要先交代系统链路，再写评分方法
  - 项目文档要同时交代设备端、云端和结果展示，不只写模型

### 1.2 A Study of Raspberry Pi Applications to Calligraphy

- 来源：Okayama University, 2020
- 链接：[论文 PDF](https://ousar.lib.okayama-u.ac.jp/files/public/6/60936/20201203155610533257/K0006259_fulltext.pdf)
- 参考点：
  - Raspberry Pi 适合作为低成本边缘设备承载书法学习辅助系统
  - 论文中把硬件、软件、使用场景和验证放在同一条工程叙事里
- 对 InkPi 的启发：
  - 强调树莓派设备端不是“演示板”，而是正式交互入口
  - 设备部署、成本、硬件能力和可维护性应该进入论文正文

## 2. 评测型参考

### 2.1 Intelligent Evaluation of Chinese Hard-Pen Calligraphy Using a Siamese Transformer Network

- 来源：Applied Sciences, 2024
- 链接：[MDPI 页面](https://www.mdpi.com/2076-3417/14/5/2051)
- 参考点：
  - 数据采集、预处理、检测识别、标准样本和评分模型可以写成清晰的整体流程
  - 论文中明确交代了数据量、样本来源和实验指标
- 对 InkPi 的启发：
  - 我们也需要在文档和 paper 里明确“主链路图”和“样本验证口径”
  - 项目应把书体支持范围说清楚，而不是笼统写“书法评测”

### 2.2 Assessing penmanship of Chinese handwriting: a deep learning-based approach

- 来源：Reading and Writing, 2024
- 链接：[PDF](https://opus.lib.uts.edu.au/bitstream/10453/181234/2/Assessing%20penmanship%20of%20Chinese%20Handwriting.pdf)
- 参考点：
  - 使用人工评分作为监督信号
  - 明确给出样本规模、评分者数量和误差指标
  - 把评测系统延伸到移动端使用场景
- 对 InkPi 的启发：
  - 评委关心的数据支撑，需要落到“样本量、评分者、验证指标”上
  - 小程序和云端不能只是展示结果，也应承载量化验证信息

## 3. 反馈型参考

### 3.1 System Report for CCL25-Eval Task 11: Aesthetic Assessment of Chinese Handwritings Based on Vision Language Models

- 来源：CCL 2025
- 链接：[ACL Anthology](https://aclanthology.org/2025.ccl-2.53/)
- 参考点：
  - 明确指出仅给分数的反馈不足以支持学习改进
  - 研究开始从“分数预测”走向“多层次反馈生成”
- 对 InkPi 的启发：
  - 四维解释层、小程序建议卡和依据卡是必要的，不是可有可无的装饰
  - 文档应该把“为什么这样评”和“下一步怎么练”写成正式部分

## 4. 工程底座参考

### 4.1 PaddleOCR

- 链接：[PaddleOCR GitHub](https://github.com/PaddlePaddle/PaddleOCR)
- 参考点：
  - 提供稳定的中文 OCR 工程能力
- 对 InkPi 的启发：
  - OCR 在本项目中是共享入口，不承担书体识别责任

### 4.2 ONNX Runtime

- 链接：[ONNX Runtime](https://onnxruntime.ai/)
- 参考点：
  - 支持把训练好的模型以轻量方式部署到树莓派和公网后端
- 对 InkPi 的启发：
  - 训练与推理解耦
  - 本机 V100 训练，边缘设备只做 ONNX 推理

## 5. InkPi 与这些参考的差异

InkPi 并不是简单复刻现有公开工作。当前版本的明确差异在于：

- **边界更明确**：只正式支持楷书与行书单字
- **工程链路更完整**：树莓派 Qt 正式端、Cloud API、运维后台、小程序在同一项目内协同
- **解释层产品化**：四维解释分、依据卡、练习建议进入正式接口和移动端页面
- **验证信息产品化**：样本量、覆盖字数、设备来源、人工复评一致率等指标进入统计链路
- **训练与部署分离**：本机 V100 负责训练与 ONNX 导出，树莓派 / 公网后端只负责推理

## 6. 这份索引怎么用

如果后面你要继续写 PPT、答辩稿或论文补充，可以优先按下面方式使用：

1. 用 1.1 和 1.2 支撑“为什么这是完整系统，而不是单模型 demo”。
2. 用 2.1 和 2.2 支撑“为什么要强调数据规模、人工评分对照和验证指标”。
3. 用 3.1 支撑“为什么不能只给分数，必须有解释与建议”。
4. 用 4.1 和 4.2 支撑“为什么当前工程选择 OCR + ONNX 的部署组合”。
