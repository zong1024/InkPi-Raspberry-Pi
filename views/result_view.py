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
        layout.setSpacing(14)

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

        layout.addWidget(summary_card)

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

        layout.addWidget(insight_card)

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
        layout.addWidget(meta_card)

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
        layout.addWidget(feedback_card)

        actions_card = QFrame()
        actions_card.setObjectName("panelCard")
        actions_layout = QGridLayout(actions_card)
        actions_layout.setContentsMargins(18, 18, 18, 18)
        actions_layout.setHorizontalSpacing(10)
        actions_layout.setVerticalSpacing(10)

        self.btn_home = QPushButton("返回首页")
        self.btn_home.setObjectName("secondaryButton")
        self.btn_home.setMinimumHeight(50)
        self.btn_home.clicked.connect(self.back_requested.emit)
        actions_layout.addWidget(self.btn_home, 0, 0)

        self.btn_history = QPushButton("查看历史")
        self.btn_history.setObjectName("secondaryButton")
        self.btn_history.setMinimumHeight(50)
        self.btn_history.clicked.connect(self.history_requested.emit)
        actions_layout.addWidget(self.btn_history, 0, 1)

        self.btn_speak = QPushButton("语音播报")
        self.btn_speak.setObjectName("ghostButton")
        self.btn_speak.setMinimumHeight(50)
        self.btn_speak.clicked.connect(self._on_speak)
        actions_layout.addWidget(self.btn_speak, 1, 0)

        self.btn_new = QPushButton("再次评测")
        self.btn_new.setObjectName("primaryButton")
        self.btn_new.setMinimumHeight(50)
        self.btn_new.clicked.connect(self.new_evaluation_requested.emit)
        actions_layout.addWidget(self.btn_new, 1, 1)

        layout.addWidget(actions_card)
        layout.addStretch()

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
        self.total_score_label.setStyleSheet("color: #fff8f1; font-size: 64px; font-weight: 800;")
        self.grade_label.setText(self.result.get_grade())
        self.grade_label.setStyleSheet(f"color: {score_color}; font-size: 16px; font-weight: 700;")

        self.meta_primary.setText(f"识别汉字：{self.result.character_name or '未识别'}")
        self.meta_secondary.setText(
            f"OCR 置信度：{round((self.result.ocr_confidence or 0.0) * 100)}% / "
            f"质量置信度：{round((self.result.quality_confidence or 0.0) * 100)}%"
        )
        self.meta_time.setText(f"评测时间：{self.result.timestamp.strftime('%Y-%m-%d %H:%M')}")
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
        for index, (title, value) in enumerate(cards):
            self.meta_grid.addWidget(MetaCard(title, value), index // 2, index % 2)

        self.feedback_label.setText(self.result.feedback)
        led_service.show_score(score)

    def _on_speak(self) -> None:
        if self.result is not None:
            speech_service.speak_score(self.result.total_score, self.result.feedback)
