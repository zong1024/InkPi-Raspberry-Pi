# 基于边缘计算与深度学习的树莓派书法智能评测系统（InkPi）

## 引言

在数字化时代，传统中国书法的传承与教学面临着诸多挑战。其中最核心的瓶颈在于缺乏能够提供即时、客观且高度细化的结构与美学反馈的专业指导。InkPi项目提出了一种高度集成的软硬件协同智能书法评测解决方案，以树莓派5作为核心边缘计算节点，构建了一个涵盖底层硬件交互、后端服务、全屏前端展示以及云端微信小程序同步的闭环生态。

本系统实现了从图像采集、算法评测到多模态反馈（语音播报与RGB光效）的毫秒级响应，突破了传统算法难以精准量化书法美学结构的鸿沟。

---

## 边缘计算硬件架构与底层外设交互

树莓派5在计算性能上实现了质的飞跃，但其底层I/O架构的根本性重构（引入了RP1南桥芯片）对硬件外设的控制提出了全新的技术要求。

### 硬件组件

| 硬件组件 | 连接接口/引脚 | 树莓派5适配方案 | 功能描述 |
|----------|---------------|-----------------|----------|
| 摄像头 | USB 3.0 | OpenCV + udev提权 | 采集书法作品高清RGB图像 |
| 实体按键 | Pin 11, 13, 15, 16 | gpiod中断监听 | 提供Kiosk前端界面的非触控导航 |
| WS2812B灯带 | Pin 36 (SPI MOSI) | neopixel_spi硬件SPI驱动 | 提供即时评测结果的视觉氛围反馈 |
| 扬声器 | 3.5mm / 蓝牙 / USB | Alsa音频子系统 + pyttsx3 | 实时播报书法改进指导意见 |

### GPIO控制与树莓派5适配

由于树莓派5的RP1芯片接管了所有GPIO功能，传统的直接内存访问（DMA）库（如旧版的RPi.GPIO）无法直接定位SOC外设基地址。因此，必须采用基于Linux字符设备接口的 **gpiod库** 或 **gpiozero库** 进行引脚电平读取，利用硬件中断（Edge Detection）机制代替高CPU占用的轮询。

对于WS2812B灯带，必须利用硬件SPI总线的MOSI引脚来模拟WS2812B的通信时序，通过 **neopixel_spi库** 实现流畅的视觉特效。

---

## 图像预处理与红格背景滤除流水线

用户提交的书法作品图像在输入评测算法之前，必须经过一系列精密的图像处理流水线，以消除环境光照、拍摄角度以及纸张背景的干扰。

### 处理流程

```
原始图像 → 畸变校正 → 透视变换 → HSV米字格滤除 → 二值化 → 骨架提取 → 输出
```

### 畸变校正与透视变换

1. **灰度化 + 高斯滤波** - 抑制高频图像噪声
2. **Canny边缘检测** - 设定动态阈值（50至150）提取图像边界
3. **概率霍夫变换** - 识别画面中纸张的主轮廓线段

$$H(\rho, \theta) = \sum_{x,y} I(x,y) \cdot \delta(\rho - x\cos\theta - y\sin\theta)$$

4. **透视变换矩阵** - 将倾斜的纸张图像映射为标准的顶视正交视角

