"""Settings and diagnostics view for the compact Qt UI."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from services.camera_service import camera_service
from services.calligraphy_style_service import calligraphy_style_service
from services.local_ocr_service import local_ocr_service
from services.quality_scorer_service import quality_scorer_service
from views.ui_theme import app_font


class SettingsView(QWidget):
    """Small-screen status/settings page."""

    back_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.compact_mode = False
        self._init_ui()

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        title = QLabel("运行状态")
        title.setObjectName("sectionTitle")
        title.setFont(app_font(13, QFont.Weight.Bold))
        root.addWidget(title)

        self.status_card = QFrame()
        self.status_card.setObjectName("softCard")
        self.status_card.setFixedHeight(82)
        status_layout = QVBoxLayout(self.status_card)
        status_layout.setContentsMargins(12, 8, 12, 8)
        status_layout.setSpacing(4)

        self.ocr_value = self._make_value_label()
        self.onnx_value = self._make_value_label()
        self.camera_value = self._make_value_label()
        for label_text, value_label in (
            ("OCR", self.ocr_value),
            ("ONNX", self.onnx_value),
            ("摄像头", self.camera_value),
        ):
            row = QHBoxLayout()
            row.setSpacing(8)
            label = QLabel(label_text)
            label.setObjectName("miniLabel")
            label.setFixedWidth(72)
            label.setFont(app_font(9, QFont.Weight.Bold))
            row.addWidget(label)
            row.addWidget(value_label, stretch=1)
            status_layout.addLayout(row)

        root.addWidget(self.status_card)

        self.style_card = QFrame()
        self.style_card.setObjectName("softCard")
        self.style_card.setFixedHeight(48)
        style_layout = QHBoxLayout(self.style_card)
        style_layout.setContentsMargins(10, 7, 10, 7)
        style_layout.setSpacing(6)

        style_label = QLabel("书体")
        style_label.setObjectName("miniLabel")
        style_label.setFixedWidth(48)
        style_label.setFont(app_font(9, QFont.Weight.Bold))
        style_layout.addWidget(style_label)

        self.btn_kaishu = QPushButton("楷书")
        self.btn_kaishu.setObjectName("secondaryButton")
        self.btn_kaishu.setFixedHeight(32)
        self.btn_kaishu.clicked.connect(lambda: self._set_style("kaishu"))
        style_layout.addWidget(self.btn_kaishu)

        self.btn_xingshu = QPushButton("行书")
        self.btn_xingshu.setObjectName("secondaryButton")
        self.btn_xingshu.setFixedHeight(32)
        self.btn_xingshu.clicked.connect(lambda: self._set_style("xingshu"))
        style_layout.addWidget(self.btn_xingshu)

        root.addWidget(self.style_card)

        actions = QHBoxLayout()
        actions.setSpacing(6)
        self.btn_refresh = QPushButton("刷新状态")
        self.btn_refresh.setObjectName("secondaryButton")
        self.btn_refresh.setFixedHeight(34)
        self.btn_refresh.clicked.connect(self.refresh)
        actions.addWidget(self.btn_refresh)

        self.btn_back = QPushButton("返回首页")
        self.btn_back.setObjectName("primaryButton")
        self.btn_back.setFixedHeight(34)
        self.btn_back.clicked.connect(self.back_requested.emit)
        actions.addWidget(self.btn_back)
        root.addLayout(actions)

        root.addStretch()
        self.refresh()

    def _make_value_label(self, text: str = "--") -> QLabel:
        label = QLabel(text)
        label.setObjectName("sectionTitle")
        label.setFont(app_font(10, QFont.Weight.Bold))
        return label

    def refresh(self) -> None:
        self.ocr_value.setText("在线" if local_ocr_service.available else "离线")
        self.onnx_value.setText("在线" if quality_scorer_service.available else "离线")
        self.camera_value.setText("可用" if camera_service.available else "离线")
        self._sync_style_buttons()

    def _set_style(self, style: str) -> None:
        calligraphy_style_service.set_style(style)
        self._sync_style_buttons()

    def _sync_style_buttons(self) -> None:
        active = calligraphy_style_service.current_style
        for style, button in (("kaishu", self.btn_kaishu), ("xingshu", self.btn_xingshu)):
            button.setProperty("active", style == active)
            button.setObjectName("primaryButton" if style == active else "secondaryButton")
            button.style().unpolish(button)
            button.style().polish(button)

    def set_compact_mode(self, compact: bool) -> None:
        self.compact_mode = compact
