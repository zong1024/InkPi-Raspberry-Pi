"""
InkPi 配置设置

参考 DeepVision 的 Configuration 类设计
"""
from pathlib import Path
import os

# =========================
# 路径配置
# =========================
PROJECT_ROOT = Path(__file__).resolve().parent.parent

PATHS = {
    "project_root": PROJECT_ROOT,
    "models_dir": PROJECT_ROOT / "models",
    "data_dir": PROJECT_ROOT / "data",
    "templates_dir": PROJECT_ROOT / "models" / "templates",
    "logs_dir": PROJECT_ROOT / "logs",
    "cache_dir": PROJECT_ROOT / ".inkpi",
    "screenshots_dir": PROJECT_ROOT / "screenshots",
}

# 确保必要的目录存在
for key, path in PATHS.items():
    if key.endswith("_dir"):
        path.mkdir(parents=True, exist_ok=True)


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
    "backend": "picamera",  # picamera, opencv, ffmpeg
    
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
    # 评分维度
    "dimensions": ["结构", "笔画", "平衡", "韵律"],
    
    # 评分范围
    "score_range": (0, 100),
    
    # 等级阈值
    "excellent_threshold": 85,
    "good_threshold": 70,
    "pass_threshold": 60,
    
    # 反馈模板
    "feedback_templates": {
        "excellent": [
            "优秀！书法功底扎实，笔画流畅有力！",
            "太棒了！字形端正，结构匀称！",
            "完美！体现了深厚的书法功底！",
        ],
        "good": {
            "结构": "注意字形的匀称和留白分布",
            "笔画": "加强笔画的连贯性和粗细变化",
            "平衡": "注意字的重心位置",
            "韵律": "提高行笔的流畅度",
        },
        "needs_work": [
            "继续练习，建议多临摹字帖",
            "加油！注意笔法和结构",
            "坚持练习，会有进步的！",
        ],
    },
    
    # 图像预处理
    "preprocessing": {
        "target_size": 224,
        "blur_kernel": 3,
        "threshold_method": "otsu",  # otsu, adaptive, fixed
    },
}


# =========================
# 模型配置
# =========================
MODEL_CONFIG = {
    # 模型文件
    "model_path": PATHS["models_dir"] / "siamese_calligraphy_best.pth",
    "onnx_path": PATHS["models_dir"] / "siamese_calligraphy.onnx",
    "tflite_path": PATHS["models_dir"] / "siamese_calligraphy.tflite",
    
    # 模型参数
    "embedding_dim": 128,
    "image_size": 224,
    
    # 推理配置
    "inference": {
        "engine": "auto",  # auto, torch, onnx, tflite
        "device": "cpu",   # cpu, cuda
        "num_threads": 4,  # TFLite 线程数
    },
    
    # 相似度阈值
    "similarity_threshold": {
        "excellent": 0.9,
        "good": 0.7,
        "medium": 0.5,
        "poor": 0.3,
    },
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
    }
    
    keys = key.split(".")
    value = configs.get(keys[0], {})
    
    for k in keys[1:]:
        if isinstance(value, dict):
            value = value.get(k, default)
        else:
            return default
    
    return value if value is not None else default