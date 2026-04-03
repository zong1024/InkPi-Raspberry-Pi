"""Result view for the single-chain OCR + ONNX evaluation flow."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from models.evaluation_result import DIMENSION_LABELS, EvaluationResult
from services.led_service import led_service
from services.speech_service import speech_service
from views.ui_theme import app_font


class DimensionRow(QWidget):
    """Compact score row inside the dimension panel."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("sectionTitle")
        self.title_label.setFont(app_font(11, QFont.Weight.Bold))
        top.addWidget(self.title_label)
        top.addStretch()

        self.value_label = QLabel("--")
        self.value_label.setObjectName("sectionTitle")
        self.value_label.setFont(app_font(11, QFont.Weight.Bold))
        top.addWidget(self.value_label)
        layout.addLayout(top)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)

    def set_score(self, score: int | None) -> None:
        if score is None:
            self.value_label.setText("--")
            self.progress.setValue(0)
            return
        self.value_label.setText(str(score))
        self.progress.setValue(score)


class ResultView(QWidget):
    """Evaluation result page matched to the provided reference structure."""

    back_requested = pyqtSignal()
    new_evaluation_requested = pyqtSignal()
    history_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.result: EvaluationResult | None = None
        self.dimension_rows: dict[str, DimensionRow] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        header = QFrame()
        header.setObjectName("pageHeader")
        header.setFixedHeight(38)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 6, 12, 6)
        header_layout.setSpacing(8)

        brand = QLabel("InkPi")
        brand.setObjectName("brandAccent")
        brand.setFont(app_font(16, QFont.Weight.Bold))
        header_layout.addWidget(brand)

        title = QLabel("EVALUATION RESULT")
        title.setObjectName("pageTitle")
        title.setFont(app_font(10, QFont.Weight.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.btn_share = QPushButton("↗")
        self.btn_share.setObjectName("headerIconButton")
        self.btn_share.setFixedSize(22, 22)
        self.btn_share.clicked.connect(self._on_speak)
        header_layout.addWidget(self.btn_share)

        self.btn_new = QPushButton("↓")
        self.btn_new.setObjectName("headerIconButton")
        self.btn_new.setFixedSize(22, 22)
        self.btn_new.clicked.connect(self.new_evaluation_requested.emit)
        header_layout.addWidget(self.btn_new)
        root.addWidget(header)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(10)

        self.score_card = QFrame()
        self.score_card.setObjectName("scoreCard")
        self.score_card.setFixedSize(150, 166)
        score_layout = QVBoxLayout(self.score_card)
        score_layout.setContentsMargins(14, 12, 14, 12)
        score_layout.setSpacing(3)

        total_label = QLabel("TOTAL")
        total_label.setObjectName("miniLabel")
        total_label.setFont(app_font(9, QFont.Weight.Bold))
        score_layout.addWidget(total_label)

        self.total_score_label = QLabel("--")
        self.total_score_label.setObjectName("scoreNumber")
        self.total_score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.total_score_label.setFont(app_font(48, QFont.Weight.Bold))
        score_layout.addWidget(self.total_score_label, stretch=1)

        self.grade_label = QLabel("--")
        self.grade_label.setObjectName("scoreGrade")
        self.grade_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.grade_label.setFont(app_font(16, QFont.Weight.Bold))
        self.grade_label.setFixedWidth(40)
        score_layout.addWidget(self.grade_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.feedback_short = QLabel("等待评测")
        self.feedback_short.setObjectName("sectionSubtitle")
        self.feedback_short.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.feedback_short.setFixedHeight(18)
        self.feedback_short.setFont(app_font(9))
        score_layout.addWidget(self.feedback_short)
        top_row.addWidget(self.score_card)

        metrics_panel = QFrame()
        metrics_panel.setObjectName("metricPanel")
        metrics_panel.setFixedHeight(166)
        metrics_layout = QVBoxLayout(metrics_panel)
        metrics_layout.setContentsMargins(12, 12, 12, 12)
        metrics_layout.setSpacing(7)

        for key in ("structure", "stroke", "integrity", "stability"):
            row = DimensionRow(DIMENSION_LABELS[key])
            self.dimension_rows[key] = row
            metrics_layout.addWidget(row)

        top_row.addWidget(metrics_panel, stretch=1)
        root.addLayout(top_row)

        self.summary_label = QLabel("最强项 / 待提升项")
        self.summary_label.setObjectName("sectionTitle")
        self.summary_label.setFixedHeight(18)
        self.summary_label.setFont(app_font(10, QFont.Weight.Bold))
        root.addWidget(self.summary_label)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(10)

        self.btn_history = QPushButton("查看历史")
        self.btn_history.setObjectName("ghostButton")
        self.btn_history.setFixedSize(128, 48)
        self.btn_history.setFont(app_font(11, QFont.Weight.Bold))
        self.btn_history.clicked.connect(self.history_requested.emit)
        button_row.addWidget(self.btn_history)

        self.btn_home = QPushButton("返回首页")
        self.btn_home.setObjectName("primaryButton")
        self.btn_home.setFixedSize(192, 48)
        self.btn_home.setFont(app_font(11, QFont.Weight.Bold))
        self.btn_home.clicked.connect(self.back_requested.emit)
        button_row.addWidget(self.btn_home)
        root.addLayout(button_row)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(6)

        self.footer_left = QLabel("Evaluation ID: --")
        self.footer_left.setObjectName("miniLabel")
        self.footer_left.setFont(app_font(8, QFont.Weight.Bold))
        footer.addWidget(self.footer_left)

        footer.addStretch()

        footer_right = QLabel("VERIFIED MASTER SCALE")
        footer_right.setObjectName("miniLabel")
        footer_right.setFont(app_font(8, QFont.Weight.Bold))
        footer.addWidget(footer_right)
        root.addLayout(footer)

    def set_result(self, result: EvaluationResult) -> None:
        self.result = result
        self._update_display()

    def _update_display(self) -> None:
        if self.result is None:
            return

        result = self.result
        self.total_score_label.setText(str(result.total_score))
        self.grade_label.setText(self._display_grade(result))

        self.feedback_short.setText(self._short_tip(result))

        dimension_items = {item["key"]: item["score"] for item in result.get_dimension_items()}
        for key, row in self.dimension_rows.items():
            row.set_score(dimension_items.get(key))

        summary = result.get_dimension_summary()
        if summary:
            self.summary_label.setText(
                f"最强项 {summary['best']['label']} {summary['best']['score']} · 待提升 {summary['weakest']['label']} {summary['weakest']['score']}"
            )
        else:
            self.summary_label.setText("当前记录暂无四维评分")

        self.footer_left.setText(f"Evaluation ID: {result.id or '--'}")
        led_service.show_score(result.total_score)

    def _display_grade(self, result: EvaluationResult) -> str:
        mapping = {"good": "A", "medium": "B", "bad": "C"}
        return mapping.get(result.quality_level, result.get_grade())

    def _clip(self, text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[: limit - 1] + "…"

    def _short_tip(self, result: EvaluationResult) -> str:
        default_tip = {
            "good": "书写流畅，结构端正",
            "medium": "整体成型，仍可提升",
            "bad": "基础偏弱，建议重练",
        }
        tip = default_tip.get(result.quality_level, "评测已完成")
        return self._clip(tip, 12)

    def _on_speak(self) -> None:
        if self.result is not None:
            speech_service.speak_score(self.result.total_score, self.result.feedback)

    def set_compact_mode(self, compact: bool) -> None:
        del compact
