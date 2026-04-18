"""History view for browsing past OCR + ONNX evaluations."""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from models.evaluation_result import EvaluationResult
from services.database_service import database_service
from views.ui_theme import app_font, clear_layout, display_font, icon_font

sys.path.insert(0, str(Path(__file__).parent.parent))

SCRIPT_LABELS = {
    "regular": "楷书",
    "running": "行书",
}


class HistoryItem(QFrame):
    """Compact history card that highlights what to fix next."""

    clicked = pyqtSignal(EvaluationResult)

    def __init__(self, result: EvaluationResult, script_label: str, parent=None):
        super().__init__(parent)
        self.result = result
        self.setObjectName("historyItemCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(92)

        profile = result.get_practice_profile()
        focus = profile.get("focus_dimension") if profile else None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        glyph_card = QFrame()
        glyph_card.setObjectName("historyGlyphCard")
        glyph_card.setFixedSize(48, 48)
        glyph_layout = QVBoxLayout(glyph_card)
        glyph_layout.setContentsMargins(0, 0, 0, 0)

        glyph = QLabel(result.character_name or "未")
        glyph.setObjectName("glyphLabel")
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        glyph.setFont(display_font(21, QFont.Weight.Bold))
        glyph_layout.addWidget(glyph)
        layout.addWidget(glyph_card)

        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(2)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(6)

        title = QLabel(result.character_name or "未识别")
        title.setObjectName("sectionTitle")
        title.setFont(display_font(15, QFont.Weight.Bold))
        title_row.addWidget(title)

        script_badge = QLabel(script_label)
        script_badge.setObjectName("coachBadge")
        script_badge.setFont(app_font(7, QFont.Weight.Bold))
        title_row.addWidget(script_badge)
        title_row.addStretch()
        info.addLayout(title_row)

        focus_text = "下一练：查看完整建议"
        if focus:
            focus_text = f"下一练：{focus['label']} {focus['score']} 分"
        focus_label = QLabel(focus_text)
        focus_label.setObjectName("hintText")
        focus_label.setFont(app_font(8, QFont.Weight.Bold))
        info.addWidget(focus_label)

        time_label = QLabel(result.timestamp.strftime("%Y.%m.%d %H:%M"))
        time_label.setObjectName("miniLabel")
        time_label.setFont(app_font(8))
        info.addWidget(time_label)
        layout.addLayout(info, stretch=1)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(3)
        right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        score = QLabel(str(result.total_score))
        score.setObjectName("historyScore")
        score.setAlignment(Qt.AlignmentFlag.AlignRight)
        score.setFont(display_font(22, QFont.Weight.Bold))
        right.addWidget(score)

        grade_label = QLabel(f"等级 {result.get_grade()}")
        grade_label.setObjectName("historyGrade")
        grade_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        grade_label.setFont(app_font(9, QFont.Weight.Bold))
        right.addWidget(grade_label)
        layout.addLayout(right)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.result)
        super().mousePressEvent(event)


