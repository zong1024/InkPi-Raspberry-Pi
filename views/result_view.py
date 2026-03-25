"""Result view with a lightweight custom chart."""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
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
from views.ui_theme import THEME, app_font, clear_layout, score_to_color, score_to_soft_color


class RadarChart(QWidget):
    """Native radar chart widget for four-dimensional scores."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scores: dict[str, int] = {}
        self.setMinimumSize(220, 220)

    def set_scores(self, scores: dict[str, int]) -> None:
        self.scores = scores or {}
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)

        labels = list(self.scores.keys()) or ["结构", "笔画", "平衡", "韵律"]
        values = [self.scores.get(label, 0) for label in labels]

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bounds = self.rect().adjusted(18, 18, -18, -24)
        center = QPointF(bounds.center())
        radius = min(bounds.width(), bounds.height()) * 0.34

        grid_pen = QPen(QColor(THEME["line"]), 1)
        axis_pen = QPen(QColor(THEME["muted"]), 1)
        fill_brush = QColor(THEME["accent"])
        fill_brush.setAlpha(90)
        outline_pen = QPen(QColor(THEME["accent"]), 2)

        count = len(labels)
        angles = [(-math.pi / 2) + (2 * math.pi * index / count) for index in range(count)]

        for step in (0.25, 0.5, 0.75, 1.0):
            ring = QPolygonF()
            for angle in angles:
                ring.append(
                    QPointF(
                        center.x() + math.cos(angle) * radius * step,
                        center.y() + math.sin(angle) * radius * step,
                    )
                )
            painter.setPen(grid_pen)
            painter.drawPolygon(ring)

        for angle, label in zip(angles, labels):
            axis_end = QPointF(
                center.x() + math.cos(angle) * radius,
                center.y() + math.sin(angle) * radius,
            )
            painter.setPen(axis_pen)
            painter.drawLine(center, axis_end)

            label_point = QPointF(
                center.x() + math.cos(angle) * (radius + 24),
                center.y() + math.sin(angle) * (radius + 24),
            )
            text_rect = QRectF(label_point.x() - 24, label_point.y() - 10, 48, 20)
            painter.setPen(QColor(THEME["ink"]))
            painter.setFont(app_font(10, QFont.Weight.Bold))
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, label)

        polygon = QPolygonF()
        for angle, value in zip(angles, values):
            polygon.append(
                QPointF(
                    center.x() + math.cos(angle) * radius * max(0.0, min(value, 100)) / 100,
                    center.y() + math.sin(angle) * radius * max(0.0, min(value, 100)) / 100,
                )
            )

        painter.setPen(outline_pen)
        painter.setBrush(fill_brush)
        painter.drawPolygon(polygon)

        painter.setPen(QPen(QColor(THEME["gold"]), 2))
        painter.setBrush(QColor(THEME["surface"]))
        for point in polygon:
            painter.drawEllipse(point, 4, 4)

        painter.end()


class DimensionCard(QFrame):
    """Dimension score card."""

    def __init__(self, title: str, score: int, parent=None):
        super().__init__(parent)
        self.setObjectName("metricCard")
        self.setStyleSheet(
            f"QFrame#metricCard {{ background-color: {score_to_soft_color(score)}; "
            f"border: 1px solid {THEME['line']}; border-radius: 20px; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setObjectName("mutedLabel")
        title_label.setFont(app_font(10))
        layout.addWidget(title_label)

        score_label = QLabel(str(score))
        score_label.setObjectName("dimensionScore")
        score_label.setStyleSheet(f"color: {score_to_color(score)};")
        layout.addWidget(score_label)

        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(score)
        bar.setTextVisible(False)
        bar.setStyleSheet(
            "QProgressBar { background-color: rgba(255,255,255,0.6); }"
            f"QProgressBar::chunk {{ background-color: {score_to_color(score)}; border-radius: 8px; }}"
        )
        layout.addWidget(bar)


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

        top_row = QHBoxLayout()
        top_row.setSpacing(14)

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
        self.grade_label.setStyleSheet("color: #f6d8b0;")
        summary_layout.addWidget(self.grade_label)

        self.meta_primary = QLabel("识别结果：-")
        self.meta_primary.setStyleSheet("color: #fff1e2; font-size: 12px;")
        summary_layout.addWidget(self.meta_primary)

        self.meta_secondary = QLabel("书体风格：-")
        self.meta_secondary.setStyleSheet("color: #d7c4ae; font-size: 10px;")
        summary_layout.addWidget(self.meta_secondary)

        self.meta_time = QLabel("--")
        self.meta_time.setStyleSheet("color: #d7c4ae; font-size: 10px;")
        summary_layout.addWidget(self.meta_time)

        top_row.addWidget(summary_card, stretch=3)

        radar_card = QFrame()
        radar_card.setObjectName("resultCard")
        radar_layout = QVBoxLayout(radar_card)
        radar_layout.setContentsMargins(18, 18, 18, 18)
        radar_layout.setSpacing(8)

        radar_title = QLabel("四维结构图")
        radar_title.setObjectName("sectionTitle")
        radar_title.setFont(app_font(16, QFont.Weight.Bold))
        radar_layout.addWidget(radar_title)

        radar_hint = QLabel("结构、笔画、平衡与韵律会共同决定总分。")
        radar_hint.setObjectName("sectionSubtitle")
        radar_hint.setWordWrap(True)
        radar_layout.addWidget(radar_hint)

        self.radar_chart = RadarChart()
        radar_layout.addWidget(self.radar_chart, alignment=Qt.AlignmentFlag.AlignCenter)

        top_row.addWidget(radar_card, stretch=4)
        layout.addLayout(top_row)

        dimensions_card = QFrame()
        dimensions_card.setObjectName("resultCard")
        dimensions_layout = QVBoxLayout(dimensions_card)
        dimensions_layout.setContentsMargins(18, 18, 18, 18)
        dimensions_layout.setSpacing(10)

        dimensions_title = QLabel("分项表现")
        dimensions_title.setObjectName("sectionTitle")
        dimensions_title.setFont(app_font(16, QFont.Weight.Bold))
        dimensions_layout.addWidget(dimensions_title)

        self.dimension_grid = QGridLayout()
        self.dimension_grid.setHorizontalSpacing(12)
        self.dimension_grid.setVerticalSpacing(12)
        dimensions_layout.addLayout(self.dimension_grid)
        layout.addWidget(dimensions_card)

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

        self.meta_primary.setText(f"识别结果：{self.result.character_name or '未识别'}")
        self.meta_secondary.setText(f"书体风格：{self.result.style or '未分类'}")
        self.meta_time.setText(f"评测时间：{self.result.timestamp.strftime('%Y-%m-%d %H:%M')}")

        self.radar_chart.set_scores(self.result.detail_scores)

        clear_layout(self.dimension_grid)

        for index, (name, value) in enumerate(self.result.detail_scores.items()):
            card = DimensionCard(name, value)
            self.dimension_grid.addWidget(card, index // 2, index % 2)

        self.feedback_label.setText(self.result.feedback)
        led_service.show_score(score)

    def _on_speak(self) -> None:
        if self.result is not None:
            speech_service.speak_score(self.result.total_score, self.result.feedback)
