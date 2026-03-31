"""Main application window."""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from config import IS_RASPBERRY_PI, UI_CONFIG
from models.evaluation_result import EvaluationResult
from views.camera_view import CameraView
from views.history_view import HistoryView
from views.home_view import HomeView
from views.result_view import ResultView
from views.ui_theme import app_font


class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.current_result: EvaluationResult | None = None
        self.compact_mode = False

        self._init_ui()
        self._connect_signals()
        self._start_clock()
        self._apply_compact_mode(self._should_use_compact_mode())
        self.show_home()

    def _init_ui(self) -> None:
        self.setObjectName("mainWindow")
        self.setWindowTitle(UI_CONFIG["window_title"])
        self.setMinimumSize(480, 320)

        default_width = 480 if IS_RASPBERRY_PI else UI_CONFIG["window_width"]
        default_height = 320 if IS_RASPBERRY_PI else UI_CONFIG["window_height"]
        self.resize(default_width, default_height)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        self.root_layout = QVBoxLayout(central_widget)
        self.root_layout.setContentsMargins(12, 12, 12, 10)
        self.root_layout.setSpacing(10)

        self.header = self._create_header()
        self.root_layout.addWidget(self.header)

        self.surface = QFrame()
        self.surface.setObjectName("mainSurface")
        self.surface_layout = QVBoxLayout(self.surface)
        self.surface_layout.setContentsMargins(14, 14, 14, 14)
        self.surface_layout.setSpacing(0)

        self.stack = QStackedWidget()
        self.surface_layout.addWidget(self.stack)
        self.root_layout.addWidget(self.surface, stretch=1)

        self.home_view = HomeView()
        self.camera_view = CameraView()
        self.result_view = ResultView()
        self.history_view = HistoryView()

        self.stack.addWidget(self.home_view)
        self.stack.addWidget(self.camera_view)
        self.stack.addWidget(self.result_view)
        self.stack.addWidget(self.history_view)

        self.footer = self._create_footer()
        self.root_layout.addWidget(self.footer)

    def _create_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("appHeader")
        self.header_layout = QHBoxLayout(header)
        self.header_layout.setContentsMargins(20, 14, 20, 14)
        self.header_layout.setSpacing(14)

        brand_layout = QVBoxLayout()
        brand_layout.setSpacing(2)

        brand_title = QLabel("InkPi")
        brand_title.setObjectName("brandTitle")
        brand_title.setFont(app_font(22, QFont.Weight.Bold))
        brand_layout.addWidget(brand_title)
        self.brand_title = brand_title

        brand_caption = QLabel("树莓派书法智能评测台")
        brand_caption.setObjectName("brandCaption")
        brand_caption.setFont(app_font(9))
        brand_layout.addWidget(brand_caption)
        self.brand_caption = brand_caption

        self.header_layout.addLayout(brand_layout)
        self.header_layout.addSpacing(12)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(4)

        self.header_title = QLabel("首页")
        self.header_title.setObjectName("headerTitle")
        self.header_title.setFont(app_font(20, QFont.Weight.Bold))
        title_layout.addWidget(self.header_title)

        self.header_subtitle = QLabel("准备开始新的自动识别评测")
        self.header_subtitle.setObjectName("headerSubtitle")
        self.header_subtitle.setFont(app_font(9))
        title_layout.addWidget(self.header_subtitle)

        self.header_layout.addLayout(title_layout, stretch=1)

        side_layout = QVBoxLayout()
        side_layout.setSpacing(8)
        side_layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        mode_text = "树莓派触控模式" if IS_RASPBERRY_PI else "桌面演示模式"
        self.header_pill = QLabel(mode_text)
        self.header_pill.setObjectName("headerPill")
        side_layout.addWidget(self.header_pill, alignment=Qt.AlignmentFlag.AlignRight)

        self.header_clock = QLabel("--/-- --:--")
        self.header_clock.setObjectName("headerClock")
        self.header_clock.setFont(app_font(11, QFont.Weight.Medium))
        side_layout.addWidget(self.header_clock, alignment=Qt.AlignmentFlag.AlignRight)

        self.header_layout.addLayout(side_layout)
        return header

    def _create_footer(self) -> QFrame:
        footer = QFrame()
        footer.setObjectName("footerBar")
        self.footer_layout = QHBoxLayout(footer)
        self.footer_layout.setContentsMargins(10, 8, 10, 8)
        self.footer_layout.setSpacing(6)

        self.btn_home = QPushButton("首页")
        self.btn_home.setObjectName("navButton")
        self.footer_layout.addWidget(self.btn_home)

        self.btn_camera = QPushButton("拍照")
        self.btn_camera.setObjectName("navButton")
        self.footer_layout.addWidget(self.btn_camera)

        self.btn_history = QPushButton("历史")
        self.btn_history.setObjectName("navButton")
        self.footer_layout.addWidget(self.btn_history)

        return footer

    def _connect_signals(self) -> None:
        self.btn_home.clicked.connect(self.show_home)
        self.btn_camera.clicked.connect(self.show_camera)
        self.btn_history.clicked.connect(self.show_history)

        self.home_view.start_evaluation.connect(self.show_camera)
        self.home_view.view_history.connect(self.show_history)
        self.home_view.recent_selected.connect(self._open_result)

        self.camera_view.capture_completed.connect(self._open_result)
        self.camera_view.cancelled.connect(self.show_home)

        self.result_view.back_requested.connect(self.show_home)
        self.result_view.new_evaluation_requested.connect(self.show_camera)
        self.result_view.history_requested.connect(self.show_history)

        self.history_view.back_requested.connect(self.show_home)
        self.history_view.result_selected.connect(self._open_result)

    def _start_clock(self) -> None:
        self._refresh_clock()
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._refresh_clock)
        self.clock_timer.start(30_000)

    def _refresh_clock(self) -> None:
        self.header_clock.setText(datetime.now().strftime("%m/%d %H:%M"))

    def _should_use_compact_mode(self) -> bool:
        return self.width() <= 540 or self.height() <= 360

    def _apply_compact_mode(self, compact: bool) -> None:
        self.compact_mode = compact

        self.root_layout.setContentsMargins(6 if compact else 12, 6 if compact else 12, 6 if compact else 12, 6 if compact else 10)
        self.root_layout.setSpacing(6 if compact else 10)
        self.surface_layout.setContentsMargins(8 if compact else 14, 8 if compact else 14, 8 if compact else 14, 8 if compact else 14)

        self.header_layout.setContentsMargins(12 if compact else 20, 10 if compact else 14, 12 if compact else 20, 10 if compact else 14)
        self.header_layout.setSpacing(10 if compact else 14)
        self.footer_layout.setContentsMargins(6 if compact else 10, 6 if compact else 8, 6 if compact else 10, 6 if compact else 8)
        self.footer_layout.setSpacing(4 if compact else 6)

        self.brand_title.setFont(app_font(18 if compact else 22, QFont.Weight.Bold))
        self.header_title.setFont(app_font(16 if compact else 20, QFont.Weight.Bold))
        self.header_pill.setVisible(not compact)
        self.brand_caption.setVisible(not compact)
        self.header_subtitle.setVisible(not compact)
        self.header_clock.setVisible(not compact)

        nav_height = 34 if compact else 40
        for button in (self.btn_home, self.btn_camera, self.btn_history):
            button.setMinimumHeight(nav_height)

        for view in (self.home_view, self.camera_view, self.result_view, self.history_view):
            if hasattr(view, "set_compact_mode"):
                view.set_compact_mode(compact)

    def _set_nav_state(self, active_index: int | None) -> None:
        for index, button in enumerate([self.btn_home, self.btn_camera, self.btn_history]):
            button.setProperty("active", active_index is not None and index == active_index)
            button.style().unpolish(button)
            button.style().polish(button)

    def _set_page(self, index: int, title: str, subtitle: str, active_nav: int | None) -> None:
        if index != 1:
            self.camera_view.cleanup()
        self.stack.setCurrentIndex(index)
        self.header_title.setText(title)
        self.header_subtitle.setText(subtitle)
        self._set_nav_state(active_nav)

    def show_home(self) -> None:
        self.home_view.refresh()
        self._set_page(0, "首页", "查看最近成绩，并开始新的自动识别评测", 0)

    def show_camera(self) -> None:
        self._set_page(1, "拍照评测", "让单个汉字落在取景框中央，系统会自动识别并评分", 1)

    def show_result(self) -> None:
        subtitle = "评测已完成，可以查看结果或继续下一次拍摄"
        if self.current_result and self.current_result.character_name:
            subtitle = f"自动识别：{self.current_result.character_name}"
        self._set_page(2, "评测结果", subtitle, None)

    def show_history(self) -> None:
        self.history_view.refresh_data()
        self._set_page(3, "历史记录", "按时间筛选并回看过去的评测结果", 2)

    def _open_result(self, result: EvaluationResult) -> None:
        self.current_result = result
        self.result_view.set_result(result)
        self.show_result()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        compact = self._should_use_compact_mode()
        if compact != self.compact_mode:
            self._apply_compact_mode(compact)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.camera_view.cleanup()
        event.accept()
