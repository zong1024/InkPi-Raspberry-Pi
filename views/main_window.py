"""Main application window."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QMainWindow, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from config import IS_RASPBERRY_PI, UI_CONFIG
from models.evaluation_result import EvaluationResult
from views.camera_view import CameraView
from views.history_view import HistoryView
from views.home_view import HomeView
from views.result_view import ResultView

sys.path.insert(0, str(Path(__file__).parent.parent))

SCRIPT_LABELS = {
    "regular": "楷书",
    "running": "行书",
}


class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.current_script_key = "regular"
        self.current_script_label = SCRIPT_LABELS[self.current_script_key]
        self.result_script_labels_by_id: dict[int, str] = {}
        self.current_result: EvaluationResult | None = None
        self._init_ui()
        self._connect_signals()
        self._sync_script_context()
        self.show_home()

    def _init_ui(self) -> None:
        self.setObjectName("mainWindow")
        self.setWindowTitle("InkPi 书法评测系统")

        viewport_width = int(UI_CONFIG["window_width"])
        viewport_height = int(UI_CONFIG["window_height"])

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.surface = QFrame()
        self.surface.setObjectName("mainSurface")
        self.surface_layout = QVBoxLayout(self.surface)
        self.surface_layout.setContentsMargins(14, 12, 14, 0)
        self.surface_layout.setSpacing(0)
        root_layout.addWidget(self.surface, stretch=1)

        self.stack = QStackedWidget()
        self.surface_layout.addWidget(self.stack)

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

        if IS_RASPBERRY_PI:
            self.resize(viewport_width, viewport_height)
            self.setMinimumSize(viewport_width, viewport_height)
        else:
            self.setFixedSize(viewport_width + 16, viewport_height + 40)

    def _create_bottom_nav(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("bottomNav")
        bar.setFixedHeight(44)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 4, 14, 4)
        layout.setSpacing(8)

        self.btn_home = QPushButton("首页")
        self.btn_home.setObjectName("navButton")
        layout.addWidget(self.btn_home)

        self.btn_camera = QPushButton("练习")
        self.btn_camera.setObjectName("navButton")
        layout.addWidget(self.btn_camera)

        self.btn_history = QPushButton("记录")
        self.btn_history.setObjectName("navButton")
        layout.addWidget(self.btn_history)

        return bar

    def _connect_signals(self) -> None:
        self.btn_home.clicked.connect(self.show_home)
        self.btn_camera.clicked.connect(self.show_camera)
        self.btn_history.clicked.connect(self.show_history)

        self.home_view.start_evaluation.connect(self.show_camera)
        self.home_view.script_selected.connect(self._set_script)
        self.home_view.view_history.connect(self.show_history)
        self.home_view.recent_selected.connect(self._open_result)

        self.camera_view.script_selected.connect(self._set_script)
        self.camera_view.capture_completed.connect(self._open_captured_result)
        self.camera_view.cancelled.connect(self.show_home)

        self.result_view.back_requested.connect(self.show_home)
        self.result_view.new_evaluation_requested.connect(self.show_camera)
        self.result_view.history_requested.connect(self.show_history)

        self.history_view.back_requested.connect(self.show_home)
        self.history_view.result_selected.connect(self._open_result)

    def _set_nav_state(self, active_index: int | None) -> None:
        nav_buttons = [self.btn_home, self.btn_camera, self.btn_history]
        for index, button in enumerate(nav_buttons):
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
        self.current_result = self._attach_script_to_result(result)
        self.result_view.set_result(result)
        self.show_result()

    def _open_captured_result(self, result: EvaluationResult) -> None:
        self.current_result = self._attach_script_to_result(result, preferred_script_key=self.current_script_key)
        self.result_view.set_result(result)
        self.show_result()

    def _set_script(self, script_key: str) -> None:
        if script_key not in SCRIPT_LABELS or script_key == self.current_script_key:
            return
        self.current_script_key = script_key
        self.current_script_label = SCRIPT_LABELS[script_key]
        self._sync_script_context()

        current_index = self.stack.currentIndex()
        if current_index == 0:
            self.home_view.refresh()
        elif current_index == 3:
            self.history_view.refresh_data()

    def _sync_script_context(self) -> None:
        self.home_view.set_current_script(self.current_script_key)
        self.home_view.set_result_script_labels(self.result_script_labels_by_id)
        self.camera_view.set_current_script(self.current_script_key)
        self.result_view.set_current_script(self.current_script_key)
        self.history_view.set_current_script(self.current_script_key)
        self.history_view.set_result_script_labels(self.result_script_labels_by_id)

    def _attach_script_to_result(
        self,
        result: EvaluationResult,
        *,
        preferred_script_key: str | None = None,
    ) -> EvaluationResult:
        script_key = self._resolve_result_script_key(result, preferred_script_key)
        script_label = SCRIPT_LABELS.get(script_key, SCRIPT_LABELS["regular"])
        result.script = script_key
        setattr(result, "qt_script_key", script_key)
        setattr(result, "qt_script_label", script_label)

        if result.id is not None:
            self.result_script_labels_by_id[result.id] = script_label
            self.home_view.set_result_script_labels(self.result_script_labels_by_id)
            self.history_view.set_result_script_labels(self.result_script_labels_by_id)
        return result

    def _resolve_result_script_key(
        self,
        result: EvaluationResult,
        preferred_script_key: str | None = None,
    ) -> str:
        if hasattr(result, "get_script"):
            value = result.get_script()
            if value in SCRIPT_LABELS:
                return value
        for attr_name in ("qt_script_key", "script_key", "script_type", "script"):
            value = getattr(result, attr_name, None)
            if isinstance(value, str) and value in SCRIPT_LABELS:
                return value
        if result.id is not None and result.id in self.result_script_labels_by_id:
            label = self.result_script_labels_by_id[result.id]
            for key, known_label in SCRIPT_LABELS.items():
                if known_label == label:
                    return key
        if preferred_script_key in SCRIPT_LABELS:
            return preferred_script_key
        return "regular"

    def closeEvent(self, event) -> None:  # noqa: N802
        self.camera_view.cleanup()
        event.accept()
