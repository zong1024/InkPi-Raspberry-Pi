"""Camera view for capture and evaluation."""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QImage, QPixmap
from PyQt6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from config import IMAGES_DIR
from models.evaluation_result import EvaluationResult
from services.camera_service import CameraService, camera_service
from services.database_service import database_service
from services.evaluation_service import evaluation_service
from services.preprocessing_service import PreprocessingError, preprocessing_service
from services.speech_service import speech_service
from views.ui_theme import app_font, display_font, icon_font

sys.path.insert(0, str(Path(__file__).parent.parent))


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
    """Capture page designed around a clear score-to-retry loop."""

    capture_completed = pyqtSignal(EvaluationResult)
    cancelled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.preview_thread: PreviewThread | None = None
        self.current_frame: np.ndarray | None = None
        self._idle_hint = "拍前确认：单字完整入框，纸面摆正，光线尽量均匀。"
        self._init_ui()

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        header = QFrame()
        header.setObjectName("pageHeader")
        header.setFixedHeight(28)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(4, 1, 4, 1)
        header_layout.setSpacing(6)

        self.btn_back = QPushButton("←")
        self.btn_back.setObjectName("headerIconButton")
        self.btn_back.setFixedSize(24, 24)
        self.btn_back.setFont(icon_font(12, QFont.Weight.Bold))
        self.btn_back.clicked.connect(self.cancelled.emit)
        header_layout.addWidget(self.btn_back)

        header_layout.addStretch()

        title = QLabel("INKPI CAPTURE")
        title.setObjectName("pageTitle")
        title.setFont(display_font(10, QFont.Weight.Bold))
        header_layout.addWidget(title)

        header_layout.addStretch()

        self.camera_state = QLabel("连接中")
        self.camera_state.setObjectName("statusPill")
        self.camera_state.setFont(app_font(7, QFont.Weight.Bold))
        header_layout.addWidget(self.camera_state)
        root.addWidget(header)

        guide_card = QFrame()
        guide_card.setObjectName("actionCard")
        guide_card.setFixedHeight(28)
        guide_layout = QHBoxLayout(guide_card)
        guide_layout.setContentsMargins(10, 4, 10, 4)
        guide_layout.setSpacing(5)

        guide_title = QLabel("拍前确认")
        guide_title.setObjectName("miniLabel")
        guide_title.setFont(app_font(7, QFont.Weight.Bold))
        guide_layout.addWidget(guide_title)

        self.capture_hint = QLabel(self._idle_hint)
        self.capture_hint.setObjectName("hintText")
        self.capture_hint.setFont(app_font(6, QFont.Weight.Bold))
        guide_layout.addWidget(self.capture_hint, stretch=1)
        root.addWidget(guide_card)

        self.preview_label = QLabel("正在连接摄像头…")
        self.preview_label.setObjectName("previewLabel")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setWordWrap(True)
        self.preview_label.setFixedHeight(164)
        self.preview_label.setFont(app_font(10))
        root.addWidget(self.preview_label)

        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(8)

        self.btn_load = QPushButton("上传图片")
        self.btn_load.setObjectName("buttonCard")
        self.btn_load.setFixedSize(88, 46)
        self.btn_load.setFont(app_font(8, QFont.Weight.Bold))
        self.btn_load.clicked.connect(self._on_load_image)
        bottom_row.addWidget(self.btn_load)

        self.btn_capture = QPushButton("拍")
        self.btn_capture.setObjectName("floatingButton")
        self.btn_capture.setFixedSize(52, 52)
        self.btn_capture.setFont(display_font(12, QFont.Weight.Bold))
        self.btn_capture.clicked.connect(self._on_capture)
        bottom_row.addWidget(self.btn_capture, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.btn_eval = QPushButton("生成评分与建议")
        self.btn_eval.setObjectName("primaryButton")
        self.btn_eval.setFixedSize(160, 46)
        self.btn_eval.setFont(display_font(8, QFont.Weight.Bold))
        self.btn_eval.clicked.connect(self._on_capture)
        bottom_row.addWidget(self.btn_eval)
        root.addLayout(bottom_row)

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

    def _set_capture_hint(self, text: str) -> None:
        self.capture_hint.setText(text)

    def _start_camera(self) -> None:
        self._set_camera_state("连接中", "working")
        self._set_capture_hint(self._idle_hint)
        if not camera_service.open():
            self.preview_label.setText("摄像头暂不可用。\n你仍然可以直接上传图片完成评测。")
            self.btn_capture.setEnabled(False)
            self.btn_eval.setEnabled(False)
            self._set_capture_hint("摄像头离线，可改用上传图片继续生成本轮建议。")
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

        box_size = min(width - 110, height - 70)
        x1 = (width - box_size) // 2
        y1 = (height - box_size) // 2
        x2 = x1 + box_size
        y2 = y1 + box_size
        accent = (31, 15, 184)
        muted = (110, 104, 96)

        cv2.rectangle(overlay, (x1, y1), (x2, y2), accent, 2)
        corner = 18
        for origin, a, b in (
            ((x1, y1), (x1 + corner, y1), (x1, y1 + corner)),
            ((x2, y1), (x2 - corner, y1), (x2, y1 + corner)),
            ((x1, y2), (x1 + corner, y2), (x1, y2 - corner)),
            ((x2, y2), (x2 - corner, y2), (x2, y2 - corner)),
        ):
            cv2.line(overlay, origin, a, accent, 3)
            cv2.line(overlay, origin, b, accent, 3)

        cv2.putText(
            overlay,
            "Center one character",
            (max(18, x1 - 8), min(height - 14, y2 + 24)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            muted,
            1,
        )
        return overlay

    def _build_retry_guidance(self, exc: PreprocessingError) -> str:
        error_guidance = {
            "too_dark": "请把作品移到更亮的位置后再试。",
            "too_bright": "请避开反光后重新对准单字。",
            "low_contrast": "请换一张更清晰、笔画更明显的图片。",
            "empty_shot": "请让单字尽量位于取景框中央。",
            "obstruction": "请移开手部或杂物，只保留目标单字。",
            "not_calligraphy": "当前画面不像单字书法，请重新对准作品。",
            "too_fragmented": "画面内容过于零散，请只保留一个字。",
            "scattered_content": "请靠近一点，让目标单字更集中。",
            "ocr_failed": "这次未能稳定识别，请让主体更完整后重试。",
        }
        return error_guidance.get(exc.error_type, "请重新对准单字后再试一次。")

    def _handle_preprocessing_failure(self, exc: PreprocessingError, dialog_title: str) -> None:
        retry_guidance = self._build_retry_guidance(exc)
        self._set_camera_state("重试", "error")
        self._set_capture_hint(f"请重拍：{retry_guidance}")
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
            QMessageBox.information(self, "暂无画面", "请等待摄像头画面稳定后再开始评测。")
            return

        self.btn_capture.setEnabled(False)
        self.btn_eval.setEnabled(False)
        self._set_capture_hint("正在评分，并生成下一轮练习建议…")
        self._set_camera_state("评测中", "working")

        timestamp = int(time.time() * 1000)
        original_path = IMAGES_DIR / f"original_{timestamp}.jpg"
        cv2.imwrite(str(original_path), self.current_frame)

        try:
            result = self._run_evaluation(self.current_frame, original_path)
            self._set_capture_hint("评测完成，正在打开结果建议。")
            self._set_camera_state("完成", "ready")
            self.capture_completed.emit(result)
        except PreprocessingError as exc:
            self._handle_preprocessing_failure(exc, "请调整拍摄画面")
            self.btn_capture.setEnabled(True)
            self.btn_eval.setEnabled(True)
        except Exception as exc:  # noqa: BLE001
            self._set_camera_state("异常", "error")
            self._set_capture_hint("评测失败，请稍后重试或改用上传图片。")
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
            QMessageBox.warning(self, "读取失败", "无法读取所选图片，请更换一张后重试。")
            return

        self.current_frame = image.copy()
        self._set_capture_hint("正在解析图片，并生成本轮评分与建议…")
        self._set_camera_state("图片模式", "working")
        self._evaluate_image(image, Path(file_path))

    def _evaluate_image(self, image: np.ndarray, original_path: Path) -> None:
        self.btn_load.setEnabled(False)
        self.btn_load.setText("评测中")
        try:
            result = self._run_evaluation(image, original_path)
            self._set_capture_hint("评测完成，正在打开结果建议。")
            self._set_camera_state("完成", "ready")
            self.capture_completed.emit(result)
        except PreprocessingError as exc:
            self._handle_preprocessing_failure(exc, "图片内容不符合评测条件")
        except Exception as exc:  # noqa: BLE001
            self._set_camera_state("异常", "error")
            self._set_capture_hint("图片评测失败，请更换图片后重试。")
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
        del compact
