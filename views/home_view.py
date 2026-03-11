"""
InkPi 书法评测系统 - 首页视图
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QScrollArea, QGridLayout
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from services.database_service import database_service
from models.evaluation_result import EvaluationResult


class RecentCard(QFrame):
    """最近记录卡片"""
    
    def __init__(self, result: EvaluationResult, parent=None):
        super().__init__(parent)
        self.result = result
        self._init_ui()
        
    def _init_ui(self):
        self.setObjectName("recentCard")
        self.setFixedHeight(80)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        
        # 分数
        score_label = QLabel(f"{self.result.total_score}")
        score_label.setObjectName("scoreLabel")
        score_label.setFont(QFont("Arial", 28, QFont.Weight.Bold))
        score_label.setStyleSheet(f"color: {self.result.get_color()};")
        score_label.setFixedWidth(60)
        layout.addWidget(score_label)
        
        # 信息
        info_layout = QVBoxLayout()
        
        if self.result.character_name:
            title = f"字符: {self.result.character_name}"
        else:
            title = "书法评测"
        title_label = QLabel(title)
        title_label.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        info_layout.addWidget(title_label)
        
        # 四维分数
        scores_str = " | ".join([f"{k}: {v}" for k, v in self.result.detail_scores.items()])
        scores_label = QLabel(scores_str)
        scores_label.setFont(QFont("Microsoft YaHei", 9))
        scores_label.setStyleSheet("color: #666;")
        info_layout.addWidget(scores_label)
        
        layout.addLayout(info_layout)
        layout.addStretch()
        
        # 等级
        grade_label = QLabel(self.result.get_grade())
        grade_label.setFont(QFont("Microsoft YaHei", 12))
        grade_label.setStyleSheet(f"color: {self.result.get_color()};")
        layout.addWidget(grade_label)


class HomeView(QWidget):
    """首页视图"""
    
    # 信号
    start_evaluation = pyqtSignal()  # 开始评测
    view_history = pyqtSignal()      # 查看历史
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._load_recent_records()
        
    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(20)
        
        # 欢迎区域
        welcome_frame = QFrame()
        welcome_frame.setObjectName("welcomeFrame")
        welcome_layout = QVBoxLayout(welcome_frame)
        
        title = QLabel("欢迎使用 InkPi 书法评测系统")
        title.setFont(QFont("Microsoft YaHei", 24, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_layout.addWidget(title)
        
        subtitle = QLabel("拍照上传您的书法作品，获取智能评测与改进建议")
        subtitle.setFont(QFont("Microsoft YaHei", 12))
        subtitle.setStyleSheet("color: #666;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_layout.addWidget(subtitle)
        
        layout.addWidget(welcome_frame)
        
        # 开始按钮
        self.btn_start = QPushButton("📷 开始评测")
        self.btn_start.setObjectName("primaryButton")
        self.btn_start.setFont(QFont("Microsoft YaHei", 16))
        self.btn_start.setFixedHeight(60)
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.clicked.connect(self.start_evaluation.emit)
        layout.addWidget(self.btn_start)
        
        # 功能介绍
        features_layout = QHBoxLayout()
        features = [
            ("🎯", "智能评测", "四维度精准评分"),
            ("📊", "趋势分析", "追踪学习进度"),
            ("🔊", "语音反馈", "实时播报结果"),
        ]
        
        for icon, title, desc in features:
            card = QFrame()
            card.setObjectName("featureCard")
            card_layout = QVBoxLayout(card)
            card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            icon_label = QLabel(icon)
            icon_label.setFont(QFont("Segoe UI Emoji", 32))
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(icon_label)
            
            title_label = QLabel(title)
            title_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(title_label)
            
            desc_label = QLabel(desc)
            desc_label.setStyleSheet("color: #666;")
            desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(desc_label)
            
            features_layout.addWidget(card)
            
        layout.addLayout(features_layout)
        
        # 最近记录区域
        recent_header = QHBoxLayout()
        recent_title = QLabel("最近评测")
        recent_title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        recent_header.addWidget(recent_title)
        
        recent_header.addStretch()
        
        btn_view_all = QPushButton("查看全部 →")
        btn_viewAll.setObjectName("textButton")
        btn_viewAll.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_viewAll.clicked.connect(self.view_history.emit)
        recent_header.addWidget(btn_viewAll)
        
        layout.addLayout(recent_header)
        
        # 最近记录列表
        self.recent_container = QWidget()
        self.recent_layout = QVBoxLayout(self.recent_container)
        self.recent_layout.setSpacing(10)
        layout.addWidget(self.recent_container)
        
        layout.addStretch()
        
    def _load_recent_records(self):
        """加载最近记录"""
        # 清除现有记录
        while self.recent_layout.count():
            item = self.recent_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        # 获取最近记录
        records = database_service.get_recent(5)
        
        if not records:
            empty_label = QLabel("暂无评测记录，开始您的第一次评测吧！")
            empty_label.setStyleSheet("color: #999;")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.recent_layout.addWidget(empty_label)
            return
            
        for record in records:
            card = RecentCard(record)
            self.recent_layout.addWidget(card)
            
    def refresh(self):
        """刷新数据"""
        self._load_recent_records()