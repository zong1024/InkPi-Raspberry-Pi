"""
InkPi 配置模块

统一导出所有配置，兼容 PyInstaller 打包
"""
from config.settings import (
    # 基础配置
    APP_CONFIG,
    CAMERA_CONFIG,
    EVALUATION_CONFIG,
    OCR_CONFIG,
    QUALITY_SCORER_CONFIG,
    MODEL_CONFIG,
    PATHS,
    HARDWARE_CONFIG,
    CLOUD_CONFIG,
    DEV_CONFIG,
    DESKTOP_SIM_CONFIG,
    DESKTOP_SIM_MODE,
    IS_RASPBERRY_PI,
    # 兼容配置（main.py 需要的）
    UI_CONFIG,
    LOG_CONFIG,
    DATA_DIR,
    MODELS_DIR,
    IMAGES_DIR,
    PROCESSED_DIR,
    PRECHECK_CONFIG,
    DB_PATH,
    DB_CONFIG,
    IMAGE_CONFIG,
    FEEDBACK_TEMPLATES,
    LED_CONFIG,
    TTS_CONFIG,
    # 工具函数
    get_config,
)

__all__ = [
    # 基础配置
    "APP_CONFIG",
    "CAMERA_CONFIG",
    "EVALUATION_CONFIG",
    "OCR_CONFIG",
    "QUALITY_SCORER_CONFIG",
    "MODEL_CONFIG",
    "PATHS",
    "HARDWARE_CONFIG",
    "CLOUD_CONFIG",
    "DEV_CONFIG",
    "DESKTOP_SIM_CONFIG",
    "DESKTOP_SIM_MODE",
    "IS_RASPBERRY_PI",
    # 兼容配置
    "UI_CONFIG",
    "LOG_CONFIG",
    "DATA_DIR",
    "MODELS_DIR",
    "IMAGES_DIR",
    "PROCESSED_DIR",
    "PRECHECK_CONFIG",
    "DB_PATH",
    "DB_CONFIG",
    "IMAGE_CONFIG",
    "FEEDBACK_TEMPLATES",
    "LED_CONFIG",
    "TTS_CONFIG",
    # 工具函数
    "get_config",
]
