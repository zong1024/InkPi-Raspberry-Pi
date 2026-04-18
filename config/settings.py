"""Runtime settings for InkPi."""

from __future__ import annotations

import os
from pathlib import Path


def _detect_raspberry_pi() -> bool:
    """Return whether the current machine is a Raspberry Pi."""
    model_path = Path("/proc/device-tree/model")
    try:
        return model_path.exists() and "Raspberry Pi" in model_path.read_text(
            encoding="utf-8",
            errors="ignore",
        )
    except OSError:
        return False


def _env_flag(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_choice(name: str, default: str, allowed: tuple[str, ...]) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    normalized = value.strip().lower()
    if normalized in allowed:
        return normalized
    return default


PROJECT_ROOT = Path(__file__).resolve().parent.parent

PATHS = {
    "project_root": PROJECT_ROOT,
    "models_dir": PROJECT_ROOT / "models",
    "quality_models_dir": PROJECT_ROOT / "models",
    "data_dir": PROJECT_ROOT / "data",
    "quality_manifests_dir": PROJECT_ROOT / "data" / "quality_manifests",
    "images_dir": PROJECT_ROOT / "data" / "images",
    "processed_dir": PROJECT_ROOT / "data" / "processed",
    "logs_dir": PROJECT_ROOT / "logs",
    "cache_dir": PROJECT_ROOT / ".inkpi",
    "screenshots_dir": PROJECT_ROOT / "screenshots",
}

for key, path in PATHS.items():
    if key.endswith("_dir"):
        path.mkdir(parents=True, exist_ok=True)


IS_RASPBERRY_PI = _detect_raspberry_pi()


APP_CONFIG = {
    "app_name": "InkPi",
    "version": "2.0.0",
    "debug": _env_flag("INKPI_DEBUG", False),
    "log_level": os.environ.get("INKPI_LOG_LEVEL", "INFO"),
    "window": {
        "width": _env_int("INKPI_WINDOW_WIDTH", 800),
        "height": _env_int("INKPI_WINDOW_HEIGHT", 480),
        "fullscreen": _env_flag("INKPI_FULLSCREEN", IS_RASPBERRY_PI),
        "title": "InkPi 书法评测系统",
    },
    "server": {
        "host": os.environ.get("INKPI_WEB_HOST", "0.0.0.0"),
        "port": _env_int("INKPI_WEB_PORT", 5000),
    },
}


CAMERA_CONFIG = {
    "device_index": 0,
    "camera_index": 0,
    "backend": os.environ.get("INKPI_CAMERA_BACKEND", "auto"),
    "preview_width": 640,
    "preview_height": 480,
    "capture_width": 1280,
    "capture_height": 960,
    "fps": _env_int("INKPI_CAMERA_FPS", 30),
    "preview_duration": 3,
    "auto_capture": False,
    "capture_delay": 2,
    "brightness": 50,
    "contrast": 50,
    "saturation": 0,
    "sharpness": 50,
}


EVALUATION_CONFIG = {
    "score_range": (0, 100),
    "quality_thresholds": {
        "good": 85,
        "medium": 70,
    },
    "quality_labels": {
        "good": "好",
        "medium": "中",
        "bad": "差",
    },
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
            "这张图还能识别到，但评测结果提示基础质量偏低。",
        ],
    },
    "preprocessing": {
        "target_size": 224,
        "blur_kernel": 3,
        "threshold_method": "otsu",
    },
}


OCR_CONFIG = {
    "engine": "paddleocr",
    "language": "ch",
    "device": os.environ.get("INKPI_LOCAL_OCR_DEVICE", "cpu"),
    "min_confidence": float(os.environ.get("INKPI_LOCAL_OCR_MIN_CONFIDENCE", "0.32")),
    "warmup": _env_flag("INKPI_LOCAL_OCR_WARMUP", True),
}


SCRIPT_CONFIG = {
    "supported": ("regular", "running"),
    "labels": {
        "regular": "楷书",
        "running": "行书",
    },
    "unsupported_labels": ["隶书", "草书", "篆书", "多字作品"],
}
SCRIPT_CONFIG["default"] = _env_choice("INKPI_DEFAULT_SCRIPT", "regular", SCRIPT_CONFIG["supported"])


def _quality_script_paths(script: str) -> dict[str, Path | str]:
    return {
        "script": script,
        "label": SCRIPT_CONFIG["labels"][script],
        "artifact_dir": PATHS["quality_models_dir"],
        "onnx_path": PATHS["quality_models_dir"] / f"quality_scorer_{script}.onnx",
        "metrics_path": PATHS["quality_models_dir"] / f"quality_scorer_{script}.metrics.json",
    }


