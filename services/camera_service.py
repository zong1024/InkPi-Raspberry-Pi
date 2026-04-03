"""Camera service used by both the Qt UI and the local WebUI."""

from __future__ import annotations

from contextlib import contextmanager
import logging
import os
from pathlib import Path
import sys
import threading
import time
from typing import List, Optional

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import CAMERA_CONFIG, IMAGE_CONFIG, IS_RASPBERRY_PI


@contextmanager
def _suppress_opencv_videoio_logs():
    """Temporarily silence noisy native OpenCV video I/O warnings."""

    previous_level = None
    try:
        previous_level = cv2.utils.logging.getLogLevel()
        cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
    except Exception:
        previous_level = None

    try:
        yield
    finally:
        if previous_level is not None:
            try:
                cv2.utils.logging.setLogLevel(previous_level)
            except Exception:
                pass


class _Picamera2Capture:
    """Adapt Picamera2 to a VideoCapture-like interface."""

    _frame_rate_controls_supported = None
    _unsupported_controls_logged = False

    def __init__(self, camera_index: int, config: dict, logger: logging.Logger):
        os.environ.setdefault("LIBCAMERA_LOG_LEVELS", "*:ERROR")
        logging.getLogger("picamera2").setLevel(logging.WARNING)
        logging.getLogger("picamera2.picamera2").setLevel(logging.WARNING)
        from picamera2 import Picamera2

        self.logger = logger
        self._width = int(config.get("preview_width", 640))
        self._height = int(config.get("preview_height", 480))
        self._fps = int(config.get("fps", 30))
        self._opened = False
        self.picam = None

        try:
            self.picam = Picamera2(camera_num=camera_index)
        except TypeError:
            self.picam = Picamera2()

        try:
            self._configure(self._width, self._height)
        except Exception:
            self.release()
            raise

    def _configure(self, width: int, height: int) -> None:
        controls = {}
        if self._fps > 0 and self.__class__._frame_rate_controls_supported is not False:
            controls = {"FrameRate": self._fps}

        camera_config = self.picam.create_preview_configuration(
            main={"size": (int(width), int(height)), "format": "RGB888"},
            controls=controls,
        )

        if self._opened:
            try:
                self.picam.stop()
            except Exception:
                pass
            self._opened = False

        try:
            self.picam.configure(camera_config)
            self.picam.start()
            if controls:
                self.__class__._frame_rate_controls_supported = True
        except RuntimeError as exc:
            if controls and "not advertised by libcamera" in str(exc):
                self.__class__._frame_rate_controls_supported = False
                if not self.__class__._unsupported_controls_logged:
                    self.logger.debug(
                        "Picamera2 frame controls are not supported on this camera; falling back to default timing."
                    )
                    self.__class__._unsupported_controls_logged = True
                camera_config = self.picam.create_preview_configuration(
                    main={"size": (int(width), int(height)), "format": "RGB888"},
                    controls={},
                )
                self.picam.configure(camera_config)
                self.picam.start()
            else:
                raise

        self._opened = True
        time.sleep(0.2)

    def isOpened(self):
        return self._opened

    def read(self):
        if not self._opened:
            return False, None

        try:
            frame = self.picam.capture_array()
            if frame is None:
                return False, None
            if frame.ndim == 3 and frame.shape[2] == 4:
                frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
            elif frame.ndim == 3:
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            return True, frame
        except Exception as exc:  # noqa: BLE001
            self.logger.error("Picamera2 frame read failed: %s", exc)
            return False, None

    def release(self):
        if self.picam is None:
            return
        if self._opened:
            try:
                self.picam.stop()
            except Exception:
                pass
            self._opened = False
        try:
            self.picam.close()
        except Exception:
            pass
        finally:
            self.picam = None

    def set(self, prop_id, value):
        value = int(value)
        if prop_id == cv2.CAP_PROP_FRAME_WIDTH and value > 0:
            if value != self._width:
                self._width = value
                self._configure(self._width, self._height)
            return True
        if prop_id == cv2.CAP_PROP_FRAME_HEIGHT and value > 0:
            if value != self._height:
                self._height = value
                self._configure(self._width, self._height)
            return True
        if prop_id == cv2.CAP_PROP_FPS and value > 0:
            if value != self._fps:
                self._fps = value
                self._configure(self._width, self._height)
            return True
        return False

    def get(self, prop_id):
        if prop_id == cv2.CAP_PROP_FRAME_WIDTH:
            return float(self._width)
        if prop_id == cv2.CAP_PROP_FRAME_HEIGHT:
            return float(self._height)
        if prop_id == cv2.CAP_PROP_FPS:
            return float(self._fps)
        return 0.0


