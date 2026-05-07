"""Result view for the single-chain OCR + ONNX evaluation flow."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from models.evaluation_result import DIMENSION_LABELS, DIMENSION_ORDER, EvaluationResult
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
        self.dimension_compact_labels: dict[str, QLabel] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(5)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        self.score_card = QFrame()
        self.score_card.setObjectName("scoreCard")
        self.score_card.setFixedHeight(76)
        score_layout = QVBoxLayout(self.score_card)
        score_layout.setContentsMargins(10, 5, 10, 5)
        score_layout.setSpacing(1)

        title = QLabel("TOTAL")
        title.setObjectName("miniLabel")
        score_layout.addWidget(title)

        self.total_score_label = QLabel("--")
        self.total_score_label.setObjectName("scoreNumber")
        self.total_score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.total_score_label.setFont(app_font(28, QFont.Weight.Bold))
        score_layout.addWidget(self.total_score_label)

        self.grade_label = QLabel("--")
        self.grade_label.setObjectName("scoreGrade")
        self.grade_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.grade_label.setFont(app_font(10, QFont.Weight.Bold))
        score_layout.addWidget(self.grade_label)

        self.feedback_short = QLabel("等待评测")
        self.feedback_short.setObjectName("sectionSubtitle")
        self.feedback_short.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.feedback_short.setWordWrap(True)
        self.feedback_short.setFont(app_font(10))
        score_layout.addWidget(self.feedback_short)

        top_row.addWidget(self.score_card, stretch=4)

        self.right_card = QFrame()
        self.right_card.setObjectName("resultCard")
        self.right_card.setFixedHeight(76)
        right_layout = QVBoxLayout(self.right_card)
        right_layout.setContentsMargins(10, 7, 10, 7)
        right_layout.setSpacing(3)

        self.result_title = QLabel("Evaluation Result")
        self.result_title.setObjectName("sectionTitle")
        self.result_title.setFont(app_font(12, QFont.Weight.Bold))
        right_layout.addWidget(self.result_title)

        self.meta_label = QLabel("识别字 / 时间 / 置信度")
        self.meta_label.setObjectName("mutedLabel")
        self.meta_label.setWordWrap(True)
        self.meta_label.setFont(app_font(9))
        right_layout.addWidget(self.meta_label)

        for key in DIMENSION_ORDER:
            bar = DimensionBar(DIMENSION_LABELS[key])
            self.dimension_bars[key] = bar
            right_layout.addWidget(bar)

        top_row.addWidget(self.right_card, stretch=6)
        root.addLayout(top_row)

        self.summary_card = QFrame()
        self.summary_card.setObjectName("softCard")
        self.summary_card.setFixedHeight(74)
        summary_layout = QVBoxLayout(self.summary_card)
        summary_layout.setContentsMargins(10, 6, 10, 6)
        summary_layout.setSpacing(4)

        summary_title = QLabel("评价摘要")
        summary_title.setObjectName("sectionTitle")
        summary_title.setFont(app_font(10, QFont.Weight.Bold))
        summary_layout.addWidget(summary_title)

        compact_grid = QGridLayout()
        compact_grid.setHorizontalSpacing(6)
        compact_grid.setVerticalSpacing(4)
        for index, key in enumerate(DIMENSION_ORDER):
            label = QLabel(f"{DIMENSION_LABELS[key]} --")
            label.setObjectName("pillLabel")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFont(app_font(9, QFont.Weight.Bold))
            self.dimension_compact_labels[key] = label
            compact_grid.addWidget(label, index // 2, index % 2)
        summary_layout.addLayout(compact_grid)

        self.dimension_summary = QLabel("新结果会显示最强项与待提升项。")
        self.dimension_summary.setObjectName("sectionSubtitle")
        self.dimension_summary.setWordWrap(True)
        self.dimension_summary.setFont(app_font(9))
        self.dimension_summary.setVisible(False)
        summary_layout.addWidget(self.dimension_summary)

        self.feedback_label = QLabel("")
        self.feedback_label.setObjectName("mutedLabel")
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setFont(app_font(9))
        summary_layout.addWidget(self.feedback_label)
        root.addWidget(self.summary_card)

        actions = QGridLayout()
        actions.setHorizontalSpacing(6)
        actions.setVerticalSpacing(0)

        self.btn_new = QPushButton("再测")
        self.btn_new.setObjectName("primaryButton")
        self.btn_new.setFixedHeight(32)
        self.btn_new.clicked.connect(self.new_evaluation_requested.emit)
        actions.addWidget(self.btn_new, 0, 0)

        self.btn_speak = QPushButton("播报")
        self.btn_speak.setObjectName("ghostButton")
        self.btn_speak.setFixedHeight(32)
        self.btn_speak.clicked.connect(self._on_speak)
        actions.addWidget(self.btn_speak, 0, 1)

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
            f"{result.get_calligraphy_style_label()}  |  "
            f"{result.timestamp.strftime('%m-%d %H:%M')}  |  "
            f"OCR {round((result.ocr_confidence or 0.0) * 100)}%"
        )
        self.feedback_short.setText(result.feedback[:18] + ("..." if len(result.feedback) > 18 else ""))
        self.feedback_label.setText(result.feedback)

        dimension_items = {item["key"]: item["score"] for item in result.get_dimension_items()}
        for key, bar in self.dimension_bars.items():
            bar.set_score(dimension_items.get(key))
        for key, label in self.dimension_compact_labels.items():
            score = dimension_items.get(key)
            label.setText(f"{DIMENSION_LABELS[key]} {score if score is not None else '--'}")

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
        self.total_score_label.setFont(app_font(28 if compact else 40, QFont.Weight.Bold))
        self.feedback_short.setVisible(not compact)
        self.feedback_label.setVisible(not compact)
        for bar in self.dimension_bars.values():
            bar.setVisible(not compact)
        for label in self.dimension_compact_labels.values():
            label.setVisible(compact)
        self.dimension_summary.setVisible(not compact)
