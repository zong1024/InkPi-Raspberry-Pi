"""
InkPi 配置设置

参考 DeepVision 的 Configuration 类设计
"""
from pathlib import Path
import os


def _detect_raspberry_pi() -> bool:
    """检测当前是否运行在树莓派环境。"""
    model_path = Path("/proc/device-tree/model")
    try:
        return model_path.exists() and "Raspberry Pi" in model_path.read_text(
            encoding="utf-8",
            errors="ignore",
        )
    except OSError:
        return False

# =========================
# 路径配置
# =========================
PROJECT_ROOT = Path(__file__).resolve().parent.parent

PATHS = {
    "project_root": PROJECT_ROOT,
    "models_dir": PROJECT_ROOT / "models",
    "data_dir": PROJECT_ROOT / "data",
    "images_dir": PROJECT_ROOT / "data" / "images",
    "processed_dir": PROJECT_ROOT / "data" / "processed",
    "logs_dir": PROJECT_ROOT / "logs",
    "cache_dir": PROJECT_ROOT / ".inkpi",
    "screenshots_dir": PROJECT_ROOT / "screenshots",
}

# 确保必要的目录存在
for key, path in PATHS.items():
    if key.endswith("_dir"):
        path.mkdir(parents=True, exist_ok=True)


IS_RASPBERRY_PI = _detect_raspberry_pi()
DESKTOP_SIM_MODE = os.environ.get("INKPI_DESKTOP_SIM", "false").lower() in {"1", "true", "yes", "on"}


# =========================
# 应用配置
# =========================
APP_CONFIG = {
    "app_name": "InkPi",
    "version": "2.0.0",
    "debug": False,
    "log_level": "INFO",
    
    # 窗口配置
    "window": {
        "width": 800,
        "height": 480,
        "fullscreen": True,  # 树莓派默认全屏
        "title": "InkPi 书法评测系统",
    },
    
    # 服务端配置
    "server": {
        "host": "0.0.0.0",
        "port": 5000,
    },
}


# =========================
# 相机配置
# =========================
CAMERA_CONFIG = {
    # 相机设备
    "device_index": 0,
    "camera_index": 0,      # 兼容旧服务层命名
    "backend": "auto",      # auto, picamera, opencv, ffmpeg
    
    # 预览分辨率
    "preview_width": 640,
    "preview_height": 480,
    
    # 捕获分辨率
    "capture_width": 1280,
    "capture_height": 960,
    
    # 帧率
    "fps": 30,
    
    # 预览配置
    "preview_duration": 3,  # 预览时间（秒）
    
    # 自动捕获
    "auto_capture": False,
    "capture_delay": 2,  # 自动捕获延迟
    
    # 图像增强
    "brightness": 50,
    "contrast": 50,
    "saturation": 0,
    "sharpness": 50,
}


# =========================
# 评测配置
# =========================
EVALUATION_CONFIG = {
    # 评分范围
    "score_range": (0, 100),

    # 等级阈值
    "quality_thresholds": {
        "good": 85,
        "medium": 70,
    },

    "quality_labels": {
        "good": "好",
        "medium": "中",
        "bad": "坏",
    },

    # 反馈模板
    "feedback_templates": {
        "good": [
            "整体状态很稳，已经接近比赛演示级效果。",
            "这张作品完成度很高，字形和气息都比较成熟。",
            "当前表现优秀，可以把它作为展示用样例。",
        ],
        "medium": [
            "整体已经成形，但还有进一步打磨空间。",
            "识别和评分都比较稳定，建议继续提升细节控制。",
            "这张作品基础不错，再收一收笔势会更稳。",
        ],
        "bad": [
            "这张作品波动比较明显，建议重拍或重新书写后再试。",
            "当前作品整体状态偏弱，建议先调整字形和用笔。",
            "这张图还能识别，但评测结果提示基础质量偏低。",
        ],
    },

    # 图像预处理
    "preprocessing": {
        "target_size": 224,
        "blur_kernel": 3,
        "threshold_method": "otsu",  # otsu, adaptive, fixed
    },
}

if DESKTOP_SIM_MODE:
    APP_CONFIG["window"]["width"] = 480
    APP_CONFIG["window"]["height"] = 320
    APP_CONFIG["window"]["fullscreen"] = False
    APP_CONFIG["debug"] = True


# =========================
# OCR 配置
# =========================
OCR_CONFIG = {
    "engine": "paddleocr",
    "language": "ch",
    "device": os.environ.get("INKPI_LOCAL_OCR_DEVICE", "cpu"),
    "min_confidence": float(os.environ.get("INKPI_LOCAL_OCR_MIN_CONFIDENCE", "0.32")),
    "warmup": os.environ.get("INKPI_LOCAL_OCR_WARMUP", "true").lower() == "true",
}


# =========================
# 质量评分 ONNX 配置
# =========================
QUALITY_SCORER_CONFIG = {
    "onnx_path": PATHS["models_dir"] / "quality_scorer.onnx",
    "input_size": 32,
    "num_threads": 2,
    "score_scale": 100.0,
    "labels": ["bad", "medium", "good"],
    "default_level": "medium",
    "feedback_by_level": {
        "good": "自动识别显示这张作品整体完成度很高，适合直接进入展示或归档。",
        "medium": "自动识别显示这张作品已经比较稳定，但仍有继续打磨空间。",
        "bad": "自动识别显示这张作品质量偏弱，建议重新书写或重新拍摄后再试。",
    },
}


# =========================
# 模型资产配置
# =========================
MODEL_CONFIG = {
    "ocr_engine": OCR_CONFIG["engine"],
    "quality_scorer_path": QUALITY_SCORER_CONFIG["onnx_path"],
    "quality_labels": QUALITY_SCORER_CONFIG["labels"],
    "input_size": QUALITY_SCORER_CONFIG["input_size"],
}