class HistoryView(QWidget):
    """History page focused on progress and next focus."""

    back_requested = pyqtSignal()
    result_selected = pyqtSignal(EvaluationResult)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_script_key = "regular"
        self.current_script_label = SCRIPT_LABELS[self.current_script_key]
        self.result_script_labels_by_id: dict[int, str] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        header = QFrame()
        header.setObjectName("pageHeader")
        header.setFixedHeight(34)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(2, 0, 2, 0)
        header_layout.setSpacing(8)

        self.btn_back = QPushButton("←")
        self.btn_back.setObjectName("headerIconButton")
        self.btn_back.setFixedSize(26, 26)
        self.btn_back.setFont(icon_font(13, QFont.Weight.Bold))
        self.btn_back.clicked.connect(self.back_requested.emit)
        header_layout.addWidget(self.btn_back)

        title = QLabel("练习记录")
        title.setObjectName("headlineTitle")
        title.setFont(display_font(17, QFont.Weight.Bold))
        header_layout.addWidget(title)

        self.script_badge = QLabel(self.current_script_label)
        self.script_badge.setObjectName("coachBadge")
        self.script_badge.setFont(app_font(7, QFont.Weight.Bold))
        header_layout.addWidget(self.script_badge)
        header_layout.addStretch()

        self.btn_refresh = QPushButton("↻")
        self.btn_refresh.setObjectName("headerIconButton")
        self.btn_refresh.setFixedSize(26, 26)
        self.btn_refresh.setFont(icon_font(13, QFont.Weight.Bold))
        self.btn_refresh.clicked.connect(self.refresh_data)
        header_layout.addWidget(self.btn_refresh)
        root.addWidget(header)

        self.summary_card = QFrame()
        self.summary_card.setObjectName("softCard")
        self.summary_card.setFixedHeight(70)
        summary_layout = QVBoxLayout(self.summary_card)
        summary_layout.setContentsMargins(12, 10, 12, 10)
        summary_layout.setSpacing(4)

        stats_row = QHBoxLayout()
        stats_row.setContentsMargins(0, 0, 0, 0)
        stats_row.setSpacing(14)

        self.total_value, total_block = self._build_stat_block("累计次数")
        stats_row.addLayout(total_block)

        self.average_value, average_block = self._build_stat_block("近 5 次均分")
        stats_row.addLayout(average_block)

        self.focus_value, focus_block = self._build_stat_block("当前关注")
        stats_row.addLayout(focus_block)
        summary_layout.addLayout(stats_row)

        self.progress_hint = QLabel("完成多次评测后，这里会告诉你当前的练习趋势。")
        self.progress_hint.setObjectName("sectionSubtitle")
        self.progress_hint.setFont(app_font(8))
        summary_layout.addWidget(self.progress_hint)
        root.addWidget(self.summary_card)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        root.addWidget(self.scroll_area, stretch=1)

        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(8)
        self.scroll_area.setWidget(self.list_container)

    def _build_stat_block(self, caption: str) -> tuple[QLabel, QVBoxLayout]:
        block = QVBoxLayout()
        block.setContentsMargins(0, 0, 0, 0)
        block.setSpacing(1)

        value = QLabel("--")
        value.setObjectName("statValue")
        value.setFont(display_font(13, QFont.Weight.Bold))
        block.addWidget(value)

        note = QLabel(caption)
        note.setObjectName("statCaption")
        note.setFont(app_font(8, QFont.Weight.Bold))
        block.addWidget(note)
        return value, block

    def refresh_data(self) -> None:
        self.scroll_area.verticalScrollBar().setValue(0)
        clear_layout(self.list_layout)

        records = database_service.get_all(limit=20)
        recent_records = records[:5]
        latest_result = records[0] if records else None
        best_score = max((record.total_score for record in records), default=0)
        recent_average = (
            sum(record.total_score for record in recent_records) / len(recent_records)
            if recent_records
            else None
        )

        focus_text = "--"
        if latest_result is not None:
            profile = latest_result.get_practice_profile()
            focus = profile.get("focus_dimension") if profile else None
            if focus:
                focus_text = focus["label"]

        self.total_value.setText(str(len(records)))
        self.average_value.setText("--" if recent_average is None else f"{recent_average:.1f}")
        self.focus_value.setText(focus_text)
        self.progress_hint.setText(self._build_progress_hint(records, best_score, focus_text))

        if not records:
            empty_card = QFrame()
            empty_card.setObjectName("softCard")
            empty_layout = QVBoxLayout(empty_card)
            empty_layout.setContentsMargins(16, 14, 16, 14)
            empty_layout.setSpacing(4)

            title = QLabel("还没有练习记录")
            title.setObjectName("sectionTitle")
            title.setFont(display_font(12, QFont.Weight.Bold))
            empty_layout.addWidget(title)

            body = QLabel("完成一次新的书法评测后，结果会自动出现在这里。")
            body.setObjectName("sectionSubtitle")
            body.setWordWrap(True)
            body.setFont(app_font(10))
            empty_layout.addWidget(body)

            self.list_layout.addWidget(empty_card)
            self.list_layout.addStretch()
            return

        for record in records:
            item = HistoryItem(record, self._script_label_for_result(record))
            item.clicked.connect(self.result_selected.emit)
            self.list_layout.addWidget(item)

        self.list_layout.addStretch()

    def _build_progress_hint(self, records: list[EvaluationResult], best_score: int, focus_text: str) -> str:
        if not records:
            return f"当前书体：{self.current_script_label}。完成多次评测后，这里会告诉你当前的练习趋势。"

        if len(records) == 1:
            return f"当前书体：{self.current_script_label}。当前最好分 {best_score}，建议继续围绕 {focus_text} 连续练 3 次。"

        latest_score = records[0].total_score
        previous_score = records[1].total_score
        delta = latest_score - previous_score

        if delta > 0:
            return f"当前书体：{self.current_script_label}。最近一次比上一张提升 {delta} 分，当前最好分 {best_score}。"
        if delta < 0:
            return f"当前书体：{self.current_script_label}。最近一次比上一张回落 {abs(delta)} 分，可回看 {focus_text}。"
        return f"当前书体：{self.current_script_label}。最近两张基本持平，当前最好分 {best_score}，继续稳定输出。"

    def set_current_script(self, script_key: str) -> None:
        if script_key not in SCRIPT_LABELS:
            return
        self.current_script_key = script_key
        self.current_script_label = SCRIPT_LABELS[script_key]
        self.script_badge.setText(self.current_script_label)

    def set_result_script_labels(self, result_script_labels_by_id: dict[int, str]) -> None:
        self.result_script_labels_by_id = dict(result_script_labels_by_id)

    def _script_label_for_result(self, result: EvaluationResult) -> str:
        if hasattr(result, "get_script_label"):
            return result.get_script_label()
        for attr_name in ("qt_script_label", "script_label", "script_name"):
            value = getattr(result, attr_name, None)
            if isinstance(value, str) and value:
                return value
        if result.id is not None and result.id in self.result_script_labels_by_id:
            return self.result_script_labels_by_id[result.id]
        return SCRIPT_LABELS["regular"]

    def set_compact_mode(self, compact: bool) -> None:
        del compact
