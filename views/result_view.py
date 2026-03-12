"""
InkPi 书法评测系统 - 结果视图
适配3.5寸屏幕 (480x320)
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
from services.led_service import led_service
from services.cloud_upload_service import CloudUploadService
from config import UI_CONFIG, CLOUD_CONFIG


class RadarChart(FigureCanvas):
    """雷达图组件 - 紧凑版"""
    
    def __init__(self, parent=None, size=150):
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
        self.ax.set_yticks([50, 100])
        self.ax.set_yticklabels(['50', '100'], fontsize=6, color='#666')
        
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
        
        # 绘制雷达图
        self.ax.plot(angles_closed, values_closed, 'o-', linewidth=1.5, color='#2196F3', markersize=4)
        self.ax.fill(angles_closed, values_closed, alpha=0.25, color='#2196F3')
        
        # 设置标签
        self.ax.set_xticks(angles)
        self.ax.set_xticklabels(labels, fontsize=7, fontweight='bold')
        
        self.ax.grid(True, linestyle='--', alpha=0.5)
        self.draw()


class ResultView(QWidget):
    """结果视图 - 适配3.5寸屏幕"""
    
    # 信号
    back_requested = pyqtSignal()              # 返回首页
    new_evaluation_requested = pyqtSignal()    # 新建评测
    history_requested = pyqtSignal()           # 查看历史
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.result: EvaluationResult = None
        self._init_ui()
        
        # 初始化云上传服务
        if CLOUD_CONFIG.get("enabled", False):
            self.cloud_service = CloudUploadService(env_id=CLOUD_CONFIG["env_id"])
        else:
            self.cloud_service = None
        
    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        # 顶部信息 - 横向布局
        top_layout = QHBoxLayout()
        top_layout.setSpacing(10)
        
        # 总分区域 - 左侧
        score_frame = QFrame()
        score_frame.setObjectName("totalScoreFrame")
        score_frame.setFixedWidth(120)
        score_layout = QVBoxLayout(score_frame)
        score_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_layout.setSpacing(2)
        
        total_title = QLabel("总分")
        total_title.setFont(QFont("Microsoft YaHei", 10))
        total_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_layout.addWidget(total_title)
        
        self.total_score_label = QLabel("--")
        self.total_score_label.setFont(QFont("Arial", 36, QFont.Weight.Bold))
        self.total_score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_layout.addWidget(self.total_score_label)
        
        self.grade_label = QLabel("--")
        self.grade_label.setFont(QFont("Microsoft YaHei", 11))
        self.grade_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_layout.addWidget(self.grade_label)
        
        top_layout.addWidget(score_frame)
        
        # 雷达图区域 - 右侧
        radar_frame = QFrame()
        radar_frame.setObjectName("radarFrame")
        radar_layout = QVBoxLayout(radar_frame)
        radar_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        radar_layout.setSpacing(2)
        
        radar_title = QLabel("四维评分")
        radar_title.setFont(QFont("Microsoft YaHei", 9))
        radar_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        radar_layout.addWidget(radar_title)
        
        self.radar_chart = RadarChart(size=UI_CONFIG["radar_chart_size"])
        radar_layout.addWidget(self.radar_chart)
        
        top_layout.addWidget(radar_frame)
        
        layout.addLayout(top_layout)
        
        # 四维分数卡片 - 紧凑横排
        self.scores_layout = QHBoxLayout()
        self.scores_layout.setSpacing(5)
        layout.addLayout(self.scores_layout)
        
        # 反馈区域 - 简化
        feedback_frame = QFrame()
        feedback_frame.setObjectName("feedbackFrame")
        feedback_layout = QVBoxLayout(feedback_frame)
        feedback_layout.setSpacing(2)
        
        feedback_title = QLabel("评测反馈")
        feedback_title.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        feedback_layout.addWidget(feedback_title)
        
        self.feedback_label = QLabel("")
        self.feedback_label.setFont(QFont("Microsoft YaHei", 9))
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setStyleSheet("color: #333; padding: 5px;")
        feedback_layout.addWidget(self.feedback_label)
        
        layout.addWidget(feedback_frame)
        
        # 识别字符显示区域
        self.char_frame = QFrame()
        self.char_frame.setObjectName("charFrame")
        char_layout = QHBoxLayout(self.char_frame)
        char_layout.setContentsMargins(5, 2, 5, 2)
        
        char_title = QLabel("识别结果:")
        char_title.setFont(QFont("Microsoft YaHei", 9))
        char_title.setStyleSheet("color: #666;")
        char_layout.addWidget(char_title)
        
        self.char_label = QLabel("--")
        self.char_label.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        self.char_label.setStyleSheet("color: #2196F3;")
        char_layout.addWidget(self.char_label)
        
        self.confidence_label = QLabel("")
        self.confidence_label.setFont(QFont("Microsoft YaHei", 8))
        self.confidence_label.setStyleSheet("color: #999;")
        char_layout.addWidget(self.confidence_label)
        
        char_layout.addStretch()
        layout.addWidget(self.char_frame)
        
        # 按钮区域 - 底部触屏优化
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)
        
        self.btn_home = QPushButton("🏠首页")
        self.btn_home.setObjectName("secondaryButton")
        self.btn_home.setFont(QFont("Microsoft YaHei", 10))
        self.btn_home.setFixedSize(80, 45)
        self.btn_home.clicked.connect(self.back_requested.emit)
        btn_layout.addWidget(self.btn_home)
        
        self.btn_speak = QPushButton("🔊播报")
        self.btn_speak.setObjectName("secondaryButton")
        self.btn_speak.setFont(QFont("Microsoft YaHei", 10))
        self.btn_speak.setFixedSize(70, 45)
        self.btn_speak.clicked.connect(self._on_speak)
        btn_layout.addWidget(self.btn_speak)
        
        btn_layout.addStretch()
        
        self.btn_upload = QPushButton("📤上传")
        self.btn_upload.setObjectName("uploadButton")
        self.btn_upload.setFont(QFont("Microsoft YaHei", 10))
        self.btn_upload.setFixedSize(70, 45)
        self.btn_upload.clicked.connect(self._on_upload)
        btn_layout.addWidget(self.btn_upload)
        
        self.btn_new = QPushButton("📷再次评测")
        self.btn_new.setObjectName("primaryButton")
        self.btn_new.setFont(QFont("Microsoft YaHei", 10))
        self.btn_new.setFixedSize(100, 45)
        self.btn_new.clicked.connect(self.new_evaluation_requested.emit)
        btn_layout.addWidget(self.btn_new)
        
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
        while self.scores_layout.count():
            item = self.scores_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        # 添加紧凑卡片
        for dim, score in self.result.detail_scores.items():
            card = self._create_score_card(dim, score)
            self.scores_layout.addWidget(card)
            
        self.scores_layout.addStretch()
        
        # 更新反馈
        self.feedback_label.setText(self.result.feedback)
        
        # 更新识别字符显示
        if self.result.character_name:
            self.char_label.setText(self.result.character_name)
            self.confidence_label.setText("(已识别)")
        else:
            self.char_label.setText("--")
            self.confidence_label.setText("")
        
        # 触发 LED 灯光效果
        led_service.show_score(self.result.total_score)
        
        # 上传到云端
        self._upload_to_cloud()
        
    def _create_score_card(self, dimension: str, score: int) -> QFrame:
        """创建紧凑评分卡片"""
        card = QFrame()
        card.setObjectName("scoreCard")
        card.setFixedSize(70, 45)
        
        layout = QVBoxLayout(card)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(1)
        
        # 维度名称
        dim_label = QLabel(dimension)
        dim_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dim_label.setStyleSheet("color: #666; font-size: 9px;")
        layout.addWidget(dim_label)
        
        # 分数
        score_label = QLabel(str(score))
        score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        if score >= 80:
            color = "#4CAF50"
        elif score >= 60:
            color = "#FF9800"
        else:
            color = "#F44336"
            
        score_label.setStyleSheet(f"color: {color}; font-size: 16px; font-weight: bold;")
        layout.addWidget(score_label)
        
        return card
        
    def _upload_to_cloud(self):
        """上传评测结果到云端"""
        if self.cloud_service and self.result:
            try:
                result = self.cloud_service.upload_evaluation_result(
                    openid=CLOUD_CONFIG["openid"],
                    total_score=self.result.total_score,
                    detail_scores=self.result.detail_scores,
                    feedback=self.result.feedback,
                    image_path=self.result.image_path,
                    processed_image_path=self.result.processed_image_path,
                    recognized_char=self.result.character_name,
                    title=f"书法评测 · {self.result.timestamp.strftime('%Y-%m-%d %H:%M')}"
                )
                if result.get("success"):
                    print("[云同步] 上传成功")
                else:
                    print(f"[云同步] 上传失败: {result.get('error', '未知错误')}")
            except Exception as e:
                print(f"[云同步] 上传异常: {e}")
        
    def _on_speak(self):
        """语音播报"""
        if self.result:
            speech_service.speak_score(
                self.result.total_score, 
                self.result.feedback
            )
    
    def _on_upload(self):
        """手动上传到小程序"""
        if not self.cloud_service:
            print("[云同步] 云服务未启用")
            return
            
        if not self.result:
            return
            
        try:
            # 显示上传中状态
            self.btn_upload.setText("上传中...")
            self.btn_upload.setEnabled(False)
            
            result = self.cloud_service.upload_evaluation_result(
                openid=CLOUD_CONFIG["openid"],
                total_score=self.result.total_score,
                detail_scores=self.result.detail_scores,
                feedback=self.result.feedback,
                image_path=self.result.image_path,
                processed_image_path=self.result.processed_image_path,
                recognized_char=self.result.character_name,
                title=f"书法评测 · {self.result.timestamp.strftime('%Y-%m-%d %H:%M')}"
            )
            
            if result.get("success"):
                self.btn_upload.setText("✓已上传")
                print("[云同步] 手动上传成功")
            else:
                self.btn_upload.setText("📤上传")
                print(f"[云同步] 手动上传失败: {result.get('error', '未知错误')}")
                
        except Exception as e:
            self.btn_upload.setText("📤上传")
            print(f"[云同步] 手动上传异常: {e}")
        finally:
            self.btn_upload.setEnabled(True)