# =========================
# 硬件配置 (树莓派)
# =========================
HARDWARE_CONFIG = {
    # LED 指示灯
    "led": {
        "enabled": True,
        "gpio_pin": 18,
        "blink_interval": 0.5,
    },
    
    # 语音播报
    "speech": {
        "enabled": True,
        "engine": "espeak",  # espeak, pyttsx3
        "language": "zh",
        "rate": 150,
    },
    
    # 按钮
    "button": {
        "enabled": True,
        "gpio_pin": 17,
        "debounce_ms": 200,
    },
}


# =========================
# 云服务配置
# =========================
CLOUD_CONFIG = {
    "enabled": True,
    
    # 微信云开发
    "wechat": {
        "env_id": "your-env-id",
        "functions": {
            "upload_result": "uploadResult",
            "get_history": "getHistory",
            "get_stats": "getStats",
        },
    },
    
    # 离线模式
    "offline_mode": True,  # 离线时仍可本地评测
}


# =========================
# 开发配置
# =========================
DEV_CONFIG = {
    # 测试模式
    "test_mode": os.environ.get("INKPI_TEST_MODE", "false").lower() == "true",
    
    # 性能分析
    "profiling": False,
    
    # 调试选项
    "debug": {
        "show_camera_preview": True,
        "save_debug_images": False,
        "verbose_logging": False,
    },
}

DESKTOP_SIM_CONFIG = {
    "enabled": DESKTOP_SIM_MODE,
    "default_character": os.environ.get("INKPI_SIM_DEFAULT_CHAR", "永"),
    "camera_source": os.environ.get("INKPI_SIM_CAMERA_SOURCE", "").strip(),
    "camera_fps": int(os.environ.get("INKPI_SIM_CAMERA_FPS", "15")),
}


# =========================
# UI 配置（兼容 PyInstaller）
# =========================
UI_CONFIG = {
    "window_title": f"{APP_CONFIG['app_name']} 书法评测系统",
    "window_width": APP_CONFIG["window"]["width"],
    "window_height": APP_CONFIG["window"]["height"],
    "theme": "light",
    "radar_chart_size": 200,
}

# =========================
# 日志配置
# =========================
LOG_CONFIG = {
    "level": APP_CONFIG["log_level"],
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "log_file": PATHS["logs_dir"] / "inkpi.log",
}

# =========================
# 数据目录（简化版）
# =========================
DATA_DIR = PATHS["data_dir"]
MODELS_DIR = PATHS["models_dir"]
IMAGES_DIR = PATHS["images_dir"]
PROCESSED_DIR = PATHS["processed_dir"]

# =========================
# 图像配置
# =========================
IMAGE_CONFIG = {
    "target_size": 512,
    "adaptive_block_size": 11,
    "adaptive_c": 2,
    "median_blur_size": 3,
    "preview_width": CAMERA_CONFIG["preview_width"],
    "preview_height": CAMERA_CONFIG["preview_height"],
    "capture_width": CAMERA_CONFIG["capture_width"],
    "capture_height": CAMERA_CONFIG["capture_height"],
}

# =========================
# 图像预检配置
# =========================
PRECHECK_CONFIG = {
    "min_brightness": 40,
    "max_brightness": 245,
    "min_contrast_std": 12,
    "min_ink_ratio": 0.01,
    "max_ink_ratio": 0.60,
    "min_component_area_ratio": 0.00008,
    "max_meaningful_components": 60,
    "min_edge_to_ink_ratio": 0.08,
    "max_blob_solidity": 0.90,
    "max_blob_fill_ratio": 0.58,
    "max_blob_area_ratio": 0.18,
}

# =========================
# 反馈模板
# =========================
FEEDBACK_TEMPLATES = EVALUATION_CONFIG["feedback_templates"]

# =========================
# 数据库配置
# =========================
DB_PATH = DATA_DIR / ("inkpi-sim.db" if DESKTOP_SIM_MODE else "inkpi.db")
DB_CONFIG = {
    "table_name": "evaluation_records",
    "max_records": 1000,
}

# =========================
# LED 配置
# =========================
LED_CONFIG = {
    "enabled": HARDWARE_CONFIG["led"]["enabled"],
    "num_leds": 8,
    "spi_bus": 0,
    "spi_device": 0,
    "brightness": 0.3,
    "gpio_pin": 10,
}

# =========================
# TTS 语音配置
# =========================
TTS_CONFIG = {
    "rate": HARDWARE_CONFIG["speech"]["rate"],
    "volume": 0.9,
}


def get_config(key: str, default=None):
    """
    获取配置值
    
    Args:
        key: 配置键，支持点分隔符 (如 "window.width")
        default: 默认值
        
    Returns:
        配置值
    """
    configs = {
        "app": APP_CONFIG,
        "camera": CAMERA_CONFIG,
        "evaluation": EVALUATION_CONFIG,
        "model": MODEL_CONFIG,
        "hardware": HARDWARE_CONFIG,
        "cloud": CLOUD_CONFIG,
        "dev": DEV_CONFIG,
        "paths": PATHS,
        "ui": UI_CONFIG,
        "log": LOG_CONFIG,
        "image": IMAGE_CONFIG,
        "precheck": PRECHECK_CONFIG,
        "db": DB_CONFIG,
        "led": LED_CONFIG,
        "tts": TTS_CONFIG,
    }
    
    keys = key.split(".")
    value = configs.get(keys[0], {})
    
    for k in keys[1:]:
        if isinstance(value, dict):
            value = value.get(k, default)
        else:
            return default
    
    return value if value is not None else default
