"""
InkPi 书法评测系统 - 配置文件
跨平台兼容配置
"""
import platform
from pathlib import Path

# ============ 平台检测 ============
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
IS_RASPBERRY_PI = False

if IS_LINUX:
    try:
        with open("/proc/device-tree/model", "r") as f:
            IS_RASPBERRY_PI = "Raspberry Pi" in f.read()
    except:
        pass

# ============ 路径配置 ============
# 使用 pathlib 确保跨平台兼容
APP_NAME = "InkPi"
DATA_DIR = Path.home() / f".{APP_NAME.lower()}" / "data"
IMAGES_DIR = DATA_DIR / "images"
PROCESSED_DIR = DATA_DIR / "processed"
DB_PATH = DATA_DIR / "inkpi.db"

# 确保目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# ============ 图像处理配置 ============
IMAGE_CONFIG = {
    "target_size": 512,           # 缩放目标尺寸
    "adaptive_block_size": 11,    # 自适应二值化块大小
    "adaptive_c": 2,              # 自适应二值化常数
    "median_blur_size": 3,        # 中值滤波窗口大小
    "preview_width": 640,         # 预览分辨率宽度
    "preview_height": 480,        # 预览分辨率高度
    "capture_width": 1920,        # 拍摄分辨率宽度
    "capture_height": 1080,       # 拍摄分辨率高度
}

# ============ 图像预检阈值（针对毛笔字优化） ============
PRECHECK_CONFIG = {
    "min_brightness": 50,         # 最低平均亮度（放宽）
    "max_brightness": 230,        # 最高平均亮度（放宽）
    "min_contrast_std": 8,        # 最低对比度（标准差）
    "min_ink_ratio": 0.01,        # 最低墨迹占比 (1%)
    "max_ink_ratio": 0.55,        # 最高墨迹占比 (55%) - 毛笔字笔画更粗
}

# ============ 评测配置 ============
EVALUATION_CONFIG = {
    "score_range": (60, 94),      # 各维度评分范围
    "dimensions": ["结构", "笔画", "平衡", "韵律"],
    "excellent_threshold": 80,    # 优秀阈值
    "good_threshold": 60,         # 良好阈值
}

# ============ 摄像头配置 ============
if IS_WINDOWS:
    CAMERA_BACKEND = 700  # cv2.CAP_DSHOW (DirectShow)
elif IS_LINUX:
    CAMERA_BACKEND = 200  # cv2.CAP_V4L2
else:
    CAMERA_BACKEND = 0    # 默认

CAMERA_CONFIG = {
    "backend": CAMERA_BACKEND,
    "camera_index": 0,            # 默认摄像头索引
    "fps": 30,                    # 预览帧率
}

# ============ 语音配置 ============
TTS_CONFIG = {
    "rate": 150,                  # 语速 (words per minute)
    "volume": 0.9,                # 音量 (0.0 - 1.0)
    # Windows: 使用 SAPI5 默认中文语音
    # Linux: 使用 espeak-ng
}

# ============ 数据库配置 ============
DB_CONFIG = {
    "table_name": "evaluations",
    "max_records": 1000,          # 最大记录数
}

# ============ UI 配置 ============
UI_CONFIG = {
    "window_title": f"{APP_NAME} 书法评测系统",
    "window_width": 480,
    "window_height": 320,
    "theme": "light",             # light / dark
    "radar_chart_size": 200,      # 雷达图尺寸 (适配3.5寸)
}

# ============ 反馈文案 ============
FEEDBACK_TEMPLATES = {
    "excellent": [
        "优秀！字形端正，笔画流畅，继续保持！",
        "非常棒！书写规范，结构匀称，堪称佳作！",
        "太棒了！您的书法水平很高，请继续保持！",
    ],
    "good": {
        "结构": "注意字形匀称，留白要适当。",
        "笔画": "起笔收笔要更到位，笔画边缘要更平滑。",
        "平衡": "注意重心稳定，保持中轴线不偏移。",
        "韵律": "行笔要更流畅连贯，注意节奏感。",
    },
    "needs_work": [
        "需要加强练习，注意控笔和字形结构。",
        "继续努力！多观察字帖，注意笔画顺序。",
        "建议从基本笔画开始练习，逐步提高。",
    ],
}

# ============ LED 灯带配置 ============
LED_CONFIG = {
    "enabled": True,              # 是否启用 LED 功能
    "num_leds": 8,                # LED 灯珠数量
    "spi_bus": 0,                 # SPI 总线号
    "spi_device": 0,              # SPI 设备号
    "brightness": 0.3,            # 亮度 (0.0 - 1.0)
    "gpio_pin": 10,               # SPI0 MOSI (GPIO10, Pin 19)
}

# 灯光效果配置
LED_EFFECTS = {
    "excellent": {
        "color": "green",
        "effect": "breathing",    # 呼吸灯
    },
    "good": {
        "color": "yellow",
        "effect": "steady",       # 稳定光
    },
    "needs_work": {
        "color": "red",
        "effect": "blinking",     # 闪烁
        "interval": 0.3,
    },
}

# ============ 微信云开发配置 ============
CLOUD_CONFIG = {
    "enabled": True,              # 是否启用云同步
    "env_id": "inkpi-cloud",      # 云开发环境ID（需要替换为实际值）
    "openid": "raspberrypi_device",  # 设备标识（用于区分数据来源）
    "collection": "evaluations",  # 数据库集合名称
}

# ============ 日志配置 ============
LOG_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "log_file": DATA_DIR / "inkpi.log",
}
