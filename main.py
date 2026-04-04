#!/usr/bin/env python3
"""InkPi application entry point."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(_PROJECT_ROOT))

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from config import APP_CONFIG, DATA_DIR, IS_RASPBERRY_PI, LOG_CONFIG
from views.main_window import MainWindow
from views.ui_theme import build_stylesheet, ensure_app_font_family


def setup_logging() -> None:
    """Configure app logging."""
    log_config = LOG_CONFIG
    logging.basicConfig(
        level=getattr(logging, log_config.get("level", "INFO")),
        format=log_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_config.get("log_file", DATA_DIR / "inkpi.log"), encoding="utf-8"),
        ],
    )


def configure_application(app: QApplication) -> None:
    """Apply global application settings."""
    app.setApplicationName(APP_CONFIG["app_name"])
    app.setApplicationVersion(APP_CONFIG["version"])
    app.setStyleSheet(build_stylesheet())
    app.setFont(QFont(ensure_app_font_family(), 10))
    app.setQuitOnLastWindowClosed(True)


def main() -> None:
    """Launch the application."""
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("InkPi 书法评测系统启动中...")

    app = QApplication(sys.argv)
    configure_application(app)

    window = MainWindow()
    if IS_RASPBERRY_PI and APP_CONFIG["window"].get("fullscreen", True):
        window.showFullScreen()
    else:
        window.show()

    logger.info("应用启动完成")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
