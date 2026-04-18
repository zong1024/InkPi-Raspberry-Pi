"""Product-style result view for the InkPi evaluation flow."""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from models.evaluation_result import DIMENSION_LABELS, EvaluationResult
from services.led_service import led_service
from services.speech_service import speech_service
from views.ui_theme import app_font, display_font

sys.path.insert(0, str(Path(__file__).parent.parent))


class MetricChip(QFrame):
    """Compact metric chip for the four-dimension summary."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("metricChip")
        self.setFixedHeight(34)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(6)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("miniLabel")
        self.title_label.setFont(app_font(8, QFont.Weight.Bold))
        layout.addWidget(self.title_label)

        layout.addStretch()

        self.value_label = QLabel("--")
        self.value_label.setObjectName("bodyStrong")
        self.value_label.setFont(display_font(11, QFont.Weight.Bold))
        layout.addWidget(self.value_label)

    def set_score(self, score: int | None) -> None:
        self.value_label.setText("--" if score is None else str(score))


class ResultView(QWidget):
    """Evaluation result page focused on a coach-style learning loop."""

    back_requested = pyqtSignal()
    new_evaluation_requested = pyqtSignal()
    history_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.result: EvaluationResult | None = None
        self.metric_chips: dict[str, MetricChip] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        header = QFrame()
        header.setObjectName("pageHeader")
        header.setFixedHeight(34)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 4, 12, 4)
        header_layout.setSpacing(8)

        brand = QLabel("InkPi")
        brand.setObjectName("brandAccent")
        brand.setFont(display_font(16, QFont.Weight.Bold))
        header_layout.addWidget(brand)

        title = QLabel("LEARN FROM THIS SCORE")
        title.setObjectName("pageTitle")
        title.setFont(display_font(10, QFont.Weight.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.btn_speak = QPushButton("播")
        self.btn_speak.setObjectName("headerIconButton")
        self.btn_speak.setFixedSize(26, 24)
        self.btn_speak.setFont(app_font(10, QFont.Weight.Bold))
        self.btn_speak.clicked.connect(self._on_speak)
        header_layout.addWidget(self.btn_speak)

        self.btn_new = QPushButton("新")
        self.btn_new.setObjectName("headerIconButton")
        self.btn_new.setFixedSize(26, 24)
        self.btn_new.setFont(app_font(10, QFont.Weight.Bold))
        self.btn_new.clicked.connect(self.new_evaluation_requested.emit)
        header_layout.addWidget(self.btn_new)
        root.addWidget(header)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)

        self.score_card = QFrame()
        self.score_card.setObjectName("scoreCard")
        self.score_card.setFixedSize(146, 154)
        score_layout = QVBoxLayout(self.score_card)
        score_layout.setContentsMargins(14, 12, 14, 12)
        score_layout.setSpacing(4)

        total_label = QLabel("TOTAL SCORE")
        total_label.setObjectName("miniLabel")
        total_label.setFont(app_font(8, QFont.Weight.Bold))
        score_layout.addWidget(total_label)

        self.total_score_label = QLabel("--")
        self.total_score_label.setObjectName("scoreNumber")
        self.total_score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.total_score_label.setFont(display_font(44, QFont.Weight.Bold))
        score_layout.addWidget(self.total_score_label, stretch=1)

        self.grade_label = QLabel("--")
        self.grade_label.setObjectName("scoreGrade")
        self.grade_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.grade_label.setFont(display_font(15, QFont.Weight.Bold))
        self.grade_label.setFixedWidth(44)
        score_layout.addWidget(self.grade_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.feedback_short = QLabel("等待本轮评测")
        self.feedback_short.setObjectName("sectionSubtitle")
        self.feedback_short.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.feedback_short.setWordWrap(True)
        self.feedback_short.setFixedHeight(28)
        self.feedback_short.setFont(app_font(9))
        score_layout.addWidget(self.feedback_short)
        top_row.addWidget(self.score_card)

        self.coach_card = QFrame()
        self.coach_card.setObjectName("feedbackCard")
        self.coach_card.setFixedHeight(154)
        coach_layout = QVBoxLayout(self.coach_card)
        coach_layout.setContentsMargins(12, 10, 12, 10)
        coach_layout.setSpacing(6)

        coach_header = QHBoxLayout()
        coach_header.setContentsMargins(0, 0, 0, 0)
        coach_header.setSpacing(6)

        self.stage_badge = QLabel("练习阶段")
        self.stage_badge.setObjectName("coachBadge")
        self.stage_badge.setFont(app_font(8, QFont.Weight.Bold))
        coach_header.addWidget(self.stage_badge)

        coach_header.addStretch()

        self.character_meta = QLabel("识别字：--")
        self.character_meta.setObjectName("miniLabel")
        self.character_meta.setFont(app_font(8, QFont.Weight.Bold))
        coach_header.addWidget(self.character_meta)
        coach_layout.addLayout(coach_header)

        self.coach_prompt = QLabel("本轮结果会告诉你该保留什么，以及下一轮先改什么。")
        self.coach_prompt.setObjectName("bodyStrong")
        self.coach_prompt.setWordWrap(True)
        self.coach_prompt.setFixedHeight(30)
        self.coach_prompt.setFont(app_font(10, QFont.Weight.Bold))
        coach_layout.addWidget(self.coach_prompt)

        self.focus_line = QLabel("优先提升：--")
        self.focus_line.setObjectName("hintText")
        self.focus_line.setFont(app_font(9, QFont.Weight.Bold))
        coach_layout.addWidget(self.focus_line)

        self.keep_line = QLabel("继续保持：--")
        self.keep_line.setObjectName("hintText")
        self.keep_line.setFont(app_font(9, QFont.Weight.Bold))
        coach_layout.addWidget(self.keep_line)

        metric_grid = QGridLayout()
        metric_grid.setContentsMargins(0, 0, 0, 0)
        metric_grid.setHorizontalSpacing(6)
        metric_grid.setVerticalSpacing(6)
        for index, key in enumerate(("structure", "stroke", "integrity", "stability")):
            chip = MetricChip(DIMENSION_LABELS[key])
            self.metric_chips[key] = chip
            metric_grid.addWidget(chip, index // 2, index % 2)
        coach_layout.addLayout(metric_grid)
        top_row.addWidget(self.coach_card, stretch=1)
        root.addLayout(top_row)

        self.summary_card = QFrame()
        self.summary_card.setObjectName("resultSummaryCard")
        self.summary_card.setFixedHeight(54)
        summary_layout = QVBoxLayout(self.summary_card)
        summary_layout.setContentsMargins(12, 8, 12, 8)
        summary_layout.setSpacing(2)

        summary_title = QLabel("下一轮怎么练")
        summary_title.setObjectName("miniLabel")
        summary_title.setFont(app_font(8, QFont.Weight.Bold))
        summary_layout.addWidget(summary_title)

        self.action_primary = QLabel("1. 先完成一次稳定拍摄。")
        self.action_primary.setObjectName("actionLine")
        self.action_primary.setFont(app_font(9, QFont.Weight.Bold))
        summary_layout.addWidget(self.action_primary)

        self.action_secondary = QLabel("2. 再连续记录 3 次，比较变化。")
        self.action_secondary.setObjectName("sectionSubtitle")
        self.action_secondary.setWordWrap(True)
        self.action_secondary.setFont(app_font(8))
        summary_layout.addWidget(self.action_secondary)
        root.addWidget(self.summary_card)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(8)

        self.btn_history = QPushButton("历史")
        self.btn_history.setObjectName("ghostButton")
        self.btn_history.setFixedSize(88, 40)
        self.btn_history.setFont(app_font(10, QFont.Weight.Bold))
        self.btn_history.clicked.connect(self.history_requested.emit)
        button_row.addWidget(self.btn_history)

        self.btn_home = QPushButton("首页")
        self.btn_home.setObjectName("ghostButton")
        self.btn_home.setFixedSize(88, 40)
        self.btn_home.setFont(app_font(10, QFont.Weight.Bold))
        self.btn_home.clicked.connect(self.back_requested.emit)
        button_row.addWidget(self.btn_home)

        self.btn_retry = QPushButton("按建议再练一张")
        self.btn_retry.setObjectName("primaryButton")
        self.btn_retry.setFixedSize(236, 40)
        self.btn_retry.setFont(display_font(11, QFont.Weight.Bold))
        self.btn_retry.clicked.connect(self.new_evaluation_requested.emit)
        button_row.addWidget(self.btn_retry)
        root.addLayout(button_row)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(6)

        self.footer_left = QLabel("识别字：--")
        self.footer_left.setObjectName("miniLabel")
        self.footer_left.setFont(app_font(8, QFont.Weight.Bold))
        footer.addWidget(self.footer_left)

        footer.addStretch()

        self.footer_right = QLabel("结果页已生成下一练建议")
        self.footer_right.setObjectName("miniLabel")
        self.footer_right.setFont(app_font(8, QFont.Weight.Bold))
        footer.addWidget(self.footer_right)
        root.addLayout(footer)

    def set_result(self, result: EvaluationResult) -> None:
        self.result = result
        self._update_display()

    def _update_display(self) -> None:
        if self.result is None:
            return

        result = self.result
        profile = result.get_practice_profile()
        dimension_items = {item["key"]: item["score"] for item in result.get_dimension_items()}
        summary = result.get_dimension_summary()
        focus_dimension = profile.get("focus_dimension") if profile else None
        best_dimension = profile.get("best_dimension") if profile else None
        actions = (profile.get("next_actions") if profile else None) or []

        self.total_score_label.setText(str(result.total_score))
        self.grade_label.setText(result.get_grade())
        self.feedback_short.setText(self._short_tip(result, profile))
        self._apply_score_tone(result.get_color())

        for key, chip in self.metric_chips.items():
            chip.set_score(dimension_items.get(key))

        char_text = result.character_name or "未识别"
        timestamp_text = result.timestamp.strftime("%m-%d %H:%M")
        self.character_meta.setText(f"识别字：{char_text}")
        self.footer_left.setText(f"识别字：{char_text} · {timestamp_text}")

        if profile:
            self.stage_badge.setText(profile.get("stage_label", "练习阶段"))
            self.coach_prompt.setText(self._clip(profile.get("coach_prompt") or result.feedback, 34))
        else:
            self.stage_badge.setText("练习阶段")
            self.coach_prompt.setText("本轮先看清强项和待提升项，再进入下一张。")

        if focus_dimension:
            self.focus_line.setText(
                f"优先提升：{focus_dimension['label']} {focus_dimension['score']} 分"
            )
        elif summary:
            self.focus_line.setText(
                f"优先提升：{summary['weakest']['label']} {summary['weakest']['score']} 分"
            )
        else:
            self.focus_line.setText("优先提升：等待更多维度数据")

        if best_dimension:
            self.keep_line.setText(
                f"继续保持：{best_dimension['label']} {best_dimension['score']} 分"
            )
        elif summary:
            self.keep_line.setText(
                f"继续保持：{summary['best']['label']} {summary['best']['score']} 分"
            )
        else:
            self.keep_line.setText("继续保持：本轮已有可用基础")

        self.action_primary.setText(f"1. {self._clip(actions[0], 22)}" if actions else "1. 先连续记录 3 次，确认波动。")
        if len(actions) > 1:
            self.action_secondary.setText(f"2. {self._clip(actions[1], 28)}")
        elif result.feedback:
            self.action_secondary.setText(f"2. 模型提示：{self._clip(result.feedback, 24)}")
        else:
            self.action_secondary.setText("2. 看懂待提升项后，再进入下一张。")

        led_service.show_score(result.total_score)

    def _apply_score_tone(self, color: str) -> None:
        self.total_score_label.setStyleSheet(f"color: {color};")
        self.grade_label.setStyleSheet(
            f"color: #ffffff; background-color: {color}; border-radius: 18px; padding: 4px 12px;"
        )
        self.stage_badge.setStyleSheet(
            f"color: {color}; background-color: #F4ECE1; border-radius: 11px; padding: 3px 10px;"
        )

    def _clip(self, text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[: limit - 1] + "…"

    def _short_tip(self, result: EvaluationResult, profile: dict | None) -> str:
        if profile and profile.get("stage_goal"):
            return self._clip(profile["stage_goal"], 16)
        if result.feedback:
            return self._clip(result.feedback, 16)
        default_tip = {
            "good": "进入巩固细节阶段",
            "medium": "继续收紧结构和笔画",
            "bad": "先把作品拍清楚、写完整",
        }
        return default_tip.get(result.quality_level, "评测已完成")

    def _on_speak(self) -> None:
        if self.result is not None:
            speech_service.speak_score(self.result.total_score, self.result.feedback)

    def set_compact_mode(self, compact: bool) -> None:
        del compact
