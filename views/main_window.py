"""Main application window."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QMainWindow, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from config import DESKTOP_SIM_MODE, IS_RASPBERRY_PI, UI_CONFIG
from models.evaluation_result import EvaluationResult
from views.camera_view import CameraView
from views.history_view import HistoryView
from views.home_view import HomeView
from views.result_view import ResultView


class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.current_result: EvaluationResult | None = None
        self.compact_mode = False

        self._init_ui()
        self._connect_signals()
        self.show_home()

    def _init_ui(self) -> None:
        self.setObjectName("mainWindow")
        self.setWindowTitle(UI_CONFIG["window_title"])

        viewport_width = 480 if IS_RASPBERRY_PI else UI_CONFIG["window_width"]
        viewport_height = 320 if IS_RASPBERRY_PI else UI_CONFIG["window_height"]

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        if DESKTOP_SIM_MODE and not IS_RASPBERRY_PI:
            central_widget.setFixedSize(viewport_width, viewport_height)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(4, 4, 4, 4)
        root_layout.setSpacing(4)

        self.surface = QFrame()
        self.surface.setObjectName("mainSurface")
        self.surface_layout = QVBoxLayout(self.surface)
        self.surface_layout.setContentsMargins(10, 10, 10, 10)
        self.surface_layout.setSpacing(0)

        self.stack = QStackedWidget()
        self.surface_layout.addWidget(self.stack)
        root_layout.addWidget(self.surface, stretch=1)

        self.home_view = HomeView()
        self.camera_view = CameraView()
        self.result_view = ResultView()
        self.history_view = HistoryView()

        self.stack.addWidget(self.home_view)
        self.stack.addWidget(self.camera_view)
        self.stack.addWidget(self.result_view)
        self.stack.addWidget(self.history_view)

        self.bottom_nav = self._create_bottom_nav()
        root_layout.addWidget(self.bottom_nav)

        if DESKTOP_SIM_MODE and not IS_RASPBERRY_PI:
            self.adjustSize()
            self.setFixedSize(self.sizeHint())
        else:
            self.resize(viewport_width, viewport_height)
            self.setMinimumSize(viewport_width, viewport_height)

    def _create_bottom_nav(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("bottomNav")
        bar.setFixedHeight(36)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 1, 10, 1)
        layout.setSpacing(4)

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

    def _set_nav_state(self, active_index: int | None) -> None:
        for index, button in enumerate([self.btn_home, self.btn_camera, self.btn_history]):
            button.setProperty("active", active_index is not None and index == active_index)
            button.style().unpolish(button)
            button.style().polish(button)

    def _set_page(self, index: int, active_nav: int | None) -> None:
        if index != 1:
            self.camera_view.cleanup()
        self.stack.setCurrentIndex(index)
        self._set_nav_state(active_nav)
        self.bottom_nav.setVisible(index == 0)

    def show_home(self) -> None:
        self.home_view.refresh()
        self._set_page(0, 0)

    def show_camera(self) -> None:
        self._set_page(1, None)

    def show_result(self) -> None:
        self._set_page(2, None)

    def show_history(self) -> None:
        self.history_view.refresh_data()
        self._set_page(3, None)

    def _open_result(self, result: EvaluationResult) -> None:
        self.current_result = result
        self.result_view.set_result(result)
        self.show_result()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.camera_view.cleanup()
        event.accept()
