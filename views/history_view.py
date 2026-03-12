"""
InkPi 书法评测系统 - 历史视图
适配3.5寸屏幕 (480x320)
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QScrollArea, QListWidget,
    QListWidgetItem, QMessageBox, QComboBox, QDateEdit,
    QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QDate
from PyQt6.QtGui import QFont

from models.evaluation_result import EvaluationResult
from services.database_service import database_service


class HistoryItem(QFrame):
    """历史记录项 - 紧凑版"""
    
    clicked = pyqtSignal(EvaluationResult)
    delete_requested = pyqtSignal(int)
    
    def __init__(self, result: EvaluationResult, parent=None):
        super().__init__(parent)
        self.result = result
        self._init_ui()
        
    def _init_ui(self):
        self.setObjectName("historyItem")
        self.setFixedHeight(45)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        
        # 分数
        score_label = QLabel(f"{self.result.total_score}")
        score_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        score_label.setStyleSheet(f"color: {self.result.get_color()};")
        score_label.setFixedWidth(35)
        score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(score_label)
        
        # 信息
        info_layout = QVBoxLayout()
        info_layout.setSpacing(1)
        
        # 时间
        time_str = self.result.timestamp.strftime("%m-%d %H:%M")
        time_label = QLabel(time_str)
        time_label.setFont(QFont("Microsoft YaHei", 8))
        time_label.setStyleSheet("color: #666;")
        info_layout.addWidget(time_label)
        
        # 四维分数 - 简短
        scores_str = " ".join([f"{v}" for v in self.result.detail_scores.values()])
        scores_label = QLabel(scores_str)
        scores_label.setFont(QFont("Microsoft YaHei", 8))
        scores_label.setStyleSheet("color: #999;")
        info_layout.addWidget(scores_label)
        
        layout.addLayout(info_layout)
        layout.addStretch()
        
        # 等级
        grade_label = QLabel(self.result.get_grade())
        grade_label.setFont(QFont("Microsoft YaHei", 9))
        grade_label.setStyleSheet(f"color: {self.result.get_color()};")
        layout.addWidget(grade_label)
        
        # 删除按钮
        btn_delete = QPushButton("×")
        btn_delete.setObjectName("deleteButton")
        btn_delete.setFixedSize(20, 20)
        btn_delete.setFont(QFont("Arial", 12))
        btn_delete.clicked.connect(lambda: self.delete_requested.emit(self.result.id))
        layout.addWidget(btn_delete)
        
    def mousePressEvent(self, event):
        """点击事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.result)


class HistoryView(QWidget):
    """历史视图 - 适配3.5寸屏幕"""
    
    # 信号
    back_requested = pyqtSignal()
    result_selected = pyqtSignal(EvaluationResult)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        
    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        # 顶部栏 - 紧凑
        top_layout = QHBoxLayout()
        top_layout.setSpacing(5)
        
        btn_back = QPushButton("← 返回")
        btn_back.setObjectName("textButton")
        btn_back.setFont(QFont("Microsoft YaHei", 9))
        btn_back.clicked.connect(self.back_requested.emit)
        top_layout.addWidget(btn_back)
        
        top_layout.addStretch()
        
        # 统计信息 - 简短
        self.stats_label = QLabel("")
        self.stats_label.setFont(QFont("Microsoft YaHei", 8))
        self.stats_label.setStyleSheet("color: #666;")
        top_layout.addWidget(self.stats_label)
        
        layout.addLayout(top_layout)
        
        # 筛选区域 - 简化
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(5)
        
        self.date_combo = QComboBox()
        self.date_combo.addItems(["全部", "今天", "7天", "30天"])
        self.date_combo.setFont(QFont("Microsoft YaHei", 8))
        self.date_combo.setFixedWidth(60)
        self.date_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.date_combo)
        
        filter_layout.addStretch()
        
        btn_refresh = QPushButton("刷新")
        btn_refresh.setObjectName("secondaryButton")
        btn_refresh.setFont(QFont("Microsoft YaHei", 8))
        btn_refresh.setFixedSize(50, 25)
        btn_refresh.clicked.connect(self.refresh_data)
        filter_layout.addWidget(btn_refresh)
        
        layout.addLayout(filter_layout)
        
        # 历史记录列表
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; }")
        
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.list_layout.setSpacing(5)
        
        self.scroll_area.setWidget(self.list_container)
        layout.addWidget(self.scroll_area)
        
    def refresh_data(self):
        """刷新数据"""
        self._load_stats()
        self._load_records()
        
    def _load_stats(self):
        """加载统计信息"""
        stats = database_service.get_statistics()
        self.stats_label.setText(
            f"共{stats['total_count']}次 | 均分{stats['average_score']}"
        )
        
    def _load_records(self):
        """加载历史记录"""
        # 清除现有记录
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        # 根据筛选条件获取记录
        filter_idx = self.date_combo.currentIndex()
        
        if filter_idx == 0:  # 全部
            records = database_service.get_all(limit=20)
        else:
            now = datetime.now()
            if filter_idx == 1:  # 今天
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif filter_idx == 2:  # 最近7天
                start_date = now - timedelta(days=7)
            else:  # 最近30天
                start_date = now - timedelta(days=30)
                
            records = database_service.get_by_date_range(start_date, now)
            
        if not records:
            empty_label = QLabel("暂无评测记录")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_label.setStyleSheet("color: #999; padding: 20px;")
            empty_label.setFont(QFont("Microsoft YaHei", 9))
            self.list_layout.addWidget(empty_label)
            return
            
        for record in records:
            item = HistoryItem(record)
            item.clicked.connect(self.result_selected.emit)
            item.delete_requested.connect(self._on_delete_record)
            self.list_layout.addWidget(item)
            
    def _on_filter_changed(self):
        """筛选条件改变"""
        self._load_records()
        
    def _on_delete_record(self, record_id: int):
        """删除记录"""
        reply = QMessageBox.question(
            self,
            "确认删除",
            "确定要删除这条记录吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            database_service.delete(record_id)
            self.refresh_data()