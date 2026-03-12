# 🖌️ InkPi 书法评测系统

基于 Python 3.11+ + PyQt6 + OpenCV 的跨平台书法评测应用

## 功能特性

- 📷 **实时拍照评测** - 摄像头实时预览，带米字格取景框引导
- 🧠 **智能图像预处理** - 光照检测、自适应二值化、降噪锐化
- 📊 **四维评分** - 结构、笔画、平衡、韵律全方位评估
- 🎨 **毛笔字专属特征** - 提按效果、笔锋锐度、飞白检测
- 📈 **雷达图展示** - 直观展示各维度得分
- 🔊 **语音播报** - TTS 语音播报评测结果
- 📋 **历史记录** - SQLite 本地存储，支持筛选删除
- 📉 **趋势分析** - 折线图展示学习进度
- 📱 **微信小程序** - 远程查看评测历史和报告

## 技术栈

- **语言**: Python 3.11+
- **GUI**: PyQt6
- **图像处理**: OpenCV, NumPy
- **图表**: Matplotlib
- **语音**: pyttsx3
- **数据库**: SQLite3
- **云服务**: 微信云开发

---

## 📐 核心算法

### 1. 图像预处理流程

```
原始图像 → 透视校正 → 缩放(512px) → HSV米字格滤除 → 灰度化 → 自适应二值化 → 中值滤波降噪 → 拉普拉斯锐化 → 输出
```

#### 1.1 图像预检 (Fail-Fast 机制)

| 检测项 | 条件 | 说明 |
|--------|------|------|
| 光线不足 | μ < 60 | 平均亮度过低 |
| 光线过曝 | μ > 220 | 平均亮度过高 |
| 对比度不足 | σ < 15 | 灰度标准差过小 |
| 空拍检测 | ink_ratio < 0.5% | 墨迹占比过低 |
| 遮挡检测 | ink_ratio > 40% | 墨迹占比过高 |

#### 1.2 透视校正算法

基于 Canny 边缘检测 + 霍夫变换：

```
1. 灰度化 → 高斯滤波 G(σ=1.0) 抑制噪声
2. Canny 边缘检测 (阈值: 50-150)
3. 概率霍夫变换检测直线:
   H(ρ,θ) = ∑_{x,y} I(x,y) · δ(ρ - x·cosθ - y·sinθ)
   
   参数: ρ=1, θ=π/180, threshold=100, minLineLength=100
4. 计算线段交点定位四角
5. 透视变换矩阵映射到正交视角:
   [x' y' w']ᵀ = M · [x y 1]ᵀ
```

#### 1.3 HSV 米字格滤除

针对红色米字格的滤除算法：

```
1. RGB → HSV 色彩空间转换
2. 生成两个红色掩码:
   - 低频红色: H ∈ [0°, 10°], S ∈ [70, 255], V ∈ [50, 255]
   - 高频红色: H ∈ [170°, 180°], S ∈ [70, 255], V ∈ [50, 255]
   
   Mask_red = Mask_1 ∪ Mask_2
   
3. 形态学闭运算防止误删:
   Mask = Closing(Mask_red, Kernel_{3×3})
   
4. 红色区域替换为背景色
```

#### 1.4 自适应二值化

使用局部阈值处理光照不均问题：

```
T(x,y) = μ_{block}(x,y) - C

其中:
- block_size = 11 (邻域大小)
- C = 2 (常数偏移)
- μ_{block} = 高斯加权邻域均值

二值化结果:
B(x,y) = { 255, if I(x,y) > T(x,y)
         { 0,   otherwise
```

#### 1.5 中值滤波降噪

```
Y(x,y) = median{ I(x+s, y+t) | s,t ∈ [-1,1] }

使用 3×3 窗口，保留边缘的同时去除椒盐噪点
```

#### 1.6 拉普拉斯锐化

增强笔画边缘清晰度：

```
Kernel = | 0  -1   0 |
         |-1   5  -1 |
         | 0  -1   0 |

I_sharp = Convolve(I, Kernel)
```

---

### 2. 书法评测算法

#### 2.1 四维评分体系

| 维度 | 评分范围 | 评价标准 |
|------|----------|----------|
| 结构 | 60-94 | 字形匀称程度、凸包矩形度、留白分布 |
| 笔画 | 60-94 | 骨架分析、边缘复杂度、提按效果、笔锋锐度 |
| 平衡 | 60-94 | 精确重心计算、中轴线偏移量 |
| 韵律 | 60-94 | 连通性、行笔流畅度、墨色变化、飞白效果 |

**总分计算:**

$$Score_{total} = \frac{1}{4} \sum_{i=1}^{4} Score_i$$

#### 2.2 结构评分 (Structure)

**2.2.1 精确重心计算**

$$\bar{x} = \frac{1}{N} \sum_{i=1}^{N} x_i, \quad \bar{y} = \frac{1}{N} \sum_{i=1}^{N} y_i$$

其中 $N$ 为墨迹像素数，$(x_i, y_i)$ 为墨迹像素坐标。

**2.2.2 凸包矩形度**

$$R_{convex} = \frac{P_{hull}}{P_{rect}}$$

其中 $P_{hull}$ 为凸包周长，$P_{rect}$ 为最小外接矩形周长。理想值约 0.8。

**2.2.3 弹性网格留白分析**

将图像划分为 3×3 网格，计算各单元格留白率方差：

$$\sigma^2_{WS} = \frac{1}{9} \sum_{i=1}^{9} (WS_i - \overline{WS})^2$$

**2.2.4 综合结构评分**

$$Score_{struct} = 0.2 \cdot S_{rect} + 0.3 \cdot S_{WS} + 0.3 \cdot S_{proj} + 0.2 \cdot S_{ratio}$$

#### 2.3 笔画评分 (Stroke)

**2.3.1 骨架提取**

使用形态学细化算法：

```
While 图像非空:
    1. Erode(图像, 交叉核)
    2. Dilate(腐蚀结果)
    3. 减去膨胀结果得到边缘
    4. 累积边缘形成骨架
```

**2.3.2 笔画粗细变化率 (Stroke Width Variance)**

使用距离变换测量笔画宽度：

$$D(p) = \min_{q \in \partial \Omega} \|p - q\|$$

在骨架点采样，计算变异系数：

$$CV_{width} = \frac{\sigma_W}{\mu_W}$$

毛笔字理想 CV 约 0.3，体现提按效果。

**2.3.3 笔锋锐度 (Brush Tip Sharpness)**

检测骨架端点，分析端点附近形态：

$$Sharpness = \frac{1}{N} \sum_{i=1}^{N} (1 - R_{local}^i)$$

其中 $R_{local}$ 为端点附近局部墨迹占比。

**2.3.4 飞白检测 (Flying White)**

在墨迹内部检测灰度变化：

$$Density_{FW} = \min(1, \frac{\sigma^2_{interior}}{1000})$$

**2.3.5 综合笔画评分**

$$Score_{stroke} = 0.15 \cdot S_{edge} + 0.15 \cdot S_{skel} + 0.20 \cdot S_{CV} + 0.15 \cdot S_{tip} + 0.10 \cdot S_{FW} + 0.25 \cdot S_{conn}$$

#### 2.4 平衡评分 (Balance)

**重心偏移量:**

$$Offset_{center} = \sqrt{(\bar{x} - 0.5)^2 + (\bar{y} - 0.5)^2}$$

**对称性分析:**

$$S_H = 1 - \frac{1}{W} \sum_{x=0}^{W-1} |P_H(x) - P_H(W-1-x)|$$

$$S_V = 1 - \frac{1}{H} \sum_{y=0}^{H-1} |P_V(y) - P_V(H-1-y)|$$

**综合平衡评分:**

$$Score_{balance} = 0.35 \cdot S_{offset} + 0.15 \cdot S_H + 0.15 \cdot S_V + 0.175 \cdot S_X + 0.175 \cdot S_Y$$

#### 2.5 韵律评分 (Rhythm)

**2.5.1 连通分量分析**

$$Score_{comp} = \begin{cases} 1.0 & n \leq 1 \\ 0.9 & n = 2 \\ 0.75 & n \leq 4 \\ 0.6 & n \leq 6 \\ 0.4 & n > 6 \end{cases}$$

**2.5.2 墨色梯度**

使用 Sobel 算子计算梯度幅值：

$$|\nabla I| = \sqrt{(\frac{\partial I}{\partial x})^2 + (\frac{\partial I}{\partial y})^2}$$

**2.5.3 骨架流畅度**

$$Smoothness = \min(1, \frac{L_{skel}}{40 \cdot N_{branch} + 80})$$

**2.5.4 综合韵律评分**

$$Score_{rhythm} = 0.20 \cdot S_{comp}^{max} + 0.20 \cdot S_{flow} + 0.15 \cdot S_{end} + 0.15 \cdot S_{smooth} + 0.15 \cdot S_{ink} + 0.15 \cdot S_{FW}$$

---

### 3. 汉字识别

基于模板匹配的汉字识别：

```
1. 预处理后的图像与模板库对比
2. 使用 Hu 矩作为特征描述符
3. 计算相似度并返回最佳匹配

Hu 矩具有平移、旋转、缩放不变性
```

