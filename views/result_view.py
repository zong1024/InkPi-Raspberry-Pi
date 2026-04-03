"""Result view for the single-chain OCR + ONNX evaluation flow."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from models.evaluation_result import DIMENSION_LABELS, EvaluationResult
from services.led_service import led_service
from services.speech_service import speech_service
from views.ui_theme import app_font


class DimensionBar(QFrame):
    """Simple progress row for a dimension score."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("dimensionBarCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("sectionTitle")
        self.title_label.setFont(app_font(11, QFont.Weight.Bold))
        top_row.addWidget(self.title_label)

        top_row.addStretch()

        self.value_label = QLabel("--")
        self.value_label.setObjectName("accentText")
        self.value_label.setFont(app_font(11, QFont.Weight.Bold))
        top_row.addWidget(self.value_label)
        layout.addLayout(top_row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        layout.addWidget(self.progress)

    def set_score(self, score: int | None) -> None:
        if score is None:
            self.value_label.setText("--")
            self.progress.setValue(0)
            return
        self.value_label.setText(str(score))
        self.progress.setValue(score)


class ResultView(QWidget):
    """Evaluation result page."""

    back_requested = pyqtSignal()
    new_evaluation_requested = pyqtSignal()
    history_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.result: EvaluationResult | None = None
        self.compact_mode = False
        self.dimension_bars: dict[str, DimensionBar] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(2, 2, 2, 2)
        root.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        self.score_card = QFrame()
        self.score_card.setObjectName("scoreCard")
        score_layout = QVBoxLayout(self.score_card)
        score_layout.setContentsMargins(18, 16, 18, 16)
        score_layout.setSpacing(8)

        title = QLabel("TOTAL")
        title.setObjectName("miniLabel")
        score_layout.addWidget(title)

        self.total_score_label = QLabel("--")
        self.total_score_label.setObjectName("scoreNumber")
        self.total_score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.total_score_label.setFont(app_font(44, QFont.Weight.Bold))
        score_layout.addWidget(self.total_score_label)

        self.grade_label = QLabel("--")
        self.grade_label.setObjectName("scoreGrade")
        self.grade_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_layout.addWidget(self.grade_label)

        self.feedback_short = QLabel("等待评测")
        self.feedback_short.setObjectName("sectionSubtitle")
        self.feedback_short.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.feedback_short.setWordWrap(True)
        self.feedback_short.setFont(app_font(10))
        score_layout.addWidget(self.feedback_short)

        top_row.addWidget(self.score_card, stretch=4)

        right_card = QFrame()
        right_card.setObjectName("resultCard")
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(14, 14, 14, 14)
        right_layout.setSpacing(8)

        self.result_title = QLabel("Evaluation Result")
        self.result_title.setObjectName("sectionTitle")
        self.result_title.setFont(app_font(13, QFont.Weight.Bold))
        right_layout.addWidget(self.result_title)

        self.meta_label = QLabel("识别字 / 时间 / 置信度")
        self.meta_label.setObjectName("mutedLabel")
        self.meta_label.setWordWrap(True)
        self.meta_label.setFont(app_font(10))
        right_layout.addWidget(self.meta_label)

        for key in ("structure", "stroke", "integrity", "stability"):
            bar = DimensionBar(DIMENSION_LABELS[key])
            self.dimension_bars[key] = bar
            right_layout.addWidget(bar)

        top_row.addWidget(right_card, stretch=6)
        root.addLayout(top_row)

        self.summary_card = QFrame()
        self.summary_card.setObjectName("softCard")
        summary_layout = QVBoxLayout(self.summary_card)
        summary_layout.setContentsMargins(14, 12, 14, 12)
        summary_layout.setSpacing(6)

        summary_title = QLabel("评价摘要")
        summary_title.setObjectName("sectionTitle")
        summary_layout.addWidget(summary_title)

        self.dimension_summary = QLabel("新结果会显示最强项与待提升项。")
        self.dimension_summary.setObjectName("sectionSubtitle")
        self.dimension_summary.setWordWrap(True)
        self.dimension_summary.setFont(app_font(10))
        summary_layout.addWidget(self.dimension_summary)

        self.feedback_label = QLabel("")
        self.feedback_label.setObjectName("mutedLabel")
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setFont(app_font(10))
        summary_layout.addWidget(self.feedback_label)
        root.addWidget(self.summary_card)

        actions = QGridLayout()
        actions.setHorizontalSpacing(10)
        actions.setVerticalSpacing(8)

        self.btn_history = QPushButton("查看历史")
        self.btn_history.setObjectName("secondaryButton")
        self.btn_history.setMinimumHeight(44)
        self.btn_history.clicked.connect(self.history_requested.emit)
        actions.addWidget(self.btn_history, 0, 0)

        self.btn_home = QPushButton("返回首页")
        self.btn_home.setObjectName("primaryButton")
        self.btn_home.setMinimumHeight(44)
        self.btn_home.clicked.connect(self.back_requested.emit)
        actions.addWidget(self.btn_home, 0, 1)

        self.btn_new = QPushButton("再次评测")
        self.btn_new.setObjectName("secondaryButton")
        self.btn_new.setMinimumHeight(40)
        self.btn_new.clicked.connect(self.new_evaluation_requested.emit)
        actions.addWidget(self.btn_new, 1, 0)

        self.btn_speak = QPushButton("语音播报")
        self.btn_speak.setObjectName("ghostButton")
        self.btn_speak.setMinimumHeight(40)
        self.btn_speak.clicked.connect(self._on_speak)
        actions.addWidget(self.btn_speak, 1, 1)

        root.addLayout(actions)

    def set_result(self, result: EvaluationResult) -> None:
        self.result = result
        self._update_display()

    def _update_display(self) -> None:
        if self.result is None:
            return

        result = self.result
        self.total_score_label.setText(str(result.total_score))
        self.grade_label.setText(result.get_grade())
        self.result_title.setText(result.character_name or "未识别")
        self.meta_label.setText(
            f"{result.timestamp.strftime('%Y-%m-%d %H:%M')}  |  OCR {round((result.ocr_confidence or 0.0) * 100)}%"
        )
        self.feedback_short.setText(result.feedback[:18] + ("..." if len(result.feedback) > 18 else ""))
        self.feedback_label.setText(result.feedback)

        dimension_items = {item["key"]: item["score"] for item in result.get_dimension_items()}
        for key, bar in self.dimension_bars.items():
            bar.set_score(dimension_items.get(key))

        summary = result.get_dimension_summary()
        if summary:
            self.dimension_summary.setText(
                f"最强项：{summary['best']['label']} {summary['best']['score']}  |  "
                f"待提升：{summary['weakest']['label']} {summary['weakest']['score']}"
            )
        else:
            self.dimension_summary.setText("老记录暂无四维评分。")

        led_service.show_score(result.total_score)

    def _on_speak(self) -> None:
        if self.result is not None:
            speech_service.speak_score(self.result.total_score, self.result.feedback)

    def set_compact_mode(self, compact: bool) -> None:
        self.compact_mode = compact
        self.total_score_label.setFont(app_font(40 if compact else 44, QFont.Weight.Bold))
