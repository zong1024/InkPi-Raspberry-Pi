"""
InkPi 书法评测系统 - 首页视图
适配3.5寸屏幕 (480x320)
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
from config import IS_RASPBERRY_PI


class RecentCard(QFrame):
    """最近记录卡片 - 紧凑版"""
    
    def __init__(self, result: EvaluationResult, parent=None):
        super().__init__(parent)
        self.result = result
        self._init_ui()
        
    def _init_ui(self):
        self.setObjectName("recentCard")
        self.setFixedHeight(50)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        
        # 分数
        score_label = QLabel(f"{self.result.total_score}")
        score_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        score_label.setStyleSheet(f"color: {self.result.get_color()};")
        score_label.setFixedWidth(40)
        layout.addWidget(score_label)
        
        # 信息
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        if self.result.character_name:
            title = f"{self.result.character_name}"
        else:
            title = "书法评测"
        title_label = QLabel(title)
        title_label.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        info_layout.addWidget(title_label)
        
        # 时间
        time_str = self.result.timestamp.strftime("%m-%d %H:%M")
        time_label = QLabel(time_str)
        time_label.setFont(QFont("Microsoft YaHei", 8))
        time_label.setStyleSheet("color: #666;")
        info_layout.addWidget(time_label)
        
        layout.addLayout(info_layout)
        layout.addStretch()
        
        # 等级
        grade_label = QLabel(self.result.get_grade())
        grade_label.setFont(QFont("Microsoft YaHei", 10))
        grade_label.setStyleSheet(f"color: {self.result.get_color()};")
        layout.addWidget(grade_label)


class HomeView(QWidget):
    """首页视图 - 适配3.5寸屏幕"""
    
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
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 欢迎区域 - 紧凑
        welcome_frame = QFrame()
        welcome_frame.setObjectName("welcomeFrame")
        welcome_layout = QVBoxLayout(welcome_frame)
        welcome_layout.setSpacing(5)
        
        title = QLabel("InkPi 书法评测")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_layout.addWidget(title)
        
        subtitle = QLabel("拍照评测您的书法作品")
        subtitle.setFont(QFont("Microsoft YaHei", 9))
        subtitle.setStyleSheet("color: #666;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_layout.addWidget(subtitle)
        
        layout.addWidget(welcome_frame)
        
        # 开始按钮 - 大按钮方便触摸
        self.btn_start = QPushButton("📷 开始评测")
        self.btn_start.setObjectName("primaryButton")
        self.btn_start.setFont(QFont("Microsoft YaHei", 12))
        self.btn_start.setFixedHeight(50)
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.clicked.connect(self.start_evaluation.emit)
        layout.addWidget(self.btn_start)
        
        # 最近记录区域
        recent_header = QHBoxLayout()
        recent_title = QLabel("最近评测")
        recent_title.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        recent_header.addWidget(recent_title)
        
        recent_header.addStretch()
        
        btn_view_all = QPushButton("更多>")
        btn_view_all.setObjectName("textButton")
        btn_view_all.setFont(QFont("Microsoft YaHei", 9))
        btn_view_all.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_view_all.clicked.connect(self.view_history.emit)
        recent_header.addWidget(btn_view_all)
        
        layout.addLayout(recent_header)
        
        # 最近记录列表
        self.recent_container = QWidget()
        self.recent_layout = QVBoxLayout(self.recent_container)
        self.recent_layout.setSpacing(5)
        layout.addWidget(self.recent_container)
        
        layout.addStretch()
        
    def _load_recent_records(self):
        """加载最近记录"""
        # 清除现有记录
        while self.recent_layout.count():
            item = self.recent_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        # 获取最近3条记录（小屏幕显示更少）
        records = database_service.get_recent(3)
        
        if not records:
            empty_label = QLabel("暂无评测记录")
            empty_label.setStyleSheet("color: #999;")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_label.setFont(QFont("Microsoft YaHei", 9))
            self.recent_layout.addWidget(empty_label)
            return
            
        for record in records:
            card = RecentCard(record)
            self.recent_layout.addWidget(card)
            
    def refresh(self):
        """刷新数据"""
        self._load_recent_records()