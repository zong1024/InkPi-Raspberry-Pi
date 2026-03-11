#!/usr/bin/env python3
"""
InkPi 书法评测系统 - 主程序入口

基于 Python 3.11+ + PyQt6 + OpenCV 的跨平台书法评测应用
"""
import sys
import logging
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from config import UI_CONFIG, LOG_CONFIG, DATA_DIR
from views.main_window import MainWindow


def setup_logging():
    """配置日志"""
    log_config = LOG_CONFIG
    
    logging.basicConfig(
        level=getattr(logging, log_config.get("level", "INFO")),
        format=log_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(
                log_config.get("log_file", DATA_DIR / "inkpi.log"),
                encoding='utf-8'
            )
        ]
    )


def load_stylesheet(app: QApplication):
    """加载样式表"""
    style = """
    /* 全局样式 */
    QWidget {
        font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
        background-color: #f5f5f5;
    }
    
    /* 导航栏 */
    #navbar {
        background-color: #ffffff;
        border-bottom: 1px solid #e0e0e0;
    }
    
    #navTitle {
        color: #333;
    }
    
    #navButton {
        background-color: transparent;
        border: none;
        padding: 8px 16px;
        font-size: 13px;
        color: #666;
        border-radius: 4px;
    }
    
    #navButton:hover {
        background-color: #f0f0f0;
        color: #333;
    }
    
    #navButton[active="true"] {
        background-color: #2196F3;
        color: white;
    }
    
    /* 按钮 */
    QPushButton {
        border: none;
        border-radius: 6px;
        padding: 8px 16px;
    }
    
    #primaryButton {
        background-color: #2196F3;
        color: white;
        font-weight: bold;
    }
    
    #primaryButton:hover {
        background-color: #1976D2;
    }
    
    #primaryButton:pressed {
        background-color: #1565C0;
    }
    
    #secondaryButton {
        background-color: #e0e0e0;
        color: #333;
    }
    
    #secondaryButton:hover {
        background-color: #d0d0d0;
    }
    
    #captureButton {
        background-color: #4CAF50;
        color: white;
        font-weight: bold;
        border-radius: 30px;
    }
    
    #captureButton:hover {
        background-color: #388E3C;
    }
    
    #captureButton:disabled {
        background-color: #9E9E9E;
    }
    
    #textButton {
        background-color: transparent;
        color: #2196F3;
        text-decoration: none;
    }
    
    #textButton:hover {
        color: #1976D2;
    }
    
    #deleteButton {
        background-color: #ffebee;
        color: #f44336;
        border-radius: 12px;
    }
    
    #deleteButton:hover {
        background-color: #f44336;
        color: white;
    }
    
    /* 卡片 */
    #recentCard, #historyItem, #scoreCard {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
    }
    
    #recentCard:hover, #historyItem:hover {
        border-color: #2196F3;
        box-shadow: 0 2px 8px rgba(33, 150, 243, 0.15);
    }
    
    #featureCard {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 20px;
    }
    
    /* 总分区域 */
    #totalScoreFrame {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 20px;
        min-width: 150px;
    }
    
    /* 雷达图区域 */
    #radarFrame {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 10px;
    }
    
    /* 反馈区域 */
    #feedbackFrame {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 15px;
    }
    
    /* 预览区域 */
    #previewFrame {
        background-color: #1a1a1a;
        border: 2px solid #333;
        border-radius: 8px;
    }
    
    /* 分数标签 */
    #scoreLabel {
        font-weight: bold;
    }
    
    /* 组合框 */
    QComboBox {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 4px;
        padding: 6px 12px;
        min-width: 100px;
    }
    
    QComboBox:hover {
        border-color: #2196F3;
    }
    
    QComboBox::drop-down {
        border: none;
        width: 20px;
    }
    
    /* 分组框 */
    QGroupBox {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        margin-top: 10px;
        padding-top: 10px;
        font-weight: bold;
    }
    
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 15px;
        padding: 0 5px;
        color: #333;
    }
    
    /* 滚动区域 */
    QScrollArea {
        background-color: transparent;
    }
    
    /* 消息框 */
    QMessageBox {
        background-color: #ffffff;
    }
    
    /* 状态栏 */
    QStatusBar {
        background-color: #ffffff;
        border-top: 1px solid #e0e0e0;
        color: #666;
        font-size: 11px;
    }
    """
    
    app.setStyleSheet(style)


def main():
    """主函数"""
    # 配置日志
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("InkPi 书法评测系统启动中...")
    
    # 创建应用
    app = QApplication(sys.argv)
    app.setApplicationName("InkPi")
    app.setApplicationVersion("1.0.0")
    
    # 设置默认字体
    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)
    
    # 加载样式表
    load_stylesheet(app)
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    logger.info("应用启动完成")
    
    # 运行事件循环
    exit_code = app.exec()
    
    logger.info(f"应用退出，代码: {exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()