---

## 📁 项目结构

```
inkpi/
├── main.py                   # 应用入口
├── config.py                 # 配置文件
├── requirements.txt          # Python 依赖
├── build_rpi.sh             # RPi 打包脚本
├── models/
│   ├── __init__.py
│   ├── evaluation_result.py  # 评测结果模型
│   └── recognition_result.py # 识别结果模型
├── services/
│   ├── __init__.py
│   ├── preprocessing_service.py  # 图像预处理
│   ├── evaluation_service.py     # 评测算法
│   ├── recognition_service.py    # 汉字识别
│   ├── database_service.py       # 数据库
│   ├── camera_service.py         # 摄像头
│   ├── speech_service.py         # 语音播报
│   └── cloud_upload_service.py   # 云上传
├── views/
│   ├── __init__.py
│   ├── main_window.py       # 主窗口
│   ├── home_view.py         # 首页
│   ├── camera_view.py       # 相机页
│   ├── result_view.py       # 结果页
│   └── history_view.py      # 历史页
└── miniprogram/             # 微信小程序
```

---

## 🚀 安装与运行

### Windows 开发环境

```bash
# 安装依赖
pip install -r requirements.txt

# 运行应用
python main.py
```

### Raspberry Pi 部署

```bash
# 添加执行权限
chmod +x build_rpi.sh

# 执行打包
./build_rpi.sh

# 运行
./dist/InkPi
```

---

## 📱 微信小程序

### 功能

- 🔐 **用户名密码登录** - 未注册自动注册
- 📋 **历史记录** - 查看评测历史列表
- 📊 **评测详情** - 四维评分、雷达图、反馈
- 👤 **个人中心** - 用户信息、设备绑定

### 目录结构

```
miniprogram/
├── pages/
│   ├── index/             # 登录页
│   ├── history/           # 历史记录页
│   ├── detail/            # 评测详情页
│   └── profile/           # 个人中心页
├── cloudfunctions/        # 云函数
│   ├── login/             # 登录/注册
│   ├── getHistory/        # 获取历史
│   ├── getDetail/         # 获取详情
│   ├── getStats/          # 获取统计
│   └── uploadResult/      # 上传结果
└── README.md
```

### 快速开始

1. 用微信开发者工具打开 `miniprogram` 目录
2. 配置云开发环境
3. 创建数据库集合：`users`, `evaluations`
4. 部署云函数

详细说明: [miniprogram/README.md](miniprogram/README.md)

---

## 🔗 树莓派与小程序联动

```python
from services.cloud_upload_service import CloudUploadService

service = CloudUploadService(env_id="your-env-id")

service.upload_evaluation_result(
    openid="user_openid",
    total_score=85,
    detail_scores={"structure": 83, "stroke": 78, "balance": 91, "rhythm": 88},
    feedback="太棒了！您的书法水平很高！",
    image_path="/path/to/image.jpg",
    title="九成宫醴泉铭 · 每日评测"
)
```

---

## ⚙️ 配置参数

| 类别 | 参数 | 默认值 | 说明 |
|------|------|--------|------|
| 图像 | target_size | 512 | 缩放目标尺寸 |
| 图像 | adaptive_block_size | 11 | 二值化邻域大小 |
| 图像 | adaptive_c | 2 | 二值化常数偏移 |
| 预检 | min_brightness | 60 | 最小亮度 |
| 预检 | max_brightness | 220 | 最大亮度 |
| 预检 | min_ink_ratio | 0.005 | 最小墨迹占比 |
| 预检 | max_ink_ratio | 0.4 | 最大墨迹占比 |
| 评分 | score_range | [60, 94] | 评分范围 |
| 评分 | excellent_threshold | 80 | 优秀阈值 |

---

## 📊 数据模型

### EvaluationResult

```python
class EvaluationResult:
    total_score: int           # 总分 (0-100)
    detail_scores: Dict[str, int]  # 四维评分
    feedback: str              # 文字反馈
    image_path: str            # 原始图片路径
    processed_image_path: str  # 预处理后图片
    character_name: str        # 识别的汉字
    timestamp: datetime        # 评测时间
```

---

## 🔧 跨平台支持

| 平台 | 摄像头后端 | 语音引擎 |
|------|------------|----------|
| Windows | DirectShow | SAPI5 |
| Linux/RPi | v4l2 | espeak-ng |

---

## 📋 后续优化

- [ ] 集成真实 AI 模型 (TFLite)
- [ ] 添加字符分割功能
- [ ] 支持多字评测
- [x] 添加用户系统（微信小程序）

---

## 📄 License

MIT License © 2026 ZongRui