class CameraService:
    """Shared camera access layer."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.config = CAMERA_CONFIG
        self.camera: Optional[object] = None
        self.is_opened = False
        self._preview_thread: Optional[threading.Thread] = None
        self._stop_preview = threading.Event()
        self._current_frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()

    def open(self, camera_index: int | None = None) -> bool:
        if self.is_opened:
            self.logger.warning("Camera is already open.")
            return True

        index = camera_index if camera_index is not None else self.config.get(
            "camera_index",
            self.config.get("device_index", 0),
        )
        backend_name = self.config.get("backend", "auto")
        backend = self._resolve_backend(backend_name)
        self.logger.info("Opening camera index=%s backend=%s", index, backend_name)

        try:
            self.camera = self._create_capture(index, backend)
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("Failed to create camera backend: %s", exc)
            self.camera = None
            self.is_opened = False
            return False

        if not self.camera or not self.camera.isOpened():
            self.logger.error("Unable to open camera.")
            self.is_opened = False
            return False

        self._configure_camera()
        self.is_opened = True
        self.logger.info("Camera opened successfully.")
        return True

    def _create_capture(self, index: int, backend):
        if backend == "picamera2":
            try:
                return _Picamera2Capture(index, self.config, self.logger)
            except Exception as exc:  # noqa: BLE001
                self.logger.warning("Picamera2 backend failed; falling back to OpenCV: %s", exc)
                backend = getattr(cv2, "CAP_V4L2", cv2.CAP_ANY) if sys.platform.startswith("linux") else cv2.CAP_ANY

        if backend == cv2.CAP_ANY:
            with _suppress_opencv_videoio_logs():
                return cv2.VideoCapture(index)

        with _suppress_opencv_videoio_logs():
            capture = cv2.VideoCapture(index, backend)
        if capture.isOpened():
            return capture

        self.logger.warning("Configured backend failed; falling back to OpenCV default backend.")
        capture.release()
        with _suppress_opencv_videoio_logs():
            return cv2.VideoCapture(index)

    def _resolve_backend(self, backend_name):
        if isinstance(backend_name, int):
            return backend_name

        backend_name = str(backend_name).lower()

        if backend_name in {"", "auto", "opencv", "default"}:
            if IS_RASPBERRY_PI and self._picamera2_available():
                return "picamera2"
            if sys.platform.startswith("win"):
                return getattr(cv2, "CAP_DSHOW", cv2.CAP_ANY)
            if sys.platform.startswith("linux"):
                return getattr(cv2, "CAP_V4L2", cv2.CAP_ANY)
            return cv2.CAP_ANY

        if backend_name in {"picamera", "picamera2", "libcamera"}:
            if self._picamera2_available():
                return "picamera2"
            return getattr(cv2, "CAP_V4L2", cv2.CAP_ANY) if sys.platform.startswith("linux") else cv2.CAP_ANY
        if backend_name == "ffmpeg":
            return getattr(cv2, "CAP_FFMPEG", cv2.CAP_ANY)
        if backend_name == "v4l2":
            return getattr(cv2, "CAP_V4L2", cv2.CAP_ANY)
        if backend_name == "dshow":
            return getattr(cv2, "CAP_DSHOW", cv2.CAP_ANY)
        return cv2.CAP_ANY

    def _picamera2_available(self) -> bool:
        try:
            os.environ.setdefault("LIBCAMERA_LOG_LEVELS", "*:ERROR")
            logging.getLogger("picamera2").setLevel(logging.WARNING)
            logging.getLogger("picamera2.picamera2").setLevel(logging.WARNING)
            from picamera2 import Picamera2  # noqa: F401

            return True
        except Exception:
            return False

    def _configure_camera(self) -> None:
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, IMAGE_CONFIG["preview_width"])
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, IMAGE_CONFIG["preview_height"])
        self.camera.set(cv2.CAP_PROP_FPS, self.config["fps"])

        actual_width = self.camera.get(cv2.CAP_PROP_FRAME_WIDTH)
        actual_height = self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT)
        actual_fps = self.camera.get(cv2.CAP_PROP_FPS)
        self.logger.debug("Camera configured to %.0fx%.0f @ %.1ffps", actual_width, actual_height, actual_fps)

    def close(self) -> None:
        self.stop_preview()
        if self.camera:
            self.camera.release()
            self.camera = None
        self.is_opened = False
        self.logger.info("Camera closed.")

    def release(self) -> None:
        self.close()

    def capture_frame(self) -> Optional[np.ndarray]:
        if not self.is_opened or self.camera is None:
            self.logger.error("Camera is not open.")
            return None

        ok, frame = self.camera.read()
        if not ok:
            self.logger.error("Failed to capture frame.")
            return None
        return frame

    def capture_high_res(self) -> Optional[np.ndarray]:
        if not self.is_opened or self.camera is None:
            self.logger.error("Camera is not open.")
            return None

        original_width = self.camera.get(cv2.CAP_PROP_FRAME_WIDTH)
        original_height = self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT)

        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, IMAGE_CONFIG["capture_width"])
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, IMAGE_CONFIG["capture_height"])
        time.sleep(0.2)
        ok, frame = self.camera.read()
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, original_width)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, original_height)

        if not ok:
            self.logger.error("Failed to capture high-resolution frame.")
            return None

        self.logger.info("Captured image: %sx%s", frame.shape[1], frame.shape[0])
        return frame

    def start_preview(self, callback=None) -> None:
        if self._preview_thread and self._preview_thread.is_alive():
            self.logger.warning("Preview is already running.")
            return

        if not self.is_opened and not self.open():
            return

        self._stop_preview.clear()
        self._preview_thread = threading.Thread(target=self._preview_loop, args=(callback,), daemon=True)
        self._preview_thread.start()
        self.logger.info("Preview started.")

    def stop_preview(self) -> None:
        if not self._preview_thread or not self._preview_thread.is_alive():
            return

        self._stop_preview.set()
        self._preview_thread.join(timeout=2.0)
        self._preview_thread = None
        self.logger.info("Preview stopped.")

    def _preview_loop(self, callback) -> None:
        while not self._stop_preview.is_set():
            if self.camera is None or not self.camera.isOpened():
                break

            ok, frame = self.camera.read()
            if ok:
                with self._frame_lock:
                    self._current_frame = frame.copy()
                if callback:
                    try:
                        callback(frame)
                    except Exception as exc:  # noqa: BLE001
                        self.logger.error("Preview callback failed: %s", exc)
            else:
                self.logger.warning("Preview frame capture failed.")

        self.logger.debug("Preview loop exited.")

    def get_current_frame(self) -> Optional[np.ndarray]:
        with self._frame_lock:
            if self._current_frame is None:
                return None
            return self._current_frame.copy()

    @staticmethod
    def list_cameras() -> List[int]:
        available: List[int] = []
        backend = cv2.CAP_ANY

        if IS_RASPBERRY_PI:
            try:
                os.environ.setdefault("LIBCAMERA_LOG_LEVELS", "*:ERROR")
                logging.getLogger("picamera2").setLevel(logging.WARNING)
                logging.getLogger("picamera2.picamera2").setLevel(logging.WARNING)
                from picamera2 import Picamera2

                camera_info = Picamera2.global_camera_info()
                return list(range(len(camera_info)))
            except Exception:
                pass

        if sys.platform.startswith("win"):
            backend = getattr(cv2, "CAP_DSHOW", cv2.CAP_ANY)
        elif sys.platform.startswith("linux"):
            backend = getattr(cv2, "CAP_V4L2", cv2.CAP_ANY)

        for index in range(5):
            with _suppress_opencv_videoio_logs():
                capture = cv2.VideoCapture(index, backend) if backend != cv2.CAP_ANY else cv2.VideoCapture(index)
            if capture.isOpened():
                available.append(index)
                capture.release()
        return available

    @property
    def available(self) -> bool:
        try:
            return bool(self.list_cameras())
        except Exception:
            return False

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


camera_service = CameraService()
