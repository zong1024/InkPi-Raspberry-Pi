"""
InkPi 书法评测系统 - 结果视图

显示评测结果，包括总分、雷达图、反馈文字
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QGridLayout
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import numpy as np

from models.evaluation_result import EvaluationResult
from services.speech_service import speech_service
from config import UI_CONFIG


class RadarChart(FigureCanvas):
    """雷达图组件"""
    
    def __init__(self, parent=None, size=300):
        self.fig = Figure(figsize=(size/100, size/100), dpi=100)
        self.fig.patch.set_facecolor('#f5f5f5')
        super().__init__(self.fig)
        self.setParent(parent)
        
        self.ax = self.fig.add_subplot(111, projection='polar')
        self.ax.set_facecolor('#f5f5f5')
        
        self._setup_chart()
        
    def _setup_chart(self):
        """设置图表"""
        self.ax.set_theta_offset(np.pi / 2)
        self.ax.set_theta_direction(-1)
        
        # 设置刻度
        self.ax.set_ylim(0, 100)
        self.ax.set_yticks([20, 40, 60, 80, 100])
        self.ax.set_yticklabels(['20', '40', '60', '80', '100'], fontsize=8, color='#666')
        
    def plot_scores(self, scores: dict):
        """绘制评分雷达图"""
        self.ax.clear()
        self._setup_chart()
        
        labels = list(scores.keys())
        values = list(scores.values())
        
        # 闭合多边形
        num_vars = len(labels)
        angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
        values_closed = values + values[:1]
        angles_closed = angles + angles[:1]
        labels_closed = labels + labels[:1]
        
        # 绘制雷达图
        self.ax.plot(angles_closed, values_closed, 'o-', linewidth=2, color='#2196F3')
        self.ax.fill(angles_closed, values_closed, alpha=0.25, color='#2196F3')
        
        # 设置标签
        self.ax.set_xticks(angles)
        self.ax.set_xticklabels(labels, fontsize=10, fontweight='bold')
        
        # 显示数值
        for angle, value in zip(angles, values):
            self.ax.annotate(
                str(value),
                xy=(angle, value),
                xytext=(angle, value + 8),
                ha='center',
                fontsize=9,
                color='#333'
            )
        
        self.ax.grid(True, linestyle='--', alpha=0.7)
        self.draw()


class ScoreCard(QFrame):
    """评分卡片"""
    
    def __init__(self, dimension: str, score: int, parent=None):
        super().__init__(parent)
        self.dimension = dimension
        self.score = score
        self._init_ui()
        
    def _init_ui(self):
        self.setObjectName("scoreCard")
        self.setFixedSize(100, 70)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 维度名称
        dim_label = QLabel(self.dimension)
        dim_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dim_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(dim_label)
        
        # 分数
        score_label = QLabel(str(self.score))
        score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 根据分数设置颜色
        if self.score >= 80:
            color = "#4CAF50"
        elif self.score >= 60:
            color = "#FF9800"
        else:
            color = "#F44336"
            
        score_label.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: bold;")
        layout.addWidget(score_label)


class ResultView(QWidget):
    """结果视图"""
    
    # 信号
    back_requested = pyqtSignal()              # 返回首页
    new_evaluation_requested = pyqtSignal()    # 新建评测
    history_requested = pyqtSignal()           # 查看历史
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.result: EvaluationResult = None
        self._init_ui()
        
    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(20)
        
        # 顶部信息
        top_layout = QHBoxLayout()
        
        # 总分区域
        score_frame = QFrame()
        score_frame.setObjectName("totalScoreFrame")
        score_layout = QVBoxLayout(score_frame)
        score_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        total_title = QLabel("总分")
        total_title.setFont(QFont("Microsoft YaHei", 14))
        total_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_layout.addWidget(total_title)
        
        self.total_score_label = QLabel("--")
        self.total_score_label.setFont(QFont("Arial", 56, QFont.Weight.Bold))
        self.total_score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_layout.addWidget(self.total_score_label)
        
        self.grade_label = QLabel("--")
        self.grade_label.setFont(QFont("Microsoft YaHei", 16))
        self.grade_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_layout.addWidget(self.grade_label)
        
        top_layout.addWidget(score_frame)
        
        # 雷达图区域
        radar_frame = QFrame()
        radar_frame.setObjectName("radarFrame")
        radar_layout = QVBoxLayout(radar_frame)
        radar_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        radar_title = QLabel("四维评分")
        radar_title.setFont(QFont("Microsoft YaHei", 12))
        radar_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        radar_layout.addWidget(radar_title)
        
        self.radar_chart = RadarChart(size=UI_CONFIG["radar_chart_size"])
        radar_layout.addWidget(self.radar_chart)
        
        top_layout.addWidget(radar_frame)
        
        layout.addLayout(top_layout)
        
        # 四维分数卡片
        self.scores_layout = QHBoxLayout()
        self.scores_layout.setSpacing(15)
        layout.addLayout(self.scores_layout)
        
        # 反馈区域
        feedback_frame = QFrame()
        feedback_frame.setObjectName("feedbackFrame")
        feedback_layout = QVBoxLayout(feedback_frame)
        
        feedback_title = QLabel("评测反馈")
        feedback_title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        feedback_layout.addWidget(feedback_title)
        
        self.feedback_label = QLabel("")
        self.feedback_label.setFont(QFont("Microsoft YaHei", 11))
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setStyleSheet("color: #333; padding: 10px;")
        feedback_layout.addWidget(self.feedback_label)
        
        layout.addWidget(feedback_frame)
        
        layout.addStretch()
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_home = QPushButton("返回首页")
        self.btn_home.setObjectName("secondaryButton")
        self.btn_home.setFont(QFont("Microsoft YaHei", 11))
        self.btn_home.setFixedSize(120, 45)
        self.btn_home.clicked.connect(self.back_requested.emit)
        btn_layout.addWidget(self.btn_home)
        
        btn_layout.addSpacing(15)
        
        self.btn_speak = QPushButton("🔊 重播")
        self.btn_speak.setObjectName("secondaryButton")
        self.btn_speak.setFont(QFont("Microsoft YaHei", 11))
        self.btn_speak.setFixedSize(100, 45)
        self.btn_speak.clicked.connect(self._on_speak)
        btn_layout.addWidget(self.btn_speak)
        
        btn_layout.addSpacing(15)
        
        self.btn_new = QPushButton("再次评测")
        self.btn_new.setObjectName("primaryButton")
        self.btn_new.setFont(QFont("Microsoft YaHei", 11))
        self.btn_new.setFixedSize(120, 45)
        self.btn_new.clicked.connect(self.new_evaluation_requested.emit)
        btn_layout.addWidget(self.btn_new)
        
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        
    def set_result(self, result: EvaluationResult):
        """设置评测结果"""
        self.result = result
        self._update_display()
        
    def _update_display(self):
        """更新显示"""
        if self.result is None:
            return
            
        # 更新总分
        self.total_score_label.setText(str(self.result.total_score))
        self.total_score_label.setStyleSheet(
            f"color: {self.result.get_color()};"
        )
        
        # 更新等级
        self.grade_label.setText(self.result.get_grade())
        self.grade_label.setStyleSheet(f"color: {self.result.get_color()};")
        
        # 更新雷达图
        self.radar_chart.plot_scores(self.result.detail_scores)
        
        # 更新四维分数卡片
        # 清除现有卡片
        while self.scores_layout.count():
            item = self.scores_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        # 添加新卡片
        for dim, score in self.result.detail_scores.items():
            card = ScoreCard(dim, score)
            self.scores_layout.addWidget(card)
            
        self.scores_layout.addStretch()
        
        # 更新反馈
        self.feedback_label.setText(self.result.feedback)
        
    def _on_speak(self):
        """语音播报"""
        if self.result:
            speech_service.speak_score(
                self.result.total_score, 
                self.result.feedback
            )