"""
InkPi 书法评测系统 - 摄像头服务

跨平台摄像头支持：
- Windows: DirectShow (CAP_DSHOW)
- Linux/RPi: v4l2 (CAP_V4L2)
"""
import cv2
import numpy as np
from typing import Optional, Tuple, List
import logging
import threading
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import CAMERA_CONFIG, IMAGE_CONFIG


class CameraService:
    """摄像头服务"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config = CAMERA_CONFIG
        
        # 摄像头设备
        self.camera: Optional[cv2.VideoCapture] = None
        self.is_opened = False
        
        # 预览线程控制
        self._preview_thread: Optional[threading.Thread] = None
        self._stop_preview = threading.Event()
        self._current_frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()
        
    def open(self, camera_index: int = None) -> bool:
        """
        打开摄像头
        
        Args:
            camera_index: 摄像头索引，None 则使用配置中的默认值
            
        Returns:
            是否成功打开
        """
        if self.is_opened:
            self.logger.warning("摄像头已经打开")
            return True
            
        index = camera_index if camera_index is not None else self.config["camera_index"]
        backend = self.config["backend"]
        
        self.logger.info(f"正在打开摄像头: index={index}, backend={backend}")
        
        self.camera = cv2.VideoCapture(index, backend)
        
        if not self.camera.isOpened():
            self.logger.error("无法打开摄像头")
            self.is_opened = False
            return False
            
        # 设置摄像头参数
        self._configure_camera()
        
        self.is_opened = True
        self.logger.info("摄像头已打开")
        return True
    
    def _configure_camera(self):
        """配置摄像头参数"""
        # 预览分辨率
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, IMAGE_CONFIG["preview_width"])
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, IMAGE_CONFIG["preview_height"])
        self.camera.set(cv2.CAP_PROP_FPS, self.config["fps"])
        
        # 获取实际配置
        actual_width = self.camera.get(cv2.CAP_PROP_FRAME_WIDTH)
        actual_height = self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT)
        actual_fps = self.camera.get(cv2.CAP_PROP_FPS)
        
        self.logger.debug(f"摄像头配置: {actual_width}x{actual_height} @ {actual_fps}fps")
    
    def close(self):
        """关闭摄像头"""
        self.stop_preview()
        
        if self.camera:
            self.camera.release()
            self.camera = None
            
        self.is_opened = False
        self.logger.info("摄像头已关闭")
    
    def capture_frame(self) -> Optional[np.ndarray]:
        """
        捕获单帧图像
        
        Returns:
            图像数组或 None
        """
        if not self.is_opened or self.camera is None:
            self.logger.error("摄像头未打开")
            return None
            
        ret, frame = self.camera.read()
        
        if not ret:
            self.logger.error("捕获图像失败")
            return None
            
        return frame
    
    def capture_high_res(self) -> Optional[np.ndarray]:
        """
        捕获高分辨率图像
        
        Returns:
            图像数组或 None
        """
        if not self.is_opened or self.camera is None:
            self.logger.error("摄像头未打开")
            return None
            
        # 临时切换到高分辨率
        original_width = self.camera.get(cv2.CAP_PROP_FRAME_WIDTH)
        original_height = self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT)
        
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, IMAGE_CONFIG["capture_width"])
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, IMAGE_CONFIG["capture_height"])
        
        # 等待摄像头稳定
        import time
        time.sleep(0.2)
        
        # 捕获图像
        ret, frame = self.camera.read()
        
        # 恢复原始分辨率
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, original_width)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, original_height)
        
        if not ret:
            self.logger.error("捕获高分辨率图像失败")
            return None
            
        self.logger.info(f"捕获高分辨率图像: {frame.shape[1]}x{frame.shape[0]}")
        return frame
    
    def start_preview(self, callback=None):
        """
        启动预览线程
        
        Args:
            callback: 每帧回调函数，接收 frame 参数
        """
        if self._preview_thread and self._preview_thread.is_alive():
            self.logger.warning("预览已经在运行")
            return
            
        if not self.is_opened:
            if not self.open():
                return
                
        self._stop_preview.clear()
        self._preview_thread = threading.Thread(
            target=self._preview_loop,
            args=(callback,),
            daemon=True
        )
        self._preview_thread.start()
        self.logger.info("预览已启动")
    
    def stop_preview(self):
        """停止预览线程"""
        if not self._preview_thread or not self._preview_thread.is_alive():
            return
            
        self._stop_preview.set()
        self._preview_thread.join(timeout=2.0)
        self._preview_thread = None
        self.logger.info("预览已停止")
    
    def _preview_loop(self, callback):
        """
        预览循环
        
        Args:
            callback: 每帧回调函数
        """
        while not self._stop_preview.is_set():
            if self.camera is None or not self.camera.isOpened():
                break
                
            ret, frame = self.camera.read()
            
            if ret:
                with self._frame_lock:
                    self._current_frame = frame.copy()
                    
                if callback:
                    try:
                        callback(frame)
                    except Exception as e:
                        self.logger.error(f"预览回调错误: {e}")
            else:
                self.logger.warning("预览帧捕获失败")
                
        self.logger.debug("预览循环结束")
    
    def get_current_frame(self) -> Optional[np.ndarray]:
        """
        获取当前帧（线程安全）
        
        Returns:
            当前帧图像
        """
        with self._frame_lock:
            if self._current_frame is not None:
                return self._current_frame.copy()
            return None
    
    @staticmethod
    def list_cameras() -> List[int]:
        """
        列出可用摄像头
        
        Returns:
            可用摄像头索引列表
        """
        available = []
        
        # 测试索引 0-9
        for i in range(10):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available.append(i)
                cap.release()
                
        return available
    
    def __enter__(self):
        """上下文管理器入口"""
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
        return False


# 创建全局服务实例
camera_service = CameraService()