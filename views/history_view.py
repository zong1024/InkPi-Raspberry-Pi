"""History view for browsing past OCR + ONNX evaluations."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QStyle, QVBoxLayout, QWidget

from models.evaluation_result import EvaluationResult
from services.database_service import database_service
from views.ui_theme import app_font, clear_layout


class HistoryItem(QFrame):
    """Compact history card close to the visual reference."""

    clicked = pyqtSignal(EvaluationResult)

    def __init__(self, result: EvaluationResult, parent=None):
        super().__init__(parent)
        self.result = result
        self.setObjectName("historyItemCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(86)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        glyph_card = QFrame()
        glyph_card.setObjectName("historyGlyphCard")
        glyph_card.setFixedSize(52, 52)
        glyph_layout = QVBoxLayout(glyph_card)
        glyph_layout.setContentsMargins(0, 0, 0, 0)

        glyph = QLabel(result.character_name or "字")
        glyph.setObjectName("glyphLabel")
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        glyph.setFont(app_font(22, QFont.Weight.Bold))
        glyph_layout.addWidget(glyph)
        layout.addWidget(glyph_card)

        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(2)

        tag = QLabel("识别字")
        tag.setObjectName("miniLabel")
        tag.setFont(app_font(8, QFont.Weight.Bold))
        info.addWidget(tag)

        title = QLabel(result.character_name or "未识别")
        title.setObjectName("sectionTitle")
        title.setFont(app_font(17, QFont.Weight.Bold))
        info.addWidget(title)

        time_label = QLabel(result.timestamp.strftime("%Y.%m.%d %H:%M"))
        time_label.setObjectName("miniLabel")
        time_label.setFont(app_font(9, QFont.Weight.Bold))
        info.addWidget(time_label)
        layout.addLayout(info, stretch=1)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(3)
        right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        grade_label = QLabel(f"等级 {result.get_grade()}")
        grade_label.setObjectName("historyGrade")
        grade_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        grade_label.setFont(app_font(15, QFont.Weight.Bold))
        right.addWidget(grade_label)

        score = QLabel(f"总分 {result.total_score}")
        score.setObjectName("historyScore")
        score.setAlignment(Qt.AlignmentFlag.AlignRight)
        score.setFont(app_font(18, QFont.Weight.Bold))
        right.addWidget(score)
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
        self._init_ui()

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        header = QFrame()
        header.setObjectName("pageHeader")
        header.setFixedHeight(38)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 4, 10, 4)
        header_layout.setSpacing(8)

        self.btn_back = QPushButton("←")
        self.btn_back.setObjectName("headerIconButton")
        self.btn_back.setFixedSize(24, 24)
        self.btn_back.clicked.connect(self.back_requested.emit)
        header_layout.addWidget(self.btn_back)

        title = QLabel("History")
        title.setObjectName("headlineTitle")
        title.setFont(app_font(17, QFont.Weight.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.btn_refresh = QPushButton("")
        self.btn_refresh.setObjectName("headerIconButton")
        self.btn_refresh.setFixedSize(24, 24)
        self.btn_refresh.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.btn_refresh.setIconSize(QSize(14, 14))
        self.btn_refresh.clicked.connect(self.refresh_data)
        header_layout.addWidget(self.btn_refresh)

        self.btn_settings = QPushButton("")
        self.btn_settings.setObjectName("headerIconButton")
        self.btn_settings.setFixedSize(24, 24)
        self.btn_settings.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        self.btn_settings.setIconSize(QSize(14, 14))
        self.btn_settings.setEnabled(False)
        header_layout.addWidget(self.btn_settings)
        root.addWidget(header)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)

        subtitle = QLabel('Past <span style="color:#B80F1F;">Evaluations</span>')
        subtitle.setTextFormat(Qt.TextFormat.RichText)
        subtitle.setObjectName("headlineTitle")
        subtitle.setFont(app_font(16, QFont.Weight.Bold))
        title_row.addWidget(subtitle)
        title_row.addStretch()

        self.total_label = QLabel("TOTAL: 0")
        self.total_label.setObjectName("miniLabel")
        self.total_label.setFont(app_font(9, QFont.Weight.Bold))
        title_row.addWidget(self.total_label)
        root.addLayout(title_row)

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
        clear_layout(self.list_layout)

        records = database_service.get_all(limit=20)
        self.total_label.setText(f"TOTAL: {len(records)}")

        if not records:
            empty_card = QFrame()
            empty_card.setObjectName("softCard")
            empty_layout = QVBoxLayout(empty_card)
            empty_layout.setContentsMargins(16, 14, 16, 14)
            empty_layout.setSpacing(4)

            title = QLabel("暂无历史记录")
            title.setObjectName("sectionTitle")
            title.setFont(app_font(12, QFont.Weight.Bold))
            empty_layout.addWidget(title)

            body = QLabel("完成一次新的评测后，结果会自动出现在这里。")
            body.setObjectName("sectionSubtitle")
            body.setWordWrap(True)
            body.setFont(app_font(10))
            empty_layout.addWidget(body)

            self.list_layout.addWidget(empty_card)
            self.list_layout.addStretch()
            return

        for record in records:
            item = HistoryItem(record)
            item.clicked.connect(self.result_selected.emit)
            self.list_layout.addWidget(item)

        self.list_layout.addStretch()

    def set_compact_mode(self, compact: bool) -> None:
        del compact
