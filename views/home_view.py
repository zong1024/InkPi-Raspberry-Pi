"""Home view for the touch-first InkPi interface."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from models.evaluation_result import EvaluationResult
from services.database_service import database_service
from views.ui_theme import THEME, app_font, clear_layout, score_to_color, score_to_soft_color


class StatCard(QFrame):
    """Compact metric card."""

    def __init__(self, title: str, value: str, hint: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("statCard")
        self.setMinimumHeight(82)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(2)

        title_label = QLabel(title)
        title_label.setObjectName("mutedLabel")
        title_label.setFont(app_font(10))
        layout.addWidget(title_label)

        value_label = QLabel(value)
        value_label.setObjectName("metricValue")
        value_label.setFont(app_font(24, QFont.Weight.Bold))
        layout.addWidget(value_label)

        hint_label = QLabel(hint)
        hint_label.setObjectName("cardSubtitle")
        hint_label.setFont(app_font(9))
        layout.addWidget(hint_label)


class RecentCard(QFrame):
    """Recent evaluation card."""

    selected = pyqtSignal(EvaluationResult)

    def __init__(self, result: EvaluationResult, parent=None):
        super().__init__(parent)
        self.result = result
        self.setObjectName("historyCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        score_block = QFrame()
        score_block.setStyleSheet(
            f"background-color: {score_to_soft_color(result.total_score)};"
            "border-radius: 18px;"
        )
        score_layout = QVBoxLayout(score_block)
        score_layout.setContentsMargins(16, 10, 16, 10)
        score_layout.setSpacing(0)

        score_label = QLabel(str(result.total_score))
        score_label.setObjectName("historyScore")
        score_label.setStyleSheet(f"color: {score_to_color(result.total_score)};")
        score_layout.addWidget(score_label, alignment=Qt.AlignmentFlag.AlignCenter)

        grade_label = QLabel(result.get_grade())
        grade_label.setObjectName("historyGrade")
        grade_label.setStyleSheet(f"color: {score_to_color(result.total_score)};")
        score_layout.addWidget(grade_label, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(score_block)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        title = result.character_name or "未命名书法评测"
        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        title_label.setFont(app_font(13, QFont.Weight.Bold))
        info_layout.addWidget(title_label)

        time_label = QLabel(result.timestamp.strftime("%m-%d %H:%M"))
        time_label.setObjectName("cardSubtitle")
        time_label.setFont(app_font(9))
        info_layout.addWidget(time_label)

        details = " / ".join(f"{name}{score}" for name, score in result.detail_scores.items())
        details_label = QLabel(details)
        details_label.setObjectName("mutedLabel")
        details_label.setWordWrap(True)
        details_label.setFont(app_font(9))
        info_layout.addWidget(details_label)

        layout.addLayout(info_layout, stretch=1)

        arrow_label = QLabel("查看")
        arrow_label.setObjectName("accentChip")
        layout.addWidget(arrow_label, alignment=Qt.AlignmentFlag.AlignVCenter)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self.result)
        super().mousePressEvent(event)


class HomeView(QWidget):
    """Touch-friendly home dashboard."""

    start_evaluation = pyqtSignal()
    view_history = pyqtSignal()
    recent_selected = pyqtSignal(EvaluationResult)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self.refresh()

    def _init_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        root_layout.addWidget(self.scroll_area)

        container = QWidget()
        self.scroll_area.setWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(12)

        hero_card = QFrame()
        hero_card.setObjectName("heroCard")
        hero_card.setMinimumHeight(148)
        hero_layout = QHBoxLayout(hero_card)
        hero_layout.setContentsMargins(20, 18, 20, 18)
        hero_layout.setSpacing(16)

        hero_text = QVBoxLayout()
        hero_text.setSpacing(6)

        eyebrow = QLabel("树莓派触控工作台")
        eyebrow.setObjectName("heroEyebrow")
        hero_text.addWidget(eyebrow, alignment=Qt.AlignmentFlag.AlignLeft)

        title = QLabel("开始一张新的书法评测")
        title.setObjectName("sectionTitle")
        title.setWordWrap(True)
        title.setFont(app_font(18, QFont.Weight.Bold))
        hero_text.addWidget(title)

        subtitle = QLabel("把单个汉字放进镜头里，几秒内就能拿到结构、笔画、平衡和韵律评分。")
        subtitle.setObjectName("sectionSubtitle")
        subtitle.setWordWrap(True)
        subtitle.setFont(app_font(9))
        hero_text.addWidget(subtitle)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)

        self.btn_start = QPushButton("开始评测")
        self.btn_start.setObjectName("primaryButton")
        self.btn_start.setMinimumHeight(50)
        self.btn_start.clicked.connect(self.start_evaluation.emit)
        button_row.addWidget(self.btn_start)

        self.btn_history = QPushButton("查看历史")
        self.btn_history.setObjectName("secondaryButton")
        self.btn_history.setMinimumHeight(50)
        self.btn_history.clicked.connect(self.view_history.emit)
        button_row.addWidget(self.btn_history)

        hero_text.addLayout(button_row)
        hero_layout.addLayout(hero_text, stretch=3)

        cue_card = QFrame()
        cue_card.setObjectName("accentCard")
        cue_card.setFixedWidth(196)
        cue_layout = QVBoxLayout(cue_card)
        cue_layout.setContentsMargins(18, 16, 18, 16)
        cue_layout.setSpacing(6)

        cue_title = QLabel("今日状态")
        cue_title.setStyleSheet("color: #fff4e5; font-size: 13px; font-weight: 700;")
        cue_layout.addWidget(cue_title)

        self.hero_metric = QLabel("准备开始")
        self.hero_metric.setStyleSheet("color: #fffaf1; font-size: 24px; font-weight: 800;")
        cue_layout.addWidget(self.hero_metric)

        self.hero_hint = QLabel("完成一次评测后，这里会显示你的近期趋势。")
        self.hero_hint.setStyleSheet("color: #d7c4ae; font-size: 9px;")
        self.hero_hint.setWordWrap(True)
        cue_layout.addWidget(self.hero_hint)

        hero_layout.addWidget(cue_card, stretch=2)
        layout.addWidget(hero_card)

        self.stats_layout = QHBoxLayout()
        self.stats_layout.setSpacing(10)
        layout.addLayout(self.stats_layout)

        recent_header = QHBoxLayout()
        recent_header.setSpacing(10)

        recent_title = QLabel("近期记录")
        recent_title.setObjectName("sectionTitle")
        recent_title.setFont(app_font(16, QFont.Weight.Bold))
        recent_header.addWidget(recent_title)
        recent_header.addStretch()

        recent_hint = QLabel("点开可直接回看结果")
        recent_hint.setObjectName("mutedLabel")
        recent_header.addWidget(recent_hint)
        layout.addLayout(recent_header)

        self.recent_container = QWidget()
        self.recent_layout = QVBoxLayout(self.recent_container)
        self.recent_layout.setContentsMargins(0, 0, 0, 0)
        self.recent_layout.setSpacing(10)
        layout.addWidget(self.recent_container)
        layout.addStretch()

    def refresh(self) -> None:
        stats = database_service.get_statistics()
        recent_records = database_service.get_recent(4)
        self.scroll_area.verticalScrollBar().setValue(0)

        clear_layout(self.stats_layout)

        self.stats_layout.addWidget(StatCard("累计评测", str(stats["total_count"]), "总记录数"))
        self.stats_layout.addWidget(
            StatCard("平均分", str(stats["average_score"]) if stats["total_count"] else "--", "近期稳定度")
        )
        self.stats_layout.addWidget(
            StatCard("最佳成绩", str(stats["max_score"]) if stats["total_count"] else "--", "个人最好表现")
        )

        if recent_records:
            latest = recent_records[0]
            self.hero_metric.setText(f"最近 {latest.total_score} 分")
            self.hero_metric.setStyleSheet("color: #fffaf1; font-size: 28px; font-weight: 800;")
            self.hero_hint.setText(
                f"最近一次评测：{latest.timestamp.strftime('%m-%d %H:%M')} / {latest.get_grade()}"
            )
        else:
            self.hero_metric.setText("准备开始")
            self.hero_metric.setStyleSheet("color: #fffaf1; font-size: 28px; font-weight: 800;")
            self.hero_hint.setText("完成一次评测后，这里会显示你的近期趋势。")

        clear_layout(self.recent_layout)

        if not recent_records:
            empty_state = QFrame()
            empty_state.setObjectName("emptyStateCard")
            empty_layout = QVBoxLayout(empty_state)
            empty_layout.setContentsMargins(24, 24, 24, 24)
            empty_layout.setSpacing(8)

            empty_title = QLabel("还没有评测记录")
            empty_title.setObjectName("sectionTitle")
            empty_layout.addWidget(empty_title)

            empty_text = QLabel("第一次拍照评测后，成绩和建议会自动保存到这里。")
            empty_text.setObjectName("sectionSubtitle")
            empty_text.setWordWrap(True)
            empty_layout.addWidget(empty_text)

            self.recent_layout.addWidget(empty_state)
            return

        for record in recent_records:
            card = RecentCard(record)
            card.selected.connect(self.recent_selected.emit)
            self.recent_layout.addWidget(card)