QUALITY_SCORER_CONFIG = {
    "artifact_root": PATHS["quality_models_dir"],
    "manifest_root": PATHS["quality_manifests_dir"],
    "input_size": 32,
    "num_threads": 2,
    "score_scale": 100.0,
    "labels": ["bad", "medium", "good"],
    "default_level": "medium",
    "default_script": SCRIPT_CONFIG["default"],
    "scripts": {
        "regular": _quality_script_paths("regular"),
        "running": _quality_script_paths("running"),
    },
    # Keep legacy flat-file aliases until runtime fully switches to script-scoped loading.
    "onnx_path": PATHS["models_dir"] / "quality_scorer.onnx",
    "metrics_path": PATHS["models_dir"] / "quality_scorer.metrics.json",
    "legacy_onnx_path": PATHS["models_dir"] / "quality_scorer.onnx",
    "legacy_metrics_path": PATHS["models_dir"] / "quality_scorer.metrics.json",
    "default_script_onnx_path": (PATHS["quality_models_dir"] / f"quality_scorer_{SCRIPT_CONFIG['default']}.onnx"),
    "default_script_metrics_path": (PATHS["quality_models_dir"] / f"quality_scorer_{SCRIPT_CONFIG['default']}.metrics.json"),
    "feedback_by_level": {
        "good": "自动识别显示这张作品整体完成度很高，适合直接进入展示或归档。",
        "medium": "自动识别显示这张作品已经比较稳定，但仍有继续打磨空间。",
        "bad": "自动识别显示这张作品质量偏弱，建议重新书写或重新拍摄后再试。",
    },
}


MODEL_CONFIG = {
    "ocr_engine": OCR_CONFIG["engine"],
    "quality_scorer_path": QUALITY_SCORER_CONFIG["onnx_path"],
    "quality_default_script_path": QUALITY_SCORER_CONFIG["default_script_onnx_path"],
    "quality_default_script": QUALITY_SCORER_CONFIG["default_script"],
    "quality_scorer_paths": {
        script: config["onnx_path"] for script, config in QUALITY_SCORER_CONFIG["scripts"].items()
    },
    "quality_scorer_metrics_paths": {
        script: config["metrics_path"] for script, config in QUALITY_SCORER_CONFIG["scripts"].items()
    },
    "quality_labels": QUALITY_SCORER_CONFIG["labels"],
    "input_size": QUALITY_SCORER_CONFIG["input_size"],
    "supported_scripts": list(SCRIPT_CONFIG["supported"]),
}


HARDWARE_CONFIG = {
    "led": {
        "enabled": True,
        "gpio_pin": 18,
        "blink_interval": 0.5,
    },
    "speech": {
        "enabled": True,
        "engine": "espeak",
        "language": "zh",
        "rate": 150,
    },
    "button": {
        "enabled": True,
        "gpio_pin": 17,
        "debounce_ms": 200,
    },
}


CLOUD_CONFIG = {
    "enabled": True,
    "wechat": {
        "env_id": "your-env-id",
        "functions": {
            "upload_result": "uploadResult",
            "get_history": "getHistory",
            "get_stats": "getStats",
        },
    },
    "offline_mode": True,
}


DEV_CONFIG = {
    "test_mode": _env_flag("INKPI_TEST_MODE", False),
    "profiling": False,
    "debug": {
        "show_camera_preview": True,
        "save_debug_images": False,
        "verbose_logging": False,
    },
}


UI_CONFIG = {
    "window_title": f"{APP_CONFIG['app_name']} 书法评测系统",
    "window_width": APP_CONFIG["window"]["width"],
    "window_height": APP_CONFIG["window"]["height"],
    "theme": "light",
    "radar_chart_size": 200,
}


LOG_CONFIG = {
    "level": APP_CONFIG["log_level"],
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "log_file": PATHS["logs_dir"] / "inkpi.log",
}


DATA_DIR = PATHS["data_dir"]
MODELS_DIR = PATHS["models_dir"]
IMAGES_DIR = PATHS["images_dir"]
PROCESSED_DIR = PATHS["processed_dir"]


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


FEEDBACK_TEMPLATES = EVALUATION_CONFIG["feedback_templates"]


DB_PATH = DATA_DIR / "inkpi.db"
DB_CONFIG = {
    "table_name": "evaluation_records",
    "max_records": 1000,
}


LED_CONFIG = {
    "enabled": HARDWARE_CONFIG["led"]["enabled"],
    "num_leds": 8,
    "spi_bus": 0,
    "spi_device": 0,
    "brightness": 0.3,
    "gpio_pin": 10,
}


TTS_CONFIG = {
    "rate": HARDWARE_CONFIG["speech"]["rate"],
    "volume": 0.9,
}


def get_config(key: str, default=None):
    """Get a config value using dot-separated access."""
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

    for item in keys[1:]:
        if isinstance(value, dict):
            value = value.get(item, default)
        else:
            return default

    return value if value is not None else default
