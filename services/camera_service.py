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
            
        index = camera_index if camera_index is not None else self.config.get(
            "camera_index",
            self.config.get("device_index", 0)
        )
        backend_name = self.config.get("backend", "auto")
        backend = self._resolve_backend(backend_name)
        
        self.logger.info(f"正在打开摄像头: index={index}, backend={backend_name}")
        
        self.camera = self._create_capture(index, backend)
        
        if not self.camera.isOpened():
            self.logger.error("无法打开摄像头")
            self.is_opened = False
            return False
            
        # 设置摄像头参数
        self._configure_camera()
        
        self.is_opened = True
        self.logger.info("摄像头已打开")
        return True

    def _create_capture(self, index: int, backend: int) -> cv2.VideoCapture:
        """根据后端创建 VideoCapture，并在需要时回退到默认实现。"""
        if backend == cv2.CAP_ANY:
            return cv2.VideoCapture(index)

        cap = cv2.VideoCapture(index, backend)
        if cap.isOpened():
            return cap

        self.logger.warning("指定后端打开失败，回退到 OpenCV 默认后端")
        cap.release()
        return cv2.VideoCapture(index)

    def _resolve_backend(self, backend_name) -> int:
        """将配置中的后端名称映射到 OpenCV 后端常量。"""
        if isinstance(backend_name, int):
            return backend_name

        backend_name = str(backend_name).lower()

        if backend_name in {"", "auto", "opencv", "default"}:
            if sys.platform.startswith("win"):
                return getattr(cv2, "CAP_DSHOW", cv2.CAP_ANY)
            if sys.platform.startswith("linux"):
                return getattr(cv2, "CAP_V4L2", cv2.CAP_ANY)
            return cv2.CAP_ANY

        if backend_name in {"picamera", "libcamera"}:
            return getattr(cv2, "CAP_V4L2", cv2.CAP_ANY) if sys.platform.startswith("linux") else cv2.CAP_ANY
        if backend_name == "ffmpeg":
            return getattr(cv2, "CAP_FFMPEG", cv2.CAP_ANY)
        if backend_name == "v4l2":
            return getattr(cv2, "CAP_V4L2", cv2.CAP_ANY)
        if backend_name == "dshow":
            return getattr(cv2, "CAP_DSHOW", cv2.CAP_ANY)

        return cv2.CAP_ANY
    
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

    def release(self):
        """兼容旧接口。"""
        self.close()
    
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
        backend = cv2.CAP_ANY

        if sys.platform.startswith("win"):
            backend = getattr(cv2, "CAP_DSHOW", cv2.CAP_ANY)
        elif sys.platform.startswith("linux"):
            backend = getattr(cv2, "CAP_V4L2", cv2.CAP_ANY)
        
        # 常见设备索引通常落在 0-4，避免无意义地探测过多设备。
        for i in range(5):
            cap = cv2.VideoCapture(i, backend) if backend != cv2.CAP_ANY else cv2.VideoCapture(i)
            if cap.isOpened():
                available.append(i)
                cap.release()
                
        return available

    @property
    def available(self) -> bool:
        """兼容旧测试逻辑，返回当前环境是否探测到可用摄像头。"""
        try:
            return bool(self.list_cameras())
        except Exception:
            return False
    
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
