"""Home view tuned for the 480x320 InkPi product screen."""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from models.evaluation_result import EvaluationResult
from services.database_service import database_service
from views.ui_theme import app_font, display_font, icon_font

sys.path.insert(0, str(Path(__file__).parent.parent))


class HomeView(QWidget):
    """Landing page that makes the device learning loop explicit."""

    start_evaluation = pyqtSignal()
    view_history = pyqtSignal()
    recent_selected = pyqtSignal(EvaluationResult)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.latest_result: EvaluationResult | None = None
        self._init_ui()
        self.refresh()

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        header = QFrame()
        header.setObjectName("pageHeader")
        header.setFixedHeight(34)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(2, 0, 2, 0)
        header_layout.setSpacing(8)

        brand = QLabel("InkPi")
        brand.setObjectName("brandTitle")
        brand.setFont(display_font(20, QFont.Weight.Bold))
        header_layout.addWidget(brand)

        header_layout.addStretch()

        self.btn_refresh = self._build_icon_button("↻")
        self.btn_refresh.clicked.connect(self.refresh)
        header_layout.addWidget(self.btn_refresh)
        root.addWidget(header)

        hero_card = QFrame()
        hero_card.setObjectName("heroCard")
        hero_card.setFixedHeight(72)
        hero_layout = QHBoxLayout(hero_card)
        hero_layout.setContentsMargins(14, 10, 14, 10)
        hero_layout.setSpacing(12)

        brand_block = QVBoxLayout()
        brand_block.setContentsMargins(0, 0, 0, 0)
        brand_block.setSpacing(0)
        brand_block.addStretch()

        hero_logo = QLabel("InkPi")
        hero_logo.setObjectName("brandAccent")
        hero_logo.setFont(display_font(24, QFont.Weight.Bold))
        brand_block.addWidget(hero_logo)

        hero_subtitle = QLabel("DEVICE PRACTICE LOOP")
        hero_subtitle.setObjectName("miniLabel")
        hero_subtitle.setFont(app_font(8, QFont.Weight.Bold))
        brand_block.addWidget(hero_subtitle)
        brand_block.addStretch()
        hero_layout.addLayout(brand_block, stretch=1)

        self.btn_start = QPushButton("开始新一轮")
        self.btn_start.setObjectName("primaryButton")
        self.btn_start.setFixedSize(160, 40)
        self.btn_start.setFont(display_font(12, QFont.Weight.Bold))
        self.btn_start.clicked.connect(self.start_evaluation.emit)
        hero_layout.addWidget(self.btn_start, alignment=Qt.AlignmentFlag.AlignCenter)
        root.addWidget(hero_card)

        loop_card = QFrame()
        loop_card.setObjectName("actionCard")
        loop_card.setFixedHeight(36)
        loop_layout = QHBoxLayout(loop_card)
        loop_layout.setContentsMargins(12, 8, 12, 8)
        loop_layout.setSpacing(8)

        loop_title = QLabel("练习闭环")
        loop_title.setObjectName("miniLabel")
        loop_title.setFont(app_font(8, QFont.Weight.Bold))
        loop_layout.addWidget(loop_title)

        self.loop_hint = QLabel("拍一张 -> 看懂强弱项 -> 按建议再练")
        self.loop_hint.setObjectName("hintText")
        self.loop_hint.setFont(app_font(9, QFont.Weight.Bold))
        loop_layout.addWidget(self.loop_hint, stretch=1)
        root.addWidget(loop_card)

        self.latest_card = QFrame()
        self.latest_card.setObjectName("feedbackCard")
        self.latest_card.setFixedHeight(102)
        latest_layout = QVBoxLayout(self.latest_card)
        latest_layout.setContentsMargins(12, 8, 12, 8)
        latest_layout.setSpacing(2)

        latest_header = QHBoxLayout()
        latest_header.setContentsMargins(0, 0, 0, 0)
        latest_header.setSpacing(6)

        self.latest_title = QLabel("准备开始")
        self.latest_title.setObjectName("sectionTitle")
        self.latest_title.setFont(app_font(10, QFont.Weight.Bold))
        latest_header.addWidget(self.latest_title)

        latest_header.addStretch()

        self.latest_badge = QLabel("等待首张作品")
        self.latest_badge.setObjectName("coachBadge")
        self.latest_badge.setFont(app_font(8, QFont.Weight.Bold))
        latest_header.addWidget(self.latest_badge)
        latest_layout.addLayout(latest_header)

        self.latest_meta = QLabel("先完成一次单字评测，结果页会告诉你下一步怎么练。")
        self.latest_meta.setObjectName("hintText")
        self.latest_meta.setFont(app_font(9, QFont.Weight.Bold))
        latest_layout.addWidget(self.latest_meta)

        self.practice_hint = QLabel("本轮会给出强项、待提升项和下一轮建议。")
        self.practice_hint.setObjectName("sectionSubtitle")
        self.practice_hint.setWordWrap(True)
        self.practice_hint.setFixedHeight(24)
        self.practice_hint.setFont(app_font(8))
        latest_layout.addWidget(self.practice_hint)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(8)

        self.btn_review_latest = QPushButton("立即开始")
        self.btn_review_latest.setObjectName("primaryButton")
        self.btn_review_latest.setFixedSize(176, 30)
        self.btn_review_latest.setFont(app_font(9, QFont.Weight.Bold))
        self.btn_review_latest.clicked.connect(self._open_latest_or_start)
        action_row.addWidget(self.btn_review_latest)

        self.btn_history = QPushButton("历史记录")
        self.btn_history.setObjectName("ghostButton")
        self.btn_history.setFixedSize(136, 30)
        self.btn_history.setFont(app_font(9, QFont.Weight.Bold))
        self.btn_history.clicked.connect(self.view_history.emit)
        action_row.addWidget(self.btn_history)
        latest_layout.addLayout(action_row)
        root.addWidget(self.latest_card)

        root.addStretch()

    def _build_icon_button(self, symbol: str) -> QPushButton:
        button = QPushButton(symbol)
        button.setObjectName("headerIconButton")
        button.setFixedSize(26, 26)
        button.setFont(icon_font(13, QFont.Weight.Bold))
        return button

    def refresh(self) -> None:
        recent_records = database_service.get_recent(5)
        self.latest_result = recent_records[0] if recent_records else None

        if self.latest_result is None:
            self.latest_title.setText("第一次上手")
            self.latest_badge.setText("等待首张作品")
            self.latest_badge.setStyleSheet("")
            self.latest_meta.setText("先拍一张单字作品，结果页会告诉你下一轮怎么练。")
            self.practice_hint.setText("你会看到强项、待提升项和下一轮建议。")
            self.btn_review_latest.setText("立即开始")
            return

        result = self.latest_result
        profile = result.get_practice_profile()
        focus = profile.get("focus_dimension") if profile else None
        keep = profile.get("best_dimension") if profile else None
        recent_average = sum(item.total_score for item in recent_records[:3]) / max(1, len(recent_records[:3]))
        char_text = result.character_name or "未识别"

        self.latest_title.setText("继续上次练习")
        self.latest_badge.setText(f"{result.total_score} 分")
        self.latest_badge.setStyleSheet(
            f"color: {result.get_color()}; background-color: #F4ECE1; border-radius: 11px; padding: 3px 10px;"
        )
        self.latest_meta.setText(
            f"最近一张：{char_text} · {result.timestamp.strftime('%m-%d %H:%M')}"
        )

        if focus:
            focus_text = f"优先提升：{focus['label']} {focus['score']} 分"
        else:
            focus_text = "优先提升：进入结果页查看完整建议"

        if keep:
            keep_text = f"继续保持：{keep['label']} {keep['score']} 分 · 近 3 次均分 {recent_average:.1f}"
        else:
            keep_text = f"近 3 次均分 {recent_average:.1f}，继续观察波动"

        self.practice_hint.setText(f"{focus_text}\n{keep_text}")

        self.btn_review_latest.setText("查看上次建议")

    def _open_latest_or_start(self) -> None:
        if self.latest_result is not None:
            self.recent_selected.emit(self.latest_result)
            return
        self.start_evaluation.emit()

    def set_compact_mode(self, compact: bool) -> None:
        del compact
