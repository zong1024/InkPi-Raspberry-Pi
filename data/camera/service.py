"""
InkPi 相机服务

参考 DeepVision 的 CameraLiveActivityBase 设计
支持多种相机后端: picamera, opencv, ffmpeg
"""
import numpy as np
import cv2
from abc import ABC, abstractmethod
from typing import Callable, Optional, Tuple
import logging
import threading
import time

logger = logging.getLogger(__name__)


class CameraFrameListener(ABC):
    """
    相机帧监听器基类
    
    参考 DeepVision 的 CameraFrameListener 接口
    """
    
    @abstractmethod
    def on_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        处理每一帧图像
        
        Args:
            frame: BGR 格式的图像
            
        Returns:
            处理后的图像（可以返回原图）
        """
        pass
    
    def on_capture(self, frame: np.ndarray) -> None:
        """
        捕获完成回调
        
        Args:
            frame: 捕获的图像
        """
        pass


class BaseCameraService(ABC):
    """相机服务基类"""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.is_running = False
        self.frame_listeners = []
        
    @abstractmethod
    def start(self):
        """启动相机"""
        pass
    
    @abstractmethod
    def stop(self):
        """停止相机"""
        pass
    
    @abstractmethod
    def capture_frame(self) -> np.ndarray:
        """捕获单帧图像"""
        pass
    
    def add_frame_listener(self, listener: CameraFrameListener):
        """添加帧监听器"""
        self.frame_listeners.append(listener)
        
    def remove_frame_listener(self, listener: CameraFrameListener):
        """移除帧监听器"""
        if listener in self.frame_listeners:
            self.frame_listeners.remove(listener)
    
    def _notify_listeners(self, frame: np.ndarray) -> np.ndarray:
        """通知所有监听器"""
        result = frame.copy()
        for listener in self.frame_listeners:
            result = listener.on_frame(result)
        return result


class PiCameraService(BaseCameraService):
    """
    树莓派相机服务
    
    使用 picamera 库进行相机控制
    """
    
    def __init__(self, config: dict = None):
        super().__init__(config)
        self.camera = None
        self.stream = None
        
    def start(self):
        try:
            from picamera import PiCamera
            from picamera.array import PiRGBArray
            
            logger.info("启动树莓派相机...")
            
            self.camera = PiCamera()
            self.camera.resolution = (
                self.config.get("preview_width", 640),
                self.config.get("preview_height", 480)
            )
            self.camera.framerate = self.config.get("fps", 30)
            
            # 设置图像增强参数
            self.camera.brightness = self.config.get("brightness", 50)
            self.camera.contrast = self.config.get("contrast", 50)
            self.camera.saturation = self.config.get("saturation", 0)
            self.camera.sharpness = self.config.get("sharpness", 50)
            
            # 预热相机
            time.sleep(2)
            
            self.stream = PiRGBArray(self.camera, size=self.camera.resolution)
            self.is_running = True
            
            logger.info("树莓派相机启动成功")
            
        except ImportError:
            logger.warning("picamera 未安装，回退到 OpenCV")
            return OpenCVCameraService(self.config).start()
        except Exception as e:
            logger.error(f"启动树莓派相机失败: {e}")
            raise
    
    def stop(self):
        if self.stream:
            self.stream.close()
            self.stream = None
        if self.camera:
            self.camera.close()
            self.camera = None
        self.is_running = False
        logger.info("树莓派相机已停止")
    
    def capture_frame(self) -> np.ndarray:
        if not self.is_running or not self.camera:
            raise RuntimeError("相机未启动")
        
        self.camera.capture(self.stream, format='bgr', use_video_port=True)
        frame = self.stream.array
        self.stream.truncate(0)
        
        return frame
    
    def capture_high_res(self) -> np.ndarray:
        """
        捕获高分辨率图像
        
        Returns:
            高分辨率图像
        """
        if not self.is_running or not self.camera:
            raise RuntimeError("相机未启动")
        
        # 临时切换到高分辨率
        original_res = self.camera.resolution
        self.camera.resolution = (
            self.config.get("capture_width", 1280),
            self.config.get("capture_height", 960)
        )
        
        time.sleep(0.5)  # 等待自动曝光调整
        
        stream = PiRGBArray(self.camera, size=self.camera.resolution)
        self.camera.capture(stream, format='bgr')
        frame = stream.array
        
        # 恢复预览分辨率
        self.camera.resolution = original_res
        
        return frame


class OpenCVCameraService(BaseCameraService):
    """
    OpenCV 相机服务
    
    适用于 USB 摄像头或测试环境
    """
    
    def __init__(self, config: dict = None):
        super().__init__(config)
        self.cap = None
        
    def start(self):
        logger.info("启动 OpenCV 相机...")
        
        device_index = self.config.get("device_index", 0)
        self.cap = cv2.VideoCapture(device_index)
        
        if not self.cap.isOpened():
            raise RuntimeError(f"无法打开相机设备 {device_index}")
        
        # 设置分辨率
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 
                     self.config.get("preview_width", 640))
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 
                     self.config.get("preview_height", 480))
        self.cap.set(cv2.CAP_PROP_FPS, self.config.get("fps", 30))
        
        self.is_running = True
        logger.info("OpenCV 相机启动成功")
    
    def stop(self):
        if self.cap:
            self.cap.release()
            self.cap = None
        self.is_running = False
        logger.info("OpenCV 相机已停止")
    
    def capture_frame(self) -> np.ndarray:
        if not self.is_running or not self.cap:
            raise RuntimeError("相机未启动")
        
        ret, frame = self.cap.read()
        if not ret:
            raise RuntimeError("无法读取相机帧")
        
        return frame


class CameraService:
    """
    统一相机服务接口
    
    自动选择最佳相机后端
    """
    
    def __init__(self, config: dict = None):
        """
        初始化相机服务
        
        Args:
            config: 相机配置，参考 CAMERA_CONFIG
        """
        self.config = config or {}
        self.backend_name = self.config.get("backend", "auto")
        self._impl = None
        
    @property
    def impl(self) -> BaseCameraService:
        """获取实际实现的相机服务"""
        if self._impl is None:
            self._impl = self._create_backend()
        return self._impl
    
    def _create_backend(self) -> BaseCameraService:
        """创建相机后端"""
        backend = self.backend_name
        
        if backend == "auto":
            # 自动选择：优先尝试 picamera
            try:
                from picamera import PiCamera
                backend = "picamera"
            except ImportError:
                backend = "opencv"
        
        if backend == "picamera":
            return PiCameraService(self.config)
        elif backend == "opencv":
            return OpenCVCameraService(self.config)
        else:
            raise ValueError(f"不支持的相机后端: {backend}")
    
    def start(self):
        """启动相机"""
        return self.impl.start()
    
    def stop(self):
        """停止相机"""
        return self.impl.stop()
    
    def capture_frame(self) -> np.ndarray:
        """捕获单帧图像"""
        return self.impl.capture_frame()
    
    def capture_high_res(self) -> np.ndarray:
        """捕获高分辨率图像"""
        if hasattr(self.impl, 'capture_high_res'):
            return self.impl.capture_high_res()
        else:
            return self.impl.capture_frame()
    
    def add_frame_listener(self, listener: CameraFrameListener):
        """添加帧监听器"""
        return self.impl.add_frame_listener(listener)
    
    def remove_frame_listener(self, listener: CameraFrameListener):
        """移除帧监听器"""
        return self.impl.remove_frame_listener(listener)
    
    @property
    def is_running(self) -> bool:
        """相机是否正在运行"""
        return self.impl.is_running