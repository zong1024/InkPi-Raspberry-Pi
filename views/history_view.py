"""History view for browsing past OCR + ONNX evaluations."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget

from models.evaluation_result import EvaluationResult
from services.database_service import database_service
from views.ui_theme import app_font, clear_layout


class HistoryItem(QFrame):
    """History record card."""

    clicked = pyqtSignal(EvaluationResult)
    delete_requested = pyqtSignal(int)

    def __init__(self, result: EvaluationResult, parent=None):
        super().__init__(parent)
        self.result = result
        self.setObjectName("historyItemCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        glyph_card = QFrame()
        glyph_card.setObjectName("historyGlyphCard")
        glyph_layout = QVBoxLayout(glyph_card)
        glyph_layout.setContentsMargins(12, 10, 12, 10)
        glyph_layout.setSpacing(4)

        glyph = QLabel(result.character_name or "字")
        glyph.setObjectName("glyphLabel")
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        glyph_layout.addWidget(glyph)

        layout.addWidget(glyph_card)

        info = QVBoxLayout()
        info.setSpacing(4)

        title = QLabel(result.character_name or "未识别")
        title.setObjectName("sectionTitle")
        title.setFont(app_font(13, QFont.Weight.Bold))
        info.addWidget(title)

        time_label = QLabel(result.timestamp.strftime("%Y-%m-%d %H:%M"))
        time_label.setObjectName("mutedLabel")
        time_label.setFont(app_font(10))
        info.addWidget(time_label)

        feedback = QLabel(result.feedback[:36] + ("..." if len(result.feedback) > 36 else ""))
        feedback.setObjectName("sectionSubtitle")
        feedback.setWordWrap(True)
        feedback.setFont(app_font(10))
        info.addWidget(feedback)
        layout.addLayout(info, stretch=1)

        right = QVBoxLayout()
        right.setSpacing(4)
        right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        grade = QLabel(result.get_grade())
        grade.setObjectName("historyGrade")
        grade.setAlignment(Qt.AlignmentFlag.AlignRight)
        right.addWidget(grade)

        score = QLabel(str(result.total_score))
        score.setObjectName("historyScore")
        score.setAlignment(Qt.AlignmentFlag.AlignRight)
        right.addWidget(score)

        delete_button = QPushButton("删除")
        delete_button.setObjectName("ghostButton")
        delete_button.setMinimumHeight(32)
        delete_button.clicked.connect(lambda: self.delete_requested.emit(self.result.id))
        right.addWidget(delete_button)

        layout.addLayout(right)

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
        self.compact_mode = False
        self._init_ui()

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(2, 2, 2, 2)
        root.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(8)

        title = QLabel("Past Evaluations")
        title.setObjectName("pageTitle")
        title.setFont(app_font(18, QFont.Weight.Bold))
        header.addWidget(title)

        header.addStretch()

        self.total_label = QLabel("TOTAL: 0")
        self.total_label.setObjectName("miniLabel")
        header.addWidget(self.total_label)
        root.addLayout(header)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)

        self.date_combo = QComboBox()
        self.date_combo.addItems(["全部", "今天", "近 7 天", "近 30 天"])
        self.date_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self.date_combo, stretch=1)

        self.btn_back = QPushButton("返回首页")
        self.btn_back.setObjectName("secondaryButton")
        self.btn_back.setMinimumHeight(38)
        self.btn_back.clicked.connect(self.back_requested.emit)
        filter_row.addWidget(self.btn_back)
        root.addLayout(filter_row)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        root.addWidget(self.scroll_area, stretch=1)

        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(8)
        self.scroll_area.setWidget(self.list_container)

    def refresh_data(self) -> None:
        self.scroll_area.verticalScrollBar().setValue(0)
        self._load_records()

    def _load_records(self) -> None:
        clear_layout(self.list_layout)

        filter_index = self.date_combo.currentIndex()
        now = datetime.now()

        if filter_index == 0:
            records = database_service.get_all(limit=20)
        else:
            if filter_index == 1:
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif filter_index == 2:
                start_date = now - timedelta(days=7)
            else:
                start_date = now - timedelta(days=30)
            records = database_service.get_by_date_range(start_date, now)

        self.total_label.setText(f"TOTAL: {len(records)}")

        if not records:
            empty_card = QFrame()
            empty_card.setObjectName("emptyStateCard")
            empty_layout = QVBoxLayout(empty_card)
            empty_layout.setContentsMargins(20, 18, 20, 18)
            empty_layout.setSpacing(6)

            title = QLabel("暂无记录")
            title.setObjectName("sectionTitle")
            empty_layout.addWidget(title)

            body = QLabel("完成新的评测后，结果会自动保存在这里。")
            body.setObjectName("sectionSubtitle")
            body.setWordWrap(True)
            empty_layout.addWidget(body)

            self.list_layout.addWidget(empty_card)
            self.list_layout.addStretch()
            return

        for record in records:
            item = HistoryItem(record)
            item.clicked.connect(self.result_selected.emit)
            item.delete_requested.connect(self._on_delete_record)
            self.list_layout.addWidget(item)

        self.list_layout.addStretch()

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

    def set_compact_mode(self, compact: bool) -> None:
        self.compact_mode = compact
