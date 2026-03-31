"""Result view for the single-chain OCR + ONNX evaluation flow."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from models.evaluation_result import EvaluationResult
from services.led_service import led_service
from services.speech_service import speech_service
from views.ui_theme import app_font, score_to_color, score_to_soft_color


class MetaCard(QFrame):
    """Small result metadata card."""

    def __init__(self, title: str, value: str, parent=None):
        super().__init__(parent)
        self.setObjectName("metricCard")
        self.setStyleSheet(
            f"QFrame#metricCard {{ background-color: {score_to_soft_color(78)}; border-radius: 20px; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setObjectName("mutedLabel")
        title_label.setFont(app_font(10))
        layout.addWidget(title_label)

        value_label = QLabel(value)
        value_label.setObjectName("sectionTitle")
        value_label.setWordWrap(True)
        value_label.setFont(app_font(15, QFont.Weight.Bold))
        layout.addWidget(value_label)


class ResultView(QWidget):
    """Evaluation result page."""

    back_requested = pyqtSignal()
    new_evaluation_requested = pyqtSignal()
    history_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.result: EvaluationResult | None = None
        self.compact_mode = False
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

        self.page_layout = QVBoxLayout(container)
        self.page_layout.setContentsMargins(4, 4, 4, 4)
        self.page_layout.setSpacing(14)

        summary_card = QFrame()
        summary_card.setObjectName("accentCard")
        summary_layout = QVBoxLayout(summary_card)
        summary_layout.setContentsMargins(22, 20, 22, 20)
        summary_layout.setSpacing(8)

        summary_hint = QLabel("本次成绩")
        summary_hint.setStyleSheet("color: #d7c4ae; font-size: 11px;")
        summary_layout.addWidget(summary_hint)

        self.total_score_label = QLabel("--")
        self.total_score_label.setObjectName("scoreNumber")
        self.total_score_label.setStyleSheet("color: #fff8f1;")
        summary_layout.addWidget(self.total_score_label)

        self.grade_label = QLabel("--")
        self.grade_label.setObjectName("scoreGrade")
        summary_layout.addWidget(self.grade_label)

        self.meta_primary = QLabel("识别汉字：--")
        self.meta_primary.setStyleSheet("color: #fff1e2; font-size: 12px;")
        summary_layout.addWidget(self.meta_primary)

        self.meta_secondary = QLabel("OCR 置信度：-")
        self.meta_secondary.setStyleSheet("color: #d7c4ae; font-size: 10px;")
        summary_layout.addWidget(self.meta_secondary)

        self.meta_time = QLabel("--")
        self.meta_time.setStyleSheet("color: #d7c4ae; font-size: 10px;")
        summary_layout.addWidget(self.meta_time)

        self.summary_badge = QLabel("自动评测中")
        self.summary_badge.setObjectName("successChip")
        summary_layout.addWidget(self.summary_badge)

        self.summary_card = summary_card
        self.summary_layout = summary_layout
        self.page_layout.addWidget(summary_card)

        insight_card = QFrame()
        insight_card.setObjectName("resultCard")
        insight_layout = QVBoxLayout(insight_card)
        insight_layout.setContentsMargins(18, 18, 18, 18)
        insight_layout.setSpacing(8)

        insight_title = QLabel("自动评测说明")
        insight_title.setObjectName("sectionTitle")
        insight_title.setFont(app_font(16, QFont.Weight.Bold))
        insight_layout.addWidget(insight_title)

        insight_hint = QLabel("当前版本固定使用预处理、官方 OCR 与 ONNX 评分模型的一条链路。")
        insight_hint.setObjectName("sectionSubtitle")
        insight_hint.setWordWrap(True)
        insight_layout.addWidget(insight_hint)

        self.insight_copy = QLabel("等待评测结果...")
        self.insight_copy.setObjectName("sectionSubtitle")
        self.insight_copy.setWordWrap(True)
        self.insight_copy.setFont(app_font(11))
        insight_layout.addWidget(self.insight_copy)

        self.page_layout.addWidget(insight_card)

        meta_card = QFrame()
        meta_card.setObjectName("resultCard")
        meta_layout = QVBoxLayout(meta_card)
        meta_layout.setContentsMargins(18, 18, 18, 18)
        meta_layout.setSpacing(10)

        meta_title = QLabel("结果摘要")
        meta_title.setObjectName("sectionTitle")
        meta_title.setFont(app_font(16, QFont.Weight.Bold))
        meta_layout.addWidget(meta_title)

        self.meta_grid = QGridLayout()
        self.meta_grid.setHorizontalSpacing(12)
        self.meta_grid.setVerticalSpacing(12)
        meta_layout.addLayout(self.meta_grid)
        self.page_layout.addWidget(meta_card)

        confidence_card = QFrame()
        confidence_card.setObjectName("resultCard")
        confidence_layout = QVBoxLayout(confidence_card)
        confidence_layout.setContentsMargins(18, 18, 18, 18)
        confidence_layout.setSpacing(10)

        confidence_title = QLabel("可信度读数")
        confidence_title.setObjectName("sectionTitle")
        confidence_title.setFont(app_font(16, QFont.Weight.Bold))
        confidence_layout.addWidget(confidence_title)

        self.ocr_confidence_label = QLabel("OCR 置信度 0%")
        self.ocr_confidence_label.setObjectName("mutedLabel")
        confidence_layout.addWidget(self.ocr_confidence_label)

        self.ocr_progress = QProgressBar()
        self.ocr_progress.setRange(0, 100)
        confidence_layout.addWidget(self.ocr_progress)

        self.quality_confidence_label = QLabel("质量置信度 0%")
        self.quality_confidence_label.setObjectName("mutedLabel")
        confidence_layout.addWidget(self.quality_confidence_label)

        self.quality_progress = QProgressBar()
        self.quality_progress.setRange(0, 100)
        confidence_layout.addWidget(self.quality_progress)

        self.confidence_hint = QLabel("这两个数值越高，说明自动识别和评分越稳定，更适合直接展示给评委。")
        self.confidence_hint.setObjectName("sectionSubtitle")
        self.confidence_hint.setWordWrap(True)
        confidence_layout.addWidget(self.confidence_hint)
        self.page_layout.addWidget(confidence_card)

        feedback_card = QFrame()
        feedback_card.setObjectName("feedbackCard")
        feedback_layout = QVBoxLayout(feedback_card)
        feedback_layout.setContentsMargins(18, 18, 18, 18)
        feedback_layout.setSpacing(10)

        feedback_title = QLabel("评测建议")
        feedback_title.setObjectName("sectionTitle")
        feedback_title.setFont(app_font(16, QFont.Weight.Bold))
        feedback_layout.addWidget(feedback_title)

        self.feedback_label = QLabel("")
        self.feedback_label.setObjectName("sectionSubtitle")
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setFont(app_font(11))
        feedback_layout.addWidget(self.feedback_label)
        self.page_layout.addWidget(feedback_card)

        actions_card = QFrame()
        actions_card.setObjectName("panelCard")
        self.actions_layout = QGridLayout(actions_card)
        self.actions_layout.setContentsMargins(18, 18, 18, 18)
        self.actions_layout.setHorizontalSpacing(10)
        self.actions_layout.setVerticalSpacing(10)

        self.btn_home = QPushButton("返回首页")
        self.btn_home.setObjectName("secondaryButton")
        self.btn_home.setMinimumHeight(50)
        self.btn_home.clicked.connect(self.back_requested.emit)

        self.btn_history = QPushButton("查看历史")
        self.btn_history.setObjectName("secondaryButton")
        self.btn_history.setMinimumHeight(50)
        self.btn_history.clicked.connect(self.history_requested.emit)

        self.btn_speak = QPushButton("语音播报")
        self.btn_speak.setObjectName("ghostButton")
        self.btn_speak.setMinimumHeight(50)
        self.btn_speak.clicked.connect(self._on_speak)

        self.btn_new = QPushButton("再次评测")
        self.btn_new.setObjectName("primaryButton")
        self.btn_new.setMinimumHeight(50)
        self.btn_new.clicked.connect(self.new_evaluation_requested.emit)
        self._apply_actions_layout()

        self.page_layout.addWidget(actions_card)
        self.page_layout.addStretch()

    def set_result(self, result: EvaluationResult) -> None:
        self.result = result
        self.scroll_area.verticalScrollBar().setValue(0)
        self._update_display()

    def _update_display(self) -> None:
        if self.result is None:
            return

        score = self.result.total_score
        score_color = score_to_color(score)

        self.total_score_label.setText(str(score))
        score_font_size = 48 if self.compact_mode else 64
        self.total_score_label.setStyleSheet(f"color: #fff8f1; font-size: {score_font_size}px; font-weight: 800;")
        self.grade_label.setText(self.result.get_grade())
        self.grade_label.setStyleSheet(f"color: {score_color}; font-size: 16px; font-weight: 700;")
        self.summary_badge.setText(f"{self.result.get_grade()} / {self.result.character_name or '未识别'}")

        self.meta_primary.setText(f"识别汉字：{self.result.character_name or '未识别'}")
        self.meta_secondary.setText(
            f"OCR 置信度：{round((self.result.ocr_confidence or 0.0) * 100)}% / "
            f"质量置信度：{round((self.result.quality_confidence or 0.0) * 100)}%"
        )
        self.meta_time.setText(f"评测时间：{self.result.timestamp.strftime('%Y-%m-%d %H:%M')}")
        ocr_value = round((self.result.ocr_confidence or 0.0) * 100)
        quality_value = round((self.result.quality_confidence or 0.0) * 100)
        self.ocr_confidence_label.setText(f"OCR 置信度 {ocr_value}%")
        self.quality_confidence_label.setText(f"质量置信度 {quality_value}%")
        self.ocr_progress.setValue(ocr_value)
        self.quality_progress.setValue(quality_value)
        self.insight_copy.setText(
            f"系统自动识别当前字为“{self.result.character_name or '未识别'}”，"
            f"再直接输出 {self.result.total_score} 分和“{self.result.get_grade()}”等级。"
        )

        while self.meta_grid.count():
            item = self.meta_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        cards = [
            ("自动识别", self.result.character_name or "未识别"),
            ("OCR 置信度", f"{round((self.result.ocr_confidence or 0.0) * 100)}%"),
            ("质量等级", self.result.get_grade()),
            ("质量置信度", f"{round((self.result.quality_confidence or 0.0) * 100)}%"),
        ]
        columns = 1 if self.compact_mode else 2
        for index, (title, value) in enumerate(cards):
            self.meta_grid.addWidget(MetaCard(title, value), index // columns, index % columns)

        self.feedback_label.setText(self.result.feedback)
        led_service.show_score(score)

    def _on_speak(self) -> None:
        if self.result is not None:
            speech_service.speak_score(self.result.total_score, self.result.feedback)

    def _apply_actions_layout(self) -> None:
        while self.actions_layout.count():
            item = self.actions_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

        buttons = [self.btn_home, self.btn_history, self.btn_speak, self.btn_new]
        if self.compact_mode:
            for row, button in enumerate(buttons):
                self.actions_layout.addWidget(button, row, 0)
        else:
            positions = [(0, 0), (0, 1), (1, 0), (1, 1)]
            for button, (row, column) in zip(buttons, positions):
                self.actions_layout.addWidget(button, row, column)

    def set_compact_mode(self, compact: bool) -> None:
        self.compact_mode = compact
        self.page_layout.setSpacing(10 if compact else 14)
        self.summary_layout.setContentsMargins(16 if compact else 22, 16 if compact else 20, 16 if compact else 22, 16 if compact else 20)

        for button in (self.btn_home, self.btn_history, self.btn_speak, self.btn_new):
            button.setMinimumHeight(42 if compact else 50)

        self._apply_actions_layout()
        if self.result is not None:
            self._update_display()
