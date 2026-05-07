"""Camera view for capture and evaluation."""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
import numpy as np
from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QImage, QPixmap
from PyQt6.QtWidgets import QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from config import IMAGES_DIR
from models.evaluation_result import EvaluationResult
from services.camera_service import CameraService, camera_service
from services.database_service import database_service
from services.evaluation_service import evaluation_service
from services.preprocessing_service import PreprocessingError, preprocessing_service
from services.speech_service import speech_service
from views.ui_theme import app_font


class PreviewThread(QThread):
    """Lightweight preview loop."""

    frame_ready = pyqtSignal(np.ndarray)

    def __init__(self, camera: CameraService):
        super().__init__()
        self.camera = camera
        self._running = False

    def run(self) -> None:
        self._running = True
        while self._running:
            frame = self.camera.capture_frame()
            if frame is not None:
                self.frame_ready.emit(frame)
            self.msleep(33)

    def stop(self) -> None:
        self._running = False
        self.wait()


class CameraView(QWidget):
    """Capture page designed for 480x320 landscape."""

    capture_completed = pyqtSignal(EvaluationResult)
    cancelled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.preview_thread: PreviewThread | None = None
        self.current_frame: np.ndarray | None = None
        self.compact_mode = False
        self._init_ui()

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(5)

        self.preview_label = QLabel("正在准备摄像头...")
        self.preview_label.setObjectName("previewLabel")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setFixedHeight(132)
        self.preview_label.setFont(app_font(10))
        self.preview_label.setWordWrap(True)
        root.addWidget(self.preview_label, stretch=1)

        hint_row = QHBoxLayout()
        hint_row.setSpacing(6)

        self.guide_label = QLabel("请将单字放在取景框中央")
        self.guide_label.setObjectName("miniLabel")
        hint_row.addWidget(self.guide_label, stretch=1)

        self.model_state = QLabel(self._build_model_state_text())
        self.model_state.setObjectName("statusPill")
        hint_row.addWidget(self.model_state)

        self.camera_state = QLabel("等待连接")
        self.camera_state.setObjectName("statusPill")
        hint_row.addWidget(self.camera_state)
        root.addLayout(hint_row)

        actions = QGridLayout()
        actions.setHorizontalSpacing(6)
        actions.setVerticalSpacing(0)

        self.btn_load = QPushButton("上传图片")
        self.btn_load.setObjectName("secondaryButton")
        self.btn_load.setFixedHeight(36)
        self.btn_load.clicked.connect(self._on_load_image)
        actions.addWidget(self.btn_load, 0, 0)

        self.btn_capture = QPushButton("拍照")
        self.btn_capture.setObjectName("circleButton")
        self.btn_capture.setFixedHeight(36)
        self.btn_capture.clicked.connect(self._on_capture)
        actions.addWidget(self.btn_capture, 0, 1)

        self.btn_eval = QPushButton("开始评测")
        self.btn_eval.setObjectName("primaryButton")
        self.btn_eval.setFixedHeight(36)
        self.btn_eval.clicked.connect(self._on_capture)
        actions.addWidget(self.btn_eval, 0, 2)

        self.btn_cancel = QPushButton("首页")
        self.btn_cancel.setObjectName("ghostButton")
        self.btn_cancel.setFixedHeight(36)
        self.btn_cancel.clicked.connect(self.cancelled.emit)
        actions.addWidget(self.btn_cancel, 0, 3)

        root.addLayout(actions)

    def _build_model_state_text(self) -> str:
        ocr_ready = getattr(evaluation_service, "logger", None) is not None
        try:
            from services.local_ocr_service import local_ocr_service
            from services.quality_scorer_service import quality_scorer_service

            ocr_ready = bool(local_ocr_service.available)
            onnx_ready = bool(quality_scorer_service.available)
        except Exception:
            ocr_ready = False
            onnx_ready = False

        if ocr_ready and onnx_ready:
            return "模型在线"
        if not ocr_ready and not onnx_ready:
            return "模型离线"
        if not ocr_ready:
            return "OCR离线"
        return "ONNX离线"

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._start_camera()

    def hideEvent(self, event) -> None:  # noqa: N802
        super().hideEvent(event)
        self._stop_camera()

    def _set_camera_state(self, text: str, state: str) -> None:
        self.camera_state.setText(text)
        self.camera_state.setProperty("state", state)
        self.camera_state.style().unpolish(self.camera_state)
        self.camera_state.style().polish(self.camera_state)

    def _start_camera(self) -> None:
        self.model_state.setText(self._build_model_state_text())
        self._set_camera_state("连接中", "working")
        if not camera_service.open():
            self.preview_label.setText("摄像头暂时不可用\n可上传图片评测")
            self.btn_capture.setEnabled(False)
            self.btn_eval.setEnabled(False)
            self._set_camera_state("离线", "error")
            return

        self.btn_capture.setEnabled(True)
        self.btn_eval.setEnabled(True)
        self._set_camera_state("在线", "ready")
        self.preview_thread = PreviewThread(camera_service)
        self.preview_thread.frame_ready.connect(self._update_preview)
        self.preview_thread.start()

    def _stop_camera(self) -> None:
        if self.preview_thread:
            self.preview_thread.stop()
            self.preview_thread = None
        camera_service.close()

    def _update_preview(self, frame: np.ndarray) -> None:
        self.current_frame = frame.copy()
        display_frame = self._add_guide_overlay(frame)
        height, width, channels = display_frame.shape
        image = QImage(display_frame.data, width, height, channels * width, QImage.Format.Format_BGR888)
        pixmap = QPixmap.fromImage(image)
        scaled = pixmap.scaled(
            self.preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_label.setPixmap(scaled)

    def _add_guide_overlay(self, frame: np.ndarray) -> np.ndarray:
        overlay = frame.copy()
        height, width = overlay.shape[:2]
        box_size = min(width - 80, height - 40)
        x1 = max(20, (width - box_size) // 2)
        y1 = max(20, (height - box_size) // 2)
        x2 = x1 + box_size
        y2 = y1 + box_size

        color = (40, 40, 180)
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 2)
        cv2.line(overlay, ((x1 + x2) // 2, y1), ((x1 + x2) // 2, y2), color, 1)
        cv2.line(overlay, (x1, (y1 + y2) // 2), (x2, (y1 + y2) // 2), color, 1)
        cv2.putText(
            overlay,
            "Place one character in frame",
            (max(12, x1 - 10), min(height - 12, y2 + 22)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (100, 100, 120),
            1,
        )
        return overlay

    def _build_retry_guidance(self, exc: PreprocessingError) -> str:
        error_guidance = {
            "too_dark": "请把作品移到更亮的位置后重试。",
            "too_bright": "请避开强反光，再对准单字重试。",
            "low_contrast": "请换一张更清晰、字迹更明显的图片。",
            "empty_shot": "请让单字尽量占据取景框中央区域。",
            "obstruction": "请移开手和杂物，只保留目标单字。",
            "not_calligraphy": "当前画面不像单字书法，请重新对准作品。",
            "too_fragmented": "画面内容太散，请只保留一个字。",
            "scattered_content": "请靠近一点，让目标字更集中。",
            "ocr_failed": "这次未能稳定识别，请让主体更完整后重试。",
        }
        return error_guidance.get(exc.error_type, "请重新对准单字并再试一次。")

    def _handle_preprocessing_failure(self, exc: PreprocessingError, dialog_title: str) -> None:
        retry_guidance = self._build_retry_guidance(exc)
        self._set_camera_state("重试", "error")
        speech_service.speak_error(str(exc))
        QMessageBox.warning(self, dialog_title, f"{exc}\n\n建议：{retry_guidance}")

    def _run_evaluation(self, image: np.ndarray, original_path: Path) -> EvaluationResult:
        processed, processed_path = preprocessing_service.preprocess(image, save_processed=True)
        ocr_image = preprocessing_service.prepare_ocr_image(image)
        result = evaluation_service.evaluate(
            processed,
            original_image_path=str(original_path),
            processed_image_path=processed_path,
            ocr_image=ocr_image,
        )
        result.id = database_service.save(result)
        speech_service.speak_score(result.total_score, result.feedback)
        return result

    def _on_capture(self) -> None:
        if self.current_frame is None:
            QMessageBox.information(self, "暂无画面", "请等待摄像头预览稳定后再开始评测。")
            return

        self.btn_capture.setEnabled(False)
        self.btn_eval.setEnabled(False)
        self._set_camera_state("评测中", "working")

        timestamp = int(time.time() * 1000)
        original_path = IMAGES_DIR / f"original_{timestamp}.jpg"
        cv2.imwrite(str(original_path), self.current_frame)

        try:
            result = self._run_evaluation(self.current_frame, original_path)
            self._set_camera_state("完成", "ready")
            self.capture_completed.emit(result)
        except PreprocessingError as exc:
            self._handle_preprocessing_failure(exc, "请调整拍摄画面")
            self.btn_capture.setEnabled(True)
            self.btn_eval.setEnabled(True)
        except Exception as exc:  # noqa: BLE001
            self._set_camera_state("异常", "error")
            QMessageBox.critical(self, "评测失败", str(exc))
            self.btn_capture.setEnabled(True)
            self.btn_eval.setEnabled(True)

    def _on_load_image(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择书法图片",
            str(IMAGES_DIR),
            "图片文件 (*.jpg *.jpeg *.png *.bmp);;所有文件 (*)",
        )
        if not file_path:
            return

        image = self._read_image(file_path)
        if image is None:
            QMessageBox.warning(self, "读取失败", "无法读取所选图片，请换一张再试。")
            return

        self.current_frame = image.copy()
        self._set_camera_state("图片模式", "working")
        self._evaluate_image(image, Path(file_path))

    def _evaluate_image(self, image: np.ndarray, original_path: Path) -> None:
        self.btn_load.setEnabled(False)
        self.btn_load.setText("评测中...")
        try:
            result = self._run_evaluation(image, original_path)
            self._set_camera_state("完成", "ready")
            self.capture_completed.emit(result)
        except PreprocessingError as exc:
            self._handle_preprocessing_failure(exc, "图片内容不符合评测条件")
        except Exception as exc:  # noqa: BLE001
            self._set_camera_state("异常", "error")
            QMessageBox.critical(self, "评测失败", str(exc))
        finally:
            self.btn_load.setEnabled(True)
            self.btn_load.setText("上传图片")

    def _read_image(self, file_path: str) -> np.ndarray | None:
        try:
            with open(file_path, "rb") as file:
                data = np.frombuffer(file.read(), dtype=np.uint8)
            return cv2.imdecode(data, cv2.IMREAD_COLOR)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("读取图片失败: %s", exc)
            return None

    def cleanup(self) -> None:
        self._stop_camera()

    def set_compact_mode(self, compact: bool) -> None:
        self.compact_mode = compact
        self.preview_label.setFixedHeight(132)
