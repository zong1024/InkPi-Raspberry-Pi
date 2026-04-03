"""Home view for the small-screen InkPi interface."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from models.evaluation_result import EvaluationResult
from services.database_service import database_service
from views.ui_theme import app_font


class HomeView(QWidget):
    """Touch-friendly landing page."""

    start_evaluation = pyqtSignal()
    view_history = pyqtSignal()
    recent_selected = pyqtSignal(EvaluationResult)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.compact_mode = False
        self.latest_result: EvaluationResult | None = None
        self._init_ui()
        self.refresh()

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(2, 2, 2, 2)
        root.setSpacing(10)

        hero = QFrame()
        hero.setObjectName("heroCard")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(6, 6, 6, 4)
        hero_layout.setSpacing(8)

        brand = QLabel("InkPi")
        brand.setObjectName("brandAccent")
        brand.setFont(app_font(28, QFont.Weight.Bold))
        hero_layout.addWidget(brand)

        subtitle = QLabel("THE MODERN CALLIGRAPHER")
        subtitle.setObjectName("miniLabel")
        hero_layout.addWidget(subtitle)

        self.btn_start = QPushButton("开始评测   ->")
        self.btn_start.setObjectName("primaryButton")
        self.btn_start.setMinimumHeight(54)
        self.btn_start.clicked.connect(self.start_evaluation.emit)
        hero_layout.addWidget(self.btn_start)

        root.addWidget(hero)

        action_grid = QGridLayout()
        action_grid.setHorizontalSpacing(10)
        action_grid.setVerticalSpacing(10)

        self.btn_recent = QPushButton("最近结果")
        self.btn_recent.setObjectName("secondaryButton")
        self.btn_recent.setMinimumHeight(48)
        self.btn_recent.clicked.connect(self._open_latest)
        action_grid.addWidget(self.btn_recent, 0, 0)

        self.btn_history = QPushButton("历史记录")
        self.btn_history.setObjectName("secondaryButton")
        self.btn_history.setMinimumHeight(48)
        self.btn_history.clicked.connect(self.view_history.emit)
        action_grid.addWidget(self.btn_history, 0, 1)

        self.btn_settings = QPushButton("设置")
        self.btn_settings.setObjectName("secondaryButton")
        self.btn_settings.setMinimumHeight(48)
        self.btn_settings.setEnabled(False)
        action_grid.addWidget(self.btn_settings, 1, 0)

        self.quick_eval = QPushButton("+")
        self.quick_eval.setObjectName("circleButton")
        self.quick_eval.setFixedSize(56, 56)
        self.quick_eval.clicked.connect(self.start_evaluation.emit)
        action_grid.addWidget(self.quick_eval, 1, 1, alignment=Qt.AlignmentFlag.AlignRight)

        root.addLayout(action_grid)

        self.recent_card = QFrame()
        self.recent_card.setObjectName("softCard")
        recent_layout = QHBoxLayout(self.recent_card)
        recent_layout.setContentsMargins(14, 12, 14, 12)
        recent_layout.setSpacing(12)

        self.latest_score = QLabel("--")
        self.latest_score.setObjectName("scoreNumber")
        self.latest_score.setFont(app_font(34, QFont.Weight.Bold))
        recent_layout.addWidget(self.latest_score)

        detail_layout = QVBoxLayout()
        detail_layout.setSpacing(4)

        self.latest_char = QLabel("暂无评测")
        self.latest_char.setObjectName("sectionTitle")
        self.latest_char.setFont(app_font(14, QFont.Weight.Bold))
        detail_layout.addWidget(self.latest_char)

        self.latest_meta = QLabel("完成一次评测后，这里会显示识别字、等级和时间。")
        self.latest_meta.setObjectName("sectionSubtitle")
        self.latest_meta.setWordWrap(True)
        self.latest_meta.setFont(app_font(10))
        detail_layout.addWidget(self.latest_meta)

        self.latest_feedback = QLabel("轻量模式，适合 3.5 寸触摸屏快速操作。")
        self.latest_feedback.setObjectName("mutedLabel")
        self.latest_feedback.setWordWrap(True)
        self.latest_feedback.setFont(app_font(9))
        detail_layout.addWidget(self.latest_feedback)

        recent_layout.addLayout(detail_layout, stretch=1)
        root.addWidget(self.recent_card)
        root.addStretch()

    def refresh(self) -> None:
        recent_records = database_service.get_recent(1)
        self.latest_result = recent_records[0] if recent_records else None

        if self.latest_result is None:
            self.latest_score.setText("--")
            self.latest_char.setText("暂无评测")
            self.latest_meta.setText("完成一次评测后，这里会显示识别字、等级和时间。")
            self.latest_feedback.setText("点击“开始评测”进入拍照 / 上传流程。")
            self.btn_recent.setEnabled(False)
            return

        result = self.latest_result
        self.latest_score.setText(str(result.total_score))
        self.latest_char.setText(result.character_name or "未识别")
        self.latest_meta.setText(
            f"{result.get_grade()} 级  |  {result.timestamp.strftime('%m-%d %H:%M')}"
        )
        self.latest_feedback.setText(result.feedback[:44] + ("..." if len(result.feedback) > 44 else ""))
        self.btn_recent.setEnabled(True)

    def _open_latest(self) -> None:
        if self.latest_result is not None:
            self.recent_selected.emit(self.latest_result)

    def set_compact_mode(self, compact: bool) -> None:
        self.compact_mode = compact
        self.btn_start.setMinimumHeight(50 if compact else 54)
        for button in (self.btn_recent, self.btn_history, self.btn_settings):
            button.setMinimumHeight(44 if compact else 48)
