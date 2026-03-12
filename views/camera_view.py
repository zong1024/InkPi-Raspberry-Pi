"""
InkPi 书法评测系统 - 相机视图
适配3.5寸屏幕 (480x320)
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt6.QtGui import QFont, QImage, QPixmap

import cv2
import numpy as np

from services.camera_service import camera_service
from services.preprocessing_service import preprocessing_service, PreprocessingError
from services.evaluation_service import evaluation_service
from services.database_service import database_service
from services.speech_service import speech_service
from services.camera_service import CameraService
from config import IMAGES_DIR
from models.evaluation_result import EvaluationResult


class PreviewThread(QThread):
    """预览线程"""
    
    frame_ready = pyqtSignal(np.ndarray)
    
    def __init__(self, camera_service: CameraService):
        super().__init__()
        self.camera = camera_service
        self._running = False
        
    def run(self):
        self._running = True
        while self._running:
            frame = self.camera.capture_frame()
            if frame is not None:
                self.frame_ready.emit(frame)
            time.sleep(0.033)  # ~30 FPS
            
    def stop(self):
        self._running = False
        self.wait()


class CameraView(QWidget):
    """相机视图 - 适配3.5寸屏幕"""
    
    # 信号
    capture_completed = pyqtSignal(EvaluationResult)  # 拍照完成
    cancelled = pyqtSignal()                          # 取消
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.preview_thread: PreviewThread = None
        self.current_frame: np.ndarray = None
        self._init_ui()
        
    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # 预览区域 - 占满大部分屏幕
        self.preview_frame = QFrame()
        self.preview_frame.setObjectName("previewFrame")
        preview_layout = QVBoxLayout(self.preview_frame)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        
        self.preview_label = QLabel("启动中...")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(470, 260)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #1a1a1a;
                color: #fff;
                font-size: 12px;
            }
        """)
        preview_layout.addWidget(self.preview_label)
        
        layout.addWidget(self.preview_frame, stretch=1)
        
        # 按钮区域 - 底部紧凑
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setObjectName("secondaryButton")
        self.btn_cancel.setFont(QFont("Microsoft YaHei", 10))
        self.btn_cancel.setFixedSize(80, 40)
        self.btn_cancel.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self.btn_cancel)
        
        btn_layout.addStretch()
        
        self.btn_capture = QPushButton("📷 拍照")
        self.btn_capture.setObjectName("captureButton")
        self.btn_capture.setFont(QFont("Microsoft YaHei", 11))
        self.btn_capture.setFixedSize(100, 40)
        self.btn_capture.clicked.connect(self._on_capture)
        btn_layout.addWidget(self.btn_capture)
        
        layout.addLayout(btn_layout)
        
    def showEvent(self, event):
        """显示事件 - 启动相机"""
        super().showEvent(event)
        self._start_camera()
        
    def hideEvent(self, event):
        """隐藏事件 - 停止相机"""
        super().hideEvent(event)
        self._stop_camera()
        
    def _start_camera(self):
        """启动相机"""
        # 打开相机
        if not camera_service.open():
            self.preview_label.setText("无法打开摄像头")
            self.btn_capture.setEnabled(False)
            return
            
        self.btn_capture.setEnabled(True)
        
        # 启动预览线程
        self.preview_thread = PreviewThread(camera_service)
        self.preview_thread.frame_ready.connect(self._update_preview)
        self.preview_thread.start()
        
    def _stop_camera(self):
        """停止相机"""
        if self.preview_thread:
            self.preview_thread.stop()
            self.preview_thread = None
            
        camera_service.close()
        
    def _update_preview(self, frame: np.ndarray):
        """更新预览画面"""
        self.current_frame = frame.copy()
        
        # 添加取景框蒙版
        display_frame = self._add_guide_overlay(frame)
        
        # 转换为 QPixmap
        h, w, ch = display_frame.shape
        bytes_per_line = ch * w
        q_image = QImage(display_frame.data, w, h, bytes_per_line, QImage.Format.Format_BGR888)
        pixmap = QPixmap.fromImage(q_image)
        
        # 缩放显示
        scaled_pixmap = pixmap.scaled(
            self.preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        self.preview_label.setPixmap(scaled_pixmap)
        
    def _add_guide_overlay(self, frame: np.ndarray) -> np.ndarray:
        """添加取景框蒙版"""
        h, w = frame.shape[:2]
        overlay = frame.copy()
        
        # 计算取景框区域（中心正方形）
        size = min(w, h) - 40
        x1 = (w - size) // 2
        y1 = (h - size) // 2
        x2 = x1 + size
        y2 = y1 + size
        
        # 绘制取景框
        color = (255, 200, 0)  # 黄色
        thickness = 2
        
        # 外框
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, thickness)
        
        # 米字格辅助线（半透明）
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        
        # 横竖线
        cv2.line(overlay, (x1, center_y), (x2, center_y), (128, 128, 128), 1)
        cv2.line(overlay, (center_x, y1), (center_x, y2), (128, 128, 128), 1)
        
        # 对角线
        cv2.line(overlay, (x1, y1), (x2, y2), (128, 128, 128), 1)
        cv2.line(overlay, (x1, y2), (x2, y1), (128, 128, 128), 1)
        
        # 四角标记
        corner_len = 20
        # 左上
        cv2.line(overlay, (x1, y1 + corner_len), (x1, y1), color, thickness)
        cv2.line(overlay, (x1, y1), (x1 + corner_len, y1), color, thickness)
        # 右上
        cv2.line(overlay, (x2 - corner_len, y1), (x2, y1), color, thickness)
        cv2.line(overlay, (x2, y1), (x2, y1 + corner_len), color, thickness)
        # 左下
        cv2.line(overlay, (x1, y2 - corner_len), (x1, y2), color, thickness)
        cv2.line(overlay, (x1, y2), (x1 + corner_len, y2), color, thickness)
        # 右下
        cv2.line(overlay, (x2 - corner_len, y2), (x2, y2), color, thickness)
        cv2.line(overlay, (x2, y2), (x2, y2 - corner_len), color, thickness)
        
        return overlay
        
    def _on_capture(self):
        """拍照按钮点击"""
        if self.current_frame is None:
            return
            
        self.btn_capture.setEnabled(False)
        
        # 保存原始图像
        timestamp = int(time.time() * 1000)
        original_path = IMAGES_DIR / f"original_{timestamp}.jpg"
        cv2.imwrite(str(original_path), self.current_frame)
        
        try:
            # 图像预处理
            processed, processed_path = preprocessing_service.preprocess(
                self.current_frame, 
                save_processed=True
            )
            
            # 评测分析
            result = evaluation_service.evaluate(
                processed,
                original_image_path=str(original_path),
                processed_image_path=processed_path
            )
            
            # 保存到数据库
            record_id = database_service.save(result)
            result.id = record_id
            
            # 语音播报
            speech_service.speak_score(result.total_score, result.feedback)
            
            # 释放内存
            preprocessing_service.release_memory()
            
            self.capture_completed.emit(result)
            
        except PreprocessingError as e:
            # 预处理错误
            speech_service.speak_error(str(e))
            QMessageBox.warning(self, "图像质量问题", str(e))
            self.btn_capture.setEnabled(True)
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"评测失败: {str(e)}")
            self.btn_capture.setEnabled(True)
            
    def _on_cancel(self):
        """取消按钮点击"""
        self.cancelled.emit()
        
    def cleanup(self):
        """清理资源"""
        self._stop_camera()