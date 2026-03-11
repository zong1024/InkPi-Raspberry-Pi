"""
InkPi 书法评测系统 - 历史视图

显示评测历史记录、趋势折线图、筛选删除功能
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

import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import numpy as np

from models.evaluation_result import EvaluationResult
from services.database_service import database_service


class TrendChart(FigureCanvas):
    """趋势折线图组件"""
    
    def __init__(self, parent=None):
        self.fig = Figure(figsize=(8, 3), dpi=100)
        self.fig.patch.set_facecolor('#ffffff')
        super().__init__(self.fig)
        self.setParent(parent)
        
        self.ax = self.fig.add_subplot(111)
        self._setup_chart()
        
    def _setup_chart(self):
        """设置图表"""
        self.ax.set_xlabel('评测次数', fontsize=9)
        self.ax.set_ylabel('分数', fontsize=9)
        self.ax.set_ylim(0, 100)
        self.ax.grid(True, linestyle='--', alpha=0.5)
        self.fig.tight_layout()
        
    def plot_trend(self, trend_data: list):
        """绘制趋势图"""
        self.ax.clear()
        self._setup_chart()
        
        if not trend_data:
            self.ax.text(0.5, 0.5, '暂无数据', ha='center', va='center',
                        fontsize=12, color='#999')
            self.draw()
            return
            
        # 提取数据
        x = range(1, len(trend_data) + 1)
        total_scores = [d['total_score'] for d in trend_data]
        
        # 绘制总分趋势线
        self.ax.plot(x, total_scores, 'o-', linewidth=2, color='#2196F3',
                     label='总分', markersize=6)
        
        # 添加平均线
        avg = np.mean(total_scores)
        self.ax.axhline(y=avg, color='#4CAF50', linestyle='--', 
                       label=f'平均: {avg:.1f}', alpha=0.7)
        
        self.ax.set_xticks(x)
        self.ax.legend(loc='lower right', fontsize=8)
        self.fig.tight_layout()
        self.draw()


class HistoryItem(QFrame):
    """历史记录项"""
    
    clicked = pyqtSignal(EvaluationResult)
    delete_requested = pyqtSignal(int)
    
    def __init__(self, result: EvaluationResult, parent=None):
        super().__init__(parent)
        self.result = result
        self._init_ui()
        
    def _init_ui(self):
        self.setObjectName("historyItem")
        self.setFixedHeight(80)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        
        # 分数
        score_label = QLabel(f"{self.result.total_score}")
        score_label.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        score_label.setStyleSheet(f"color: {self.result.get_color()};")
        score_label.setFixedWidth(60)
        score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(score_label)
        
        # 信息
        info_layout = QVBoxLayout()
        
        # 时间
        time_str = self.result.timestamp.strftime("%Y-%m-%d %H:%M")
        time_label = QLabel(time_str)
        time_label.setFont(QFont("Microsoft YaHei", 10))
        time_label.setStyleSheet("color: #999;")
        info_layout.addWidget(time_label)
        
        # 四维分数
        scores_str = " | ".join([f"{k}: {v}" for k, v in self.result.detail_scores.items()])
        scores_label = QLabel(scores_str)
        scores_label.setFont(QFont("Microsoft YaHei", 9))
        scores_label.setStyleSheet("color: #666;")
        info_layout.addWidget(scores_label)
        
        # 反馈预览
        feedback_preview = self.result.feedback[:30] + "..." if len(self.result.feedback) > 30 else self.result.feedback
        feedback_label = QLabel(feedback_preview)
        feedback_label.setFont(QFont("Microsoft YaHei", 9))
        feedback_label.setStyleSheet("color: #999;")
        info_layout.addWidget(feedback_label)
        
        layout.addLayout(info_layout)
        layout.addStretch()
        
        # 等级
        grade_label = QLabel(self.result.get_grade())
        grade_label.setFont(QFont("Microsoft YaHei", 12))
        grade_label.setStyleSheet(f"color: {self.result.get_color()};")
        layout.addWidget(grade_label)
        
        # 删除按钮
        btn_delete = QPushButton("×")
        btn_delete.setObjectName("deleteButton")
        btn_delete.setFixedSize(24, 24)
        btn_delete.setFont(QFont("Arial", 14))
        btn_delete.clicked.connect(lambda: self.delete_requested.emit(self.result.id))
        layout.addWidget(btn_delete)
        
    def mousePressEvent(self, event):
        """点击事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.result)


class HistoryView(QWidget):
    """历史视图"""
    
    # 信号
    back_requested = pyqtSignal()
    result_selected = pyqtSignal(EvaluationResult)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        
    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(15)
        
        # 顶部栏
        top_layout = QHBoxLayout()
        
        btn_back = QPushButton("← 返回")
        btn_back.setObjectName("textButton")
        btn_back.clicked.connect(self.back_requested.emit)
        top_layout.addWidget(btn_back)
        
        top_layout.addStretch()
        
        # 统计信息
        self.stats_label = QLabel("")
        self.stats_label.setFont(QFont("Microsoft YaHei", 11))
        self.stats_label.setStyleSheet("color: #666;")
        top_layout.addWidget(self.stats_label)
        
        layout.addLayout(top_layout)
        
        # 趋势图区域
        trend_group = QGroupBox("分数趋势")
        trend_layout = QVBoxLayout(trend_group)
        
        self.trend_chart = TrendChart()
        trend_layout.addWidget(self.trend_chart)
        
        layout.addWidget(trend_group)
        
        # 筛选区域
        filter_layout = QHBoxLayout()
        
        filter_layout.addWidget(QLabel("筛选:"))
        
        self.date_combo = QComboBox()
        self.date_combo.addItems(["全部", "今天", "最近7天", "最近30天"])
        self.date_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.date_combo)
        
        filter_layout.addStretch()
        
        btn_refresh = QPushButton("🔄 刷新")
        btn_refresh.setObjectName("secondaryButton")
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
        self.list_layout.setSpacing(8)
        
        self.scroll_area.setWidget(self.list_container)
        layout.addWidget(self.scroll_area)
        
    def refresh_data(self):
        """刷新数据"""
        self._load_stats()
        self._load_trend()
        self._load_records()
        
    def _load_stats(self):
        """加载统计信息"""
        stats = database_service.get_statistics()
        self.stats_label.setText(
            f"共 {stats['total_count']} 次评测 | "
            f"平均分: {stats['average_score']} | "
            f"最高: {stats['max_score']} | "
            f"最低: {stats['min_score']}"
        )
        
    def _load_trend(self):
        """加载趋势数据"""
        trend_data = database_service.get_score_trend(limit=30)
        self.trend_chart.plot_trend(trend_data)
        
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
            records = database_service.get_all(limit=50)
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
            empty_label.setStyleSheet("color: #999; padding: 40px;")
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