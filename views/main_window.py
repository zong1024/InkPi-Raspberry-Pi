"""Main application window."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton, QStackedWidget, QVBoxLayout, QWidget

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
        self.root_layout.setContentsMargins(10, 8, 10, 8)
        self.root_layout.setSpacing(8)

        self.top_bar = self._create_top_bar()
        self.root_layout.addWidget(self.top_bar)

        self.surface = QFrame()
        self.surface.setObjectName("mainSurface")
        self.surface_layout = QVBoxLayout(self.surface)
        self.surface_layout.setContentsMargins(10, 8, 10, 8)
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

        self.bottom_nav = self._create_bottom_nav()
        self.root_layout.addWidget(self.bottom_nav)

    def _create_top_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("topBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        self.brand_title = QLabel("InkPi")
        self.brand_title.setObjectName("brandTitle")
        self.brand_title.setFont(app_font(20, QFont.Weight.Bold))
        layout.addWidget(self.brand_title)

        layout.addStretch()

        self.page_title = QLabel("Home")
        self.page_title.setObjectName("miniLabel")
        self.page_title.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.page_title)
        return bar

    def _create_bottom_nav(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("bottomNav")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)

        self.btn_home = QPushButton("HOME")
        self.btn_home.setObjectName("navButton")
        layout.addWidget(self.btn_home)

        self.btn_camera = QPushButton("STUDIO")
        self.btn_camera.setObjectName("navButton")
        layout.addWidget(self.btn_camera)

        self.btn_history = QPushButton("HISTORY")
        self.btn_history.setObjectName("navButton")
        layout.addWidget(self.btn_history)

        return bar

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

    def _should_use_compact_mode(self) -> bool:
        return self.width() <= 540 or self.height() <= 360

    def _apply_compact_mode(self, compact: bool) -> None:
        self.compact_mode = compact
        self.root_layout.setContentsMargins(6 if compact else 10, 6 if compact else 8, 6 if compact else 10, 6 if compact else 8)
        self.root_layout.setSpacing(6 if compact else 8)
        self.surface_layout.setContentsMargins(8 if compact else 10, 8 if compact else 8, 8 if compact else 10, 8 if compact else 8)

        self.brand_title.setFont(app_font(18 if compact else 20, QFont.Weight.Bold))
        self.page_title.setFont(app_font(9 if compact else 10, QFont.Weight.Bold))

        for button in (self.btn_home, self.btn_camera, self.btn_history):
            button.setMinimumHeight(36 if compact else 40)

        for view in (self.home_view, self.camera_view, self.result_view, self.history_view):
            if hasattr(view, "set_compact_mode"):
                view.set_compact_mode(compact)

    def _set_nav_state(self, active_index: int | None) -> None:
        for index, button in enumerate([self.btn_home, self.btn_camera, self.btn_history]):
            button.setProperty("active", active_index is not None and index == active_index)
            button.style().unpolish(button)
            button.style().polish(button)

    def _set_page(self, index: int, title: str, active_nav: int | None) -> None:
        if index != 1:
            self.camera_view.cleanup()
        self.stack.setCurrentIndex(index)
        self.page_title.setText(title)
        self._set_nav_state(active_nav)

    def show_home(self) -> None:
        self.home_view.refresh()
        self._set_page(0, "HOME", 0)

    def show_camera(self) -> None:
        self._set_page(1, "INKPI CAPTURE", 1)

    def show_result(self) -> None:
        self._set_page(2, "EVALUATION RESULT", None)

    def show_history(self) -> None:
        self.history_view.refresh_data()
        self._set_page(3, "HISTORY", 2)

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
