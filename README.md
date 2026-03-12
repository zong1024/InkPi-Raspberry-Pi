# 🖌️ InkPi 书法评测系统

基于 Python 3.11+ + PyQt6 + OpenCV 的跨平台书法评测应用

## 功能特性

- 📷 **实时拍照评测** - 摄像头实时预览，带米字格取景框引导
- 🧠 **智能图像预处理** - 光照检测、自适应二值化、降噪锐化
- 📊 **四维评分** - 结构、笔画、平衡、韵律全方位评估
- 📈 **雷达图展示** - 直观展示各维度得分
- 🔊 **语音播报** - TTS 语音播报评测结果
- 📋 **历史记录** - SQLite 本地存储，支持筛选删除
- 📉 **趋势分析** - 折线图展示学习进度

## 技术栈

- **语言**: Python 3.11+
- **GUI**: PyQt6
- **图像处理**: OpenCV, NumPy
- **图表**: Matplotlib
- **语音**: pyttsx3
- **数据库**: SQLite3

## 项目结构

```
inkpi/
├── main.py                   # 应用入口
├── config.py                 # 配置文件
├── requirements.txt          # Python 依赖
├── build_rpi.sh             # RPi 打包脚本
├── models/
│   ├── __init__.py
│   └── evaluation_result.py  # 数据模型
├── services/
│   ├── __init__.py
│   ├── preprocessing_service.py  # 图像预处理
│   ├── evaluation_service.py     # 评测算法
│   ├── database_service.py       # 数据库
│   ├── camera_service.py         # 摄像头
│   └── speech_service.py         # 语音播报
└── views/
    ├── __init__.py
    ├── main_window.py       # 主窗口
    ├── home_view.py         # 首页
    ├── camera_view.py       # 相机页
    ├── result_view.py       # 结果页
    └── history_view.py      # 历史页
```

## 安装

### Windows 开发环境

```bash
# 安装依赖
pip install -r requirements.txt

# 运行应用
python main.py
```

### Raspberry Pi 部署

1. 将项目复制到 Raspberry Pi
2. 运行打包脚本:

```bash
chmod +x build_rpi.sh
./build_rpi.sh
```

3. 运行可执行文件:

```bash
./dist/InkPi
```

## 核心算法

### 图像预处理流程

```
原始图像 → 缩放(512px) → 灰度化 → 自适应二值化 → 中值滤波降噪 → 拉普拉斯锐化 → 输出
```

### 图像预检 (Fail-Fast)

- **光照检测**: 亮度 <60 或 >220 拦截
- **空拍检测**: 墨迹占比 <0.5% 或 >40% 拦截

### 四维评分

| 维度 | 评分范围 | 评价标准 |
|------|----------|----------|
| 结构 | 60-94 | 字形匀称程度、留白分布 |
| 笔画 | 60-94 | 起收笔到位程度、边缘平滑度 |
| 平衡 | 60-94 | 重心稳定性、中轴线偏移量 |
| 韵律 | 60-94 | 行笔流畅度、连贯性 |

## 配置

配置文件 `config.py` 包含所有可调参数：

- 图像处理参数（缩放尺寸、二值化参数等）
- 评测参数（评分范围、阈值）
- 摄像头参数（分辨率、帧率）
- 语音参数（语速、音量）

## 跨平台支持

应用自动检测运行平台并适配：

- **Windows**: 使用 DirectShow 摄像头后端，SAPI5 语音
- **Linux/RPi**: 使用 v4l2 摄像头后端，espeak-ng 语音

## 📱 微信小程序

项目包含微信小程序端，支持查看评测历史和详细报告。

### 小程序功能

- 🔐 **用户名密码登录** - 未注册自动注册
- 📋 **历史记录** - 查看评测历史列表
- 📊 **评测详情** - 四维评分、雷达图、反馈
- 👤 **个人中心** - 用户信息、设备绑定

### 小程序目录

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
└── README.md              # 小程序说明文档
```

### 快速开始

1. 用微信开发者工具打开 `miniprogram` 目录
2. 配置云开发环境
3. 创建数据库集合：`users`, `evaluations`
4. 部署云函数

详细说明请查看 [miniprogram/README.md](miniprogram/README.md)

## 🔗 树莓派与小程序联动

树莓派评测完成后，可通过云上传服务同步到小程序：

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

## 后续优化

- [ ] 集成真实 AI 模型 (TFLite)
- [ ] 添加字符分割功能
- [ ] 支持多字评测
- [x] 添加用户系统（微信小程序）

## License

MIT License
