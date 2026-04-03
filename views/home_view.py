"""Home view tuned for a 480x320 touch screen."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QStyle, QVBoxLayout, QWidget

from models.evaluation_result import EvaluationResult
from services.database_service import database_service
from views.ui_theme import app_font


class HomeView(QWidget):
    """Landing page that closely follows the provided reference layout."""

    start_evaluation = pyqtSignal()
    view_history = pyqtSignal()
    recent_selected = pyqtSignal(EvaluationResult)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.latest_result: EvaluationResult | None = None
        self._init_ui()
        self.refresh()

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        header = QFrame()
        header.setObjectName("pageHeader")
        header.setFixedHeight(52)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 10, 14, 10)
        header_layout.setSpacing(8)

        brand = QLabel("InkPi")
        brand.setObjectName("brandTitle")
        brand.setFont(app_font(20, QFont.Weight.Bold))
        header_layout.addWidget(brand)
        header_layout.addStretch()

        self.btn_refresh = self._build_icon_button(QStyle.StandardPixmap.SP_BrowserReload)
        self.btn_refresh.clicked.connect(self.refresh)
        header_layout.addWidget(self.btn_refresh)

        self.btn_settings = self._build_icon_button(QStyle.StandardPixmap.SP_FileDialogDetailedView)
        self.btn_settings.setEnabled(False)
        header_layout.addWidget(self.btn_settings)
        root.addWidget(header)

        hero = QWidget()
        hero.setFixedHeight(104)
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(4, 4, 4, 4)
        hero_layout.setSpacing(10)

        brand_block = QVBoxLayout()
        brand_block.setContentsMargins(0, 0, 0, 0)
        brand_block.setSpacing(0)
        brand_block.addStretch()

        hero_logo = QLabel("InkPi")
        hero_logo.setObjectName("brandAccent")
        hero_logo.setFont(app_font(32, QFont.Weight.Bold))
        brand_block.addWidget(hero_logo)

        hero_subtitle = QLabel("THE MODERN CALLIGRAPHER")
        hero_subtitle.setObjectName("miniLabel")
        hero_subtitle.setFont(app_font(9, QFont.Weight.Bold))
        brand_block.addWidget(hero_subtitle)
        brand_block.addStretch()
        hero_layout.addLayout(brand_block, stretch=3)

        self.btn_start = QPushButton("开始评测        →")
        self.btn_start.setObjectName("primaryButton")
        self.btn_start.setFixedSize(206, 54)
        self.btn_start.setFont(app_font(14, QFont.Weight.Bold))
        self.btn_start.clicked.connect(self.start_evaluation.emit)
        hero_layout.addWidget(self.btn_start, alignment=Qt.AlignmentFlag.AlignCenter)
        root.addWidget(hero)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(10)

        self.btn_studio = QPushButton("笔")
        self.btn_studio.setObjectName("buttonCard")
        self.btn_studio.setFixedSize(54, 54)
        self.btn_studio.setFont(app_font(18, QFont.Weight.Bold))
        self.btn_studio.clicked.connect(self.start_evaluation.emit)
        action_row.addWidget(self.btn_studio)

        self.btn_history = QPushButton("历史记录")
        self.btn_history.setObjectName("buttonCard")
        self.btn_history.setFixedSize(118, 54)
        self.btn_history.setFont(app_font(11, QFont.Weight.Bold))
        self.btn_history.clicked.connect(self.view_history.emit)
        action_row.addWidget(self.btn_history)

        self.btn_settings_tile = QPushButton("设置")
        self.btn_settings_tile.setObjectName("buttonCard")
        self.btn_settings_tile.setFixedSize(72, 54)
        self.btn_settings_tile.setFont(app_font(11, QFont.Weight.Bold))
        self.btn_settings_tile.setEnabled(False)
        action_row.addWidget(self.btn_settings_tile)

        self.btn_plus = QPushButton("+")
        self.btn_plus.setObjectName("floatingButton")
        self.btn_plus.setFixedSize(54, 54)
        self.btn_plus.clicked.connect(self._open_latest_or_start)
        action_row.addWidget(self.btn_plus)
        root.addLayout(action_row)

        self.latest_hint = QLabel("")
        self.latest_hint.setObjectName("miniLabel")
        self.latest_hint.setFixedHeight(16)
        self.latest_hint.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(self.latest_hint)

        root.addStretch()

    def _build_icon_button(self, icon_type: QStyle.StandardPixmap) -> QPushButton:
        button = QPushButton("")
        button.setObjectName("headerIconButton")
        button.setFixedSize(24, 24)
        button.setIcon(self.style().standardIcon(icon_type))
        button.setIconSize(QSize(14, 14))
        return button

    def refresh(self) -> None:
        recent_records = database_service.get_recent(1)
        self.latest_result = recent_records[0] if recent_records else None

        if self.latest_result is None:
            self.latest_hint.setText("本地 480x320 小屏模式已开启")
            return

        result = self.latest_result
        char_text = result.character_name or "未识别"
        self.latest_hint.setText(
            f"最近一次：{char_text} · {result.total_score} 分 · {result.timestamp.strftime('%m-%d %H:%M')}"
        )

    def _open_latest_or_start(self) -> None:
        if self.latest_result is not None:
            self.recent_selected.emit(self.latest_result)
            return
        self.start_evaluation.emit()

    def set_compact_mode(self, compact: bool) -> None:
        del compact
