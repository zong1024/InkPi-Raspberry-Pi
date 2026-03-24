"""History view for browsing past evaluations."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from models.evaluation_result import EvaluationResult
from services.database_service import database_service
from views.ui_theme import app_font, clear_layout, score_to_color, score_to_soft_color


class StatTile(QFrame):
    """Small statistics tile."""

    def __init__(self, title: str, value: str, parent=None):
        super().__init__(parent)
        self.setObjectName("statCard")
        self.setMinimumHeight(74)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(2)

        title_label = QLabel(title)
        title_label.setObjectName("mutedLabel")
        title_label.setFont(app_font(10))
        layout.addWidget(title_label)

        value_label = QLabel(value)
        value_label.setObjectName("metricValue")
        value_label.setFont(app_font(22, QFont.Weight.Bold))
        layout.addWidget(value_label)


class HistoryItem(QFrame):
    """History record card."""

    clicked = pyqtSignal(EvaluationResult)
    delete_requested = pyqtSignal(int)

    def __init__(self, result: EvaluationResult, parent=None):
        super().__init__(parent)
        self.result = result
        self.setObjectName("historyCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        score_panel = QFrame()
        score_panel.setStyleSheet(
            f"background-color: {score_to_soft_color(result.total_score)};"
            "border-radius: 18px;"
        )
        score_layout = QVBoxLayout(score_panel)
        score_layout.setContentsMargins(14, 10, 14, 10)
        score_layout.setSpacing(0)

        score_label = QLabel(str(result.total_score))
        score_label.setObjectName("historyScore")
        score_label.setStyleSheet(f"color: {score_to_color(result.total_score)};")
        score_layout.addWidget(score_label, alignment=Qt.AlignmentFlag.AlignCenter)

        grade_label = QLabel(result.get_grade())
        grade_label.setObjectName("historyGrade")
        grade_label.setStyleSheet(f"color: {score_to_color(result.total_score)};")
        score_layout.addWidget(grade_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(score_panel)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)

        title = result.character_name or "书法评测记录"
        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        title_label.setFont(app_font(13, QFont.Weight.Bold))
        text_layout.addWidget(title_label)

        time_label = QLabel(result.timestamp.strftime("%Y-%m-%d %H:%M"))
        time_label.setObjectName("cardSubtitle")
        text_layout.addWidget(time_label)

        detail_text = "  ·  ".join(f"{key}{value}" for key, value in result.detail_scores.items())
        detail_label = QLabel(detail_text)
        detail_label.setObjectName("mutedLabel")
        detail_label.setWordWrap(True)
        text_layout.addWidget(detail_label)

        feedback_label = QLabel(result.feedback[:80] + ("..." if len(result.feedback) > 80 else ""))
        feedback_label.setObjectName("sectionSubtitle")
        feedback_label.setWordWrap(True)
        text_layout.addWidget(feedback_label)

        layout.addLayout(text_layout, stretch=1)

        action_layout = QVBoxLayout()
        action_layout.setSpacing(8)
        action_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        view_chip = QLabel("查看")
        view_chip.setObjectName("accentChip")
        action_layout.addWidget(view_chip, alignment=Qt.AlignmentFlag.AlignRight)

        delete_button = QPushButton("删除")
        delete_button.setObjectName("dangerButton")
        delete_button.setMinimumHeight(36)
        delete_button.clicked.connect(lambda: self.delete_requested.emit(self.result.id))
        action_layout.addWidget(delete_button)

        layout.addLayout(action_layout)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.result)
        super().mousePressEvent(event)


class HistoryView(QWidget):
    """History page."""

    back_requested = pyqtSignal()
    result_selected = pyqtSignal(EvaluationResult)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

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

        stats_title = QLabel("成绩总览")
        stats_title.setObjectName("sectionTitle")
        stats_title.setFont(app_font(16, QFont.Weight.Bold))
        layout.addWidget(stats_title)

        self.stats_row = QHBoxLayout()
        self.stats_row.setSpacing(10)
        layout.addLayout(self.stats_row)

        filter_card = QFrame()
        filter_card.setObjectName("panelCard")
        filter_layout = QHBoxLayout(filter_card)
        filter_layout.setContentsMargins(16, 12, 16, 12)
        filter_layout.setSpacing(8)

        filter_title = QLabel("筛选范围")
        filter_title.setObjectName("mutedLabel")
        filter_layout.addWidget(filter_title)

        self.date_combo = QComboBox()
        self.date_combo.addItems(["全部", "今天", "近 7 天", "近 30 天"])
        self.date_combo.setMinimumWidth(104)
        self.date_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.date_combo)

        filter_layout.addStretch()

        self.record_hint = QLabel("最近 20 条记录")
        self.record_hint.setObjectName("mutedLabel")
        filter_layout.addWidget(self.record_hint)

        btn_refresh = QPushButton("刷新")
        btn_refresh.setObjectName("secondaryButton")
        btn_refresh.setMinimumHeight(40)
        btn_refresh.clicked.connect(self.refresh_data)
        filter_layout.addWidget(btn_refresh)

        btn_back = QPushButton("返回首页")
        btn_back.setObjectName("ghostButton")
        btn_back.setMinimumHeight(40)
        btn_back.clicked.connect(self.back_requested.emit)
        filter_layout.addWidget(btn_back)

        layout.addWidget(filter_card)

        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(8)
        layout.addWidget(self.list_container)
        layout.addStretch()

    def refresh_data(self) -> None:
        self.scroll_area.verticalScrollBar().setValue(0)
        self._load_stats()
        self._load_records()

    def _load_stats(self) -> None:
        stats = database_service.get_statistics()

        clear_layout(self.stats_row)

        tiles = [
            StatTile("累计评测", str(stats["total_count"])),
            StatTile("平均分", str(stats["average_score"]) if stats["total_count"] else "--"),
            StatTile("最佳成绩", str(stats["max_score"]) if stats["total_count"] else "--"),
            StatTile("最低成绩", str(stats["min_score"]) if stats["total_count"] else "--"),
        ]

        for index, tile in enumerate(tiles):
            self.stats_row.addWidget(tile)

    def _load_records(self) -> None:
        clear_layout(self.list_layout)

        filter_index = self.date_combo.currentIndex()
        now = datetime.now()

        if filter_index == 0:
            records = database_service.get_all(limit=20)
            self.record_hint.setText("最近 20 条记录")
        else:
            if filter_index == 1:
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif filter_index == 2:
                start_date = now - timedelta(days=7)
            else:
                start_date = now - timedelta(days=30)
            records = database_service.get_by_date_range(start_date, now)
            self.record_hint.setText(f"筛选结果：{len(records)} 条")

        if not records:
            empty_card = QFrame()
            empty_card.setObjectName("emptyStateCard")
            empty_layout = QVBoxLayout(empty_card)
            empty_layout.setContentsMargins(24, 24, 24, 24)
            empty_layout.setSpacing(8)

            title = QLabel("这个时间范围内还没有记录")
            title.setObjectName("sectionTitle")
            empty_layout.addWidget(title)

            body = QLabel("完成新的书法评测后，记录会自动保存在这里。")
            body.setObjectName("sectionSubtitle")
            body.setWordWrap(True)
            empty_layout.addWidget(body)

            self.list_layout.addWidget(empty_card)
            return

        for record in records:
            item = HistoryItem(record)
            item.clicked.connect(self.result_selected.emit)
            item.delete_requested.connect(self._on_delete_record)
            self.list_layout.addWidget(item)

    def _on_filter_changed(self) -> None:
        self._load_records()

    def _on_delete_record(self, record_id: int) -> None:
        reply = QMessageBox.question(
            self,
            "确认删除",
            "确定要删除这条评测记录吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            database_service.delete(record_id)
            self.refresh_data()
