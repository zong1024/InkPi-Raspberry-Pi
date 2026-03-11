"""
InkPi 书法评测系统 - 主窗口
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QPushButton, QLabel, QMessageBox,
    QApplication, QStatusBar
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon

from config import UI_CONFIG
from views.home_view import HomeView
from views.camera_view import CameraView
from views.result_view import ResultView
from views.history_view import HistoryView
from models.evaluation_result import EvaluationResult


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        
        # 当前评测结果
        self.current_result: EvaluationResult = None
        
        # 初始化 UI
        self._init_ui()
        self._connect_signals()
        
    def _init_ui(self):
        """初始化 UI"""
        # 窗口设置
        self.setWindowTitle(UI_CONFIG["window_title"])
        self.setMinimumSize(800, 600)
        self.resize(UI_CONFIG["window_width"], UI_CONFIG["window_height"])
        
        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 顶部导航栏
        self._create_navbar(main_layout)
        
        # 页面堆栈
        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack)
        
        # 创建各页面
        self.home_view = HomeView()
        self.camera_view = CameraView()
        self.result_view = ResultView()
        self.history_view = HistoryView()
        
        self.stack.addWidget(self.home_view)      # 0
        self.stack.addWidget(self.camera_view)    # 1
        self.stack.addWidget(self.result_view)    # 2
        self.stack.addWidget(self.history_view)   # 3
        
        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")
        
    def _create_navbar(self, layout: QVBoxLayout):
        """创建导航栏"""
        navbar = QWidget()
        navbar.setObjectName("navbar")
        navbar.setFixedHeight(60)
        
        nav_layout = QHBoxLayout(navbar)
        nav_layout.setContentsMargins(20, 10, 20, 10)
        
        # Logo/标题
        title_label = QLabel("🖌️ InkPi 书法评测")
        title_label.setObjectName("navTitle")
        title_label.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        nav_layout.addWidget(title_label)
        
        nav_layout.addStretch()
        
        # 导航按钮
        self.btn_home = QPushButton("首页")
        self.btn_home.setObjectName("navButton")
        self.btn_camera = QPushButton("拍照")
        self.btn_camera.setObjectName("navButton")
        self.btn_history = QPushButton("历史")
        self.btn_history.setObjectName("navButton")
        
        nav_layout.addWidget(self.btn_home)
        nav_layout.addWidget(self.btn_camera)
        nav_layout.addWidget(self.btn_history)
        
        layout.addWidget(navbar)
        
    def _connect_signals(self):
        """连接信号"""
        # 导航按钮
        self.btn_home.clicked.connect(self.show_home)
        self.btn_camera.clicked.connect(self.show_camera)
        self.btn_history.clicked.connect(self.show_history)
        
        # 首页信号
        self.home_view.start_evaluation.connect(self.show_camera)
        self.home_view.view_history.connect(self.show_history)
        
        # 相机页信号
        self.camera_view.capture_completed.connect(self._on_capture_completed)
        self.camera_view.cancelled.connect(self.show_home)
        
        # 结果页信号
        self.result_view.back_requested.connect(self.show_home)
        self.result_view.new_evaluation_requested.connect(self.show_camera)
        self.result_view.history_requested.connect(self.show_history)
        
        # 历史页信号
        self.history_view.back_requested.connect(self.show_home)
        self.history_view.result_selected.connect(self._on_history_result_selected)
        
    def show_home(self):
        """显示首页"""
        self.stack.setCurrentIndex(0)
        self.status_bar.showMessage("首页")
        self._update_nav_buttons(0)
        
    def show_camera(self):
        """显示相机页"""
        self.stack.setCurrentIndex(1)
        self.status_bar.showMessage("准备拍照")
        self._update_nav_buttons(1)
        
    def show_result(self):
        """显示结果页"""
        self.stack.setCurrentIndex(2)
        self.status_bar.showMessage("评测结果")
        self._update_nav_buttons(2)
        
    def show_history(self):
        """显示历史页"""
        self.stack.setCurrentIndex(3)
        self.history_view.refresh_data()
        self.status_bar.showMessage("历史记录")
        self._update_nav_buttons(3)
        
    def _update_nav_buttons(self, active_index: int):
        """更新导航按钮状态"""
        buttons = [self.btn_home, self.btn_camera, self.btn_history]
        for i, btn in enumerate(buttons):
            btn.setProperty("active", i == active_index)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            
    def _on_capture_completed(self, result: EvaluationResult):
        """拍照完成回调"""
        self.current_result = result
        self.result_view.set_result(result)
        self.show_result()
        
    def _on_history_result_selected(self, result: EvaluationResult):
        """历史记录选择回调"""
        self.current_result = result
        self.result_view.set_result(result)
        self.show_result()
        
    def closeEvent(self, event):
        """窗口关闭事件"""
        # 停止相机
        self.camera_view.cleanup()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())