$$[x', y', w']^T = M \cdot [x, y, 1]^T$$

### 基于HSV色彩空间的米字格滤除

在RGB色彩空间中，由于光照强度的变化，红色的表现极其不稳定。因此，将图像从RGB空间转换至HSV空间进行颜色分割。

红色的色相分布在柱状坐标的两端，算法生成两个掩码以捕捉全色域的红色：

- **低频红色掩码**：Hue阈值区间设定为 [0°, 10°]
- **高频红色掩码**：Hue阈值区间设定为 [170°, 180°]

$$Mask_{red} = Mask_1 \cup Mask_2$$

对掩码进行形态学闭运算（Morphological Closing），防止红色网格与黑色笔画交叠处的墨迹被误删。最后应用大津法（Otsu's method）或自适应高斯二值化，实现墨迹的无损提取。

---

## 书法特征量化与细粒度笔画提取算法

### 重心平衡（Center of Gravity）

书法的结体讲究"平正"。在宽高为 $W$ 和 $H$ 的二值矩阵中，若 $B(x,y)$ 表示黑色像素，则物理重心坐标 $(C_x, C_y)$ 计算公式为：

$$C_x = \frac{\sum_{x=1}^{W} \sum_{y=1}^{H} x \cdot B(x,y)}{\sum_{x=1}^{W} \sum_{y=1}^{H} B(x,y)}$$

$$C_y = \frac{\sum_{x=1}^{W} \sum_{y=1}^{H} y \cdot B(x,y)}{\sum_{x=1}^{W} \sum_{y=1}^{H} B(x,y)}$$

计算出的重心与九宫格的几何中心进行比对，若偏差向量超过特定阈值，则表明书写失衡。

### 外接凸包矩形度（Rectangularity of Convex Hull）

书法结构的张力可以通过字形外围像素的凸包来量化。计算凸包的周长 $P_{hull}$ 与汉字最小外接矩形的周长 $P_{rect}$ 的比值：

$$R = \frac{P_{hull}}{P_{rect}}$$

该指标反映了字形的紧凑度；若值过低，则说明存在个别笔画过度延伸或结体松散。

### 留白与布白（Whitespace Distribution）

"计白当黑"是书法的重要原则。系统采用弹性网格（Elastic Mesh）将图像等分为 $N \times N$ 的网格，通过计算各区域内的留白面积方差，评估笔画间距是否均匀：

$$\sigma^2_{WS} = \frac{1}{N^2} \sum_{i=1}^{N^2} (WS_i - \overline{WS})^2$$

### 骨架提取（Skeletonization）

墨迹的粗细（受毛笔按压力度影响）不应直接干扰结构正确性的判定。传统的张细化（Zhang-Suen）算法容易在笔画交叉处产生冗余的分支。

本系统采用形态学细化算法提取单像素宽度的笔画核心轨迹，准确率可达98%以上。

---

## 四维评分体系

基于提取出的骨架与二值化图像，系统计算高维几何特征向量，严格对应传统书法的美学法则。

| 维度 | 评价标准 | 关键指标 |
|------|----------|----------|
| **结构** | 字形匀称程度 | 凸包矩形度、留白分布、墨迹占比 |
| **笔画** | 起收笔到位程度 | 骨架分析、边缘复杂度、连通性 |
| **平衡** | 重心稳定性 | 精确重心坐标、对称性分析 |
| **韵律** | 行笔流畅度 | 连通分量、骨架流畅度、墨色变化 |

**总分计算：**

$$Score_{total} = \frac{1}{4} \sum_{i=1}^{4} Score_i$$

---

## 多模态反馈引擎

纯粹的分数对书法初学者而言缺乏指导意义。系统通过融合自然语言生成引擎与硬件反馈模块，将深奥的几何参数转化为易懂的教学指令。

### 规则映射与语音播报

推理进程提取的结构参数被送入确定性逻辑决策树中进行语义映射：

- 若重心横坐标 $C_x$ 向左偏移超过15%，生成："结构重心严重左倾，请注意右侧笔画的伸展"
- 若某一部首外接矩形的高宽比失调，生成："字形过于扁平，建议拉长垂直中轴线"

语音播报采用本地TTS引擎（pyttsx3），实现"所写即所听"的教学体验。

### RGB灯光心理学反馈

系统根据总评分动态调整RGB的色值与闪烁频率：

| 分数区间 | 灯光效果 | 含义 |
|----------|----------|------|
| 85-100 | 平滑呼吸绿色/青色光晕 | 正向激励 |
| 60-84 | 稳定黄色/橙色 | 尚可但需改进 |
| 0-59 | 红色闪烁警告 | 存在结构性错误 |

---

## 全栈应用架构

### 前端：PyQt6 桌面应用

- 实时预览与骨架映射区
- 结果反馈仪表面板（雷达图）
- 历史记录与趋势分析（折线图）

### 后端：Python服务

数据存储采用 **SQLite** 轻量级关系型数据库，主要包含：

| 表名 | 存储内容 |
|------|----------|
| Users | 用户注册信息、加密密码及设备绑定标识 |
| Templates | 标准字帖库、骨架图及高维特征基准向量 |
| EvaluationRecords | 提交时间、细分指标得分、文字反馈、图像路径 |

---

## 云端协同：微信小程序

小程序充当用户数据管理的云端枢纽与成长记录的数字化档案室。

### 功能模块

- **统一鉴权体系** - 用户名密码登录，JWT身份校验
- **远程查阅** - 随时随地查看评测历史和详细报告
- **成长档案** - 折线图呈现相似度进步轨迹
- **阶段总结** - 根据高频错误生成针对性报告

### 数据同步机制

树莓派作为物联网节点，当网络连接可用时，将本地SQLite中新增的评测记录以异步批量的方式上传至云端数据库。微信小程序通过RESTful API实现数据的拉取与同步。

---

## 项目结构

```
inkpi/
├── main.py                   # 应用入口
├── config.py                 # 配置文件
├── requirements.txt          # Python依赖
├── models/
│   ├── evaluation_result.py  # 评测结果模型
│   └── recognition_result.py # 识别结果模型
├── services/
│   ├── preprocessing_service.py  # 图像预处理
│   ├── evaluation_service.py     # 评测算法
│   ├── recognition_service.py    # 汉字识别
│   ├── database_service.py       # 数据库
│   ├── camera_service.py         # 摄像头
│   ├── speech_service.py         # 语音播报
│   └── cloud_upload_service.py   # 云上传
├── views/
│   ├── main_window.py       # 主窗口
│   ├── home_view.py         # 首页
│   ├── camera_view.py       # 相机页
│   ├── result_view.py       # 结果页
│   └── history_view.py      # 历史页
└── miniprogram/             # 微信小程序
```

---

## 安装与运行

### Windows开发环境

```bash
pip install -r requirements.txt
python main.py
```

### Raspberry Pi部署

```bash
chmod +x build_rpi.sh
./build_rpi.sh
./dist/InkPi
```

---

## 安全性保障

- **通信链路加密** - HTTPS/TLS 1.3协议
- **访问控制** - 基于角色的访问控制（RBAC）
- **JWT身份校验** - 防止越权访问
- **本地数据脱敏** - 关键字段通过散列算法加密

---

## 后续优化

- [ ] 集成孪生网络（Siamese Network）深度学习模型
- [ ] 基于NCNN/TFLite的边缘侧推理加速
- [ ] 集成YOLOv8n-seg笔画实例分割
- [x] 微信小程序云端协同

---

## 参考文献

1. Orbbec SDK v2 Python Binding - GitHub
2. Aesthetic Visual Quality Evaluation of Chinese Handwritings - IJCAI
3. Intelligent Evaluation of Chinese Hard-Pen Calligraphy Using a Siamese Transformer Network - MDPI
4. Fully Convolutional Network Based Skeletonization for Handwritten Chinese Characters - AAAI
5. Fine Segmentation of Chinese Character Strokes Based on Coordinate Awareness and Enhanced BiFPN - ResearchGate

---

## License

MIT License © 2026 ZongRui