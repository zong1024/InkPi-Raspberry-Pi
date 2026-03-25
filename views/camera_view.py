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
from PyQt6.QtWidgets import (
    QBoxLayout,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

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
    """Touch-first capture page."""

    capture_completed = pyqtSignal(EvaluationResult)
    cancelled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.preview_thread: PreviewThread | None = None
        self.current_frame: np.ndarray | None = None
        self._compact_mode = False
        self.guide_steps: list[QLabel] = []
        self._init_ui()

    def _init_ui(self) -> None:
        self.content_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self.content_layout.setContentsMargins(4, 4, 4, 4)
        self.content_layout.setSpacing(12)

        preview_card = QFrame()
        preview_card.setObjectName("previewCard")
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(16, 16, 16, 16)
        preview_layout.setSpacing(8)

        preview_header = QHBoxLayout()
        preview_header.setSpacing(10)

        preview_title = QLabel("实时取景")
        preview_title.setObjectName("sectionTitle")
        preview_title.setFont(app_font(16, QFont.Weight.Bold))
        preview_header.addWidget(preview_title)

        preview_header.addStretch()

        self.camera_state = QLabel("准备中")
        self.camera_state.setObjectName("statusPill")
        preview_header.addWidget(self.camera_state)

        preview_layout.addLayout(preview_header)

        self.preview_frame = QFrame()
        self.preview_frame.setObjectName("previewFrame")
        self.preview_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        frame_layout = QVBoxLayout(self.preview_frame)
        frame_layout.setContentsMargins(14, 14, 14, 14)

        self.preview_label = QLabel("正在准备相机...")
        self.preview_label.setObjectName("previewLabel")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(430, 270)
        self.preview_label.setWordWrap(True)
        self.preview_label.setFont(app_font(12))
        frame_layout.addWidget(self.preview_label)

        preview_layout.addWidget(self.preview_frame, stretch=1)

        self.preview_hint = QLabel("单字尽量占画面 60% 左右，避免纸张边缘进入取景框。")
        self.preview_hint.setObjectName("sectionSubtitle")
        self.preview_hint.setWordWrap(True)
        preview_layout.addWidget(self.preview_hint)

        self.content_layout.addWidget(preview_card, stretch=7)

        self.side_layout = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        self.side_layout.setSpacing(10)

        self.guide_card = QFrame()
        self.guide_card.setObjectName("guideCard")
        guide_layout = QVBoxLayout(self.guide_card)
        guide_layout.setContentsMargins(16, 16, 16, 16)
        guide_layout.setSpacing(6)

        guide_title = QLabel("拍摄引导")
        guide_title.setObjectName("sectionTitle")
        guide_title.setFont(app_font(15, QFont.Weight.Bold))
        guide_layout.addWidget(guide_title)

        self.guide_badge = QLabel("拍摄前检查")
        self.guide_badge.setObjectName("chipLabel")
        guide_layout.addWidget(self.guide_badge, alignment=Qt.AlignmentFlag.AlignLeft)

        for text in [
            "1. 只保留一个汉字，避免整页一起入镜。",
            "2. 使用浅色背景，并尽量减少阴影和反光。",
        ]:
            label = QLabel(text)
            label.setObjectName("sectionSubtitle")
            label.setWordWrap(True)
            guide_layout.addWidget(label)
            self.guide_steps.append(label)

        self.status_label = QLabel("等待相机就绪")
        self.status_label.setObjectName("sectionSubtitle")
        self.status_label.setWordWrap(True)
        guide_layout.addWidget(self.status_label)

        self.source_label = QLabel("输入来源：摄像头")
        self.source_label.setObjectName("mutedLabel")
        guide_layout.addWidget(self.source_label)

        self.action_hint = QLabel(
            "准备好后点击“拍照并评测”，系统会先检查画面里是否真的有可评测的单个毛笔字。"
        )
        self.action_hint.setObjectName("sectionSubtitle")
        self.action_hint.setWordWrap(True)
        self.action_hint.setFont(app_font(10))
        guide_layout.addWidget(self.action_hint)

        self.side_layout.addWidget(self.guide_card)

        self.action_card = QFrame()
        self.action_card.setObjectName("panelCard")
        action_layout = QVBoxLayout(self.action_card)
        action_layout.setContentsMargins(16, 16, 16, 16)
        action_layout.setSpacing(8)

        self.btn_capture = QPushButton("拍照并评测")
        self.btn_capture.setObjectName("primaryButton")
        self.btn_capture.setMinimumHeight(48)
        self.btn_capture.clicked.connect(self._on_capture)
        action_layout.addWidget(self.btn_capture)

        self.btn_load = QPushButton("载入图片评测")
        self.btn_load.setObjectName("secondaryButton")
        self.btn_load.setMinimumHeight(46)
        self.btn_load.clicked.connect(self._on_load_image)
        action_layout.addWidget(self.btn_load)

        self.btn_cancel = QPushButton("返回首页")
        self.btn_cancel.setObjectName("ghostButton")
        self.btn_cancel.setMinimumHeight(42)
        self.btn_cancel.clicked.connect(self._on_cancel)
        action_layout.addWidget(self.btn_cancel)

        self.side_layout.addWidget(self.action_card)
        self.side_layout.addStretch()

        self.side_widget = QWidget()
        self.side_widget.setLayout(self.side_layout)
        self.side_widget.setMaximumWidth(232)
        self.side_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.content_layout.addWidget(self.side_widget, stretch=3)
        self.side_layout.setStretch(0, 3)
        self.side_layout.setStretch(1, 2)
        self._update_layout_mode()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._start_camera()

    def hideEvent(self, event) -> None:  # noqa: N802
        super().hideEvent(event)
        self._stop_camera()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_layout_mode()

    def _update_layout_mode(self) -> None:
        compact = self.width() < 760 or self.height() < 430
        if compact == self._compact_mode:
            return

        self._compact_mode = compact
        if compact:
            self.content_layout.setDirection(QBoxLayout.Direction.TopToBottom)
            self.side_layout.setDirection(QBoxLayout.Direction.TopToBottom)
            self.side_widget.setMaximumWidth(16777215)
            self.side_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            self.preview_label.setMinimumSize(220, 160)
            self.preview_hint.setVisible(False)
            for label in self.guide_steps:
                label.setVisible(False)
            self.btn_capture.setMinimumHeight(42)
            self.btn_load.setMinimumHeight(40)
            self.btn_cancel.setMinimumHeight(38)
        else:
            self.content_layout.setDirection(QBoxLayout.Direction.LeftToRight)
            self.side_layout.setDirection(QBoxLayout.Direction.TopToBottom)
            self.side_widget.setMaximumWidth(232)
            self.side_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
            self.preview_label.setMinimumSize(430, 270)
            self.preview_hint.setVisible(True)
            for label in self.guide_steps:
                label.setVisible(True)
            self.btn_capture.setMinimumHeight(48)
            self.btn_load.setMinimumHeight(46)
            self.btn_cancel.setMinimumHeight(42)

    def _set_camera_state(self, text: str, state: str) -> None:
        self.camera_state.setText(text)
        self.camera_state.setProperty("state", state)
        self.camera_state.style().unpolish(self.camera_state)
        self.camera_state.style().polish(self.camera_state)

    def _set_action_hint(self, text: str, badge: str | None = None) -> None:
        self.action_hint.setText(text)
        if badge:
            self.guide_badge.setText(badge)

    def _build_retry_guidance(self, exc: PreprocessingError) -> str:
        error_guidance = {
            "too_dark": "把纸张移到更亮的地方，再让镜头正对作品后重拍。",
            "too_bright": "避开顶灯反光或窗边强光，让纸面亮但不过曝。",
            "low_contrast": "请换一张更清晰的作品，或让墨迹和背景分离得更明显。",
            "empty_shot": "把单个汉字移到取景框中央，尽量占满参考框的六成以上。",
            "obstruction": "移开手、桌面杂物和纸张边缘，只保留要评测的字。",
            "not_calligraphy": "当前画面不像单个毛笔字。请重新对准作品，避免拍到色块、边框或空白纸面。",
            "too_fragmented": "画面里的内容太散。请只保留一个字，尽量不要把整页一起拍进去。",
            "scattered_content": "请再靠近一点，让目标汉字更集中地落在取景框中央。",
        }
        return error_guidance.get(exc.error_type, "请按照取景框重新对准单个汉字后再试一次。")

    def _handle_preprocessing_failure(self, exc: PreprocessingError, dialog_title: str) -> None:
        retry_guidance = self._build_retry_guidance(exc)
        self._set_camera_state("需重拍", "error")
        self.status_label.setText(str(exc))
        self._set_action_hint(retry_guidance, badge="重拍建议")
        speech_service.speak_error(str(exc))
        QMessageBox.warning(self, dialog_title, f"{exc}\n\n建议：{retry_guidance}")

    def _start_camera(self) -> None:
        self._set_camera_state("连接中", "working")
        self.status_label.setText("正在尝试连接树莓派摄像头...")
        self.source_label.setText("输入来源：摄像头")
        self._set_action_hint("正在连接相机，请稍等一秒；看到实时画面后再开始拍照。", "连接中")

        if not camera_service.open():
            self.preview_label.setText("相机暂时不可用\n你仍然可以载入图片完成评测。")
            self.btn_capture.setEnabled(False)
            self._set_camera_state("离线", "error")
            self.status_label.setText("未能打开摄像头，建议检查连接或直接使用图片评测。")
            self._set_action_hint(
                "如果评委现场相机异常，可以先用“载入图片评测”继续演示流程。",
                "相机异常",
            )
            return

        self.btn_capture.setEnabled(True)
        self._set_camera_state("在线", "ready")
        self.status_label.setText("相机已就绪，请将单个汉字放到取景框中央。")
        self._set_action_hint("让单个汉字落在参考框中央，尽量不要把整页纸一起拍进来。", "拍摄中")

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
        bytes_per_line = channels * width
        image = QImage(display_frame.data, width, height, bytes_per_line, QImage.Format.Format_BGR888)
        pixmap = QPixmap.fromImage(image)
        scaled = pixmap.scaled(
            self.preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_label.setPixmap(scaled)

    def _add_guide_overlay(self, frame: np.ndarray) -> np.ndarray:
        overlay = frame.copy()
        height, width = overlay.shape[:2]

        guide_size = max(120, min(width, height) - 54)
        x1 = (width - guide_size) // 2
        y1 = (height - guide_size) // 2
        x2 = x1 + guide_size
        y2 = y1 + guide_size

        accent = (95, 161, 201)
        soft = (149, 170, 183)
        cv2.rectangle(overlay, (x1, y1), (x2, y2), accent, 2)

        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        cv2.line(overlay, (x1, center_y), (x2, center_y), soft, 1)
        cv2.line(overlay, (center_x, y1), (center_x, y2), soft, 1)
        cv2.line(overlay, (x1, y1), (x2, y2), soft, 1)
        cv2.line(overlay, (x1, y2), (x2, y1), soft, 1)

        corner_length = 24
        for start, mid1, mid2 in [
            ((x1, y1), (x1 + corner_length, y1), (x1, y1 + corner_length)),
            ((x2, y1), (x2 - corner_length, y1), (x2, y1 + corner_length)),
            ((x1, y2), (x1 + corner_length, y2), (x1, y2 - corner_length)),
            ((x2, y2), (x2 - corner_length, y2), (x2, y2 - corner_length)),
        ]:
            cv2.line(overlay, start, mid1, accent, 3)
            cv2.line(overlay, start, mid2, accent, 3)

        caption = "Single Char"
        cv2.rectangle(overlay, (x1, y2 + 10), (x1 + 152, y2 + 40), (34, 25, 19), -1)
        cv2.putText(overlay, caption, (x1 + 10, y2 + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (245, 235, 222), 1)

        return overlay

    def _run_evaluation(self, image: np.ndarray, original_path: Path) -> EvaluationResult:
        processed, processed_path = preprocessing_service.preprocess(image, save_processed=True)
        result = evaluation_service.evaluate(
            processed,
            original_image_path=str(original_path),
            processed_image_path=processed_path,
            texture_image=image,
        )
        result.id = database_service.save(result)
        speech_service.speak_score(result.total_score, result.feedback)
        self._release_preprocessing_memory()
        return result

    def _on_capture(self) -> None:
        if self.current_frame is None:
            QMessageBox.information(self, "暂无画面", "请等待摄像头预览稳定后再拍照。")
            return

        self.btn_capture.setEnabled(False)
        self._set_camera_state("评测中", "working")
        self.status_label.setText("正在预处理图像并生成评测结果...")
        self._set_action_hint(
            "系统正在检查画面里是否是清晰的单个毛笔字，并生成评测结果。",
            "评测中",
        )

        timestamp = int(time.time() * 1000)
        original_path = IMAGES_DIR / f"original_{timestamp}.jpg"
        cv2.imwrite(str(original_path), self.current_frame)

        try:
            result = self._run_evaluation(self.current_frame, original_path)
            self._set_camera_state("完成", "ready")
            self.status_label.setText("评测完成，正在打开结果页。")
            self._set_action_hint(
                "这次结果已经生成。你可以继续拍下一张，或者直接向评委讲解评分维度。",
                "评测完成",
            )
            self.capture_completed.emit(result)
        except PreprocessingError as exc:
            self._handle_preprocessing_failure(exc, "请调整拍摄画面")
            self.btn_capture.setEnabled(True)
        except Exception as exc:  # noqa: BLE001
            self._set_camera_state("异常", "error")
            self.status_label.setText("评测流程中断，请查看错误信息。")
            self._set_action_hint("评测流程意外中断。可以先回到首页，再重新进入拍照页。", "系统异常")
            QMessageBox.critical(self, "评测失败", str(exc))
            self.btn_capture.setEnabled(True)

    def _release_preprocessing_memory(self) -> None:
        try:
            preprocessing_service.release_memory()
        except Exception as exc:  # noqa: BLE001
            self.logger.debug("Skip preprocessing memory cleanup: %s", exc)

    def _on_cancel(self) -> None:
        self.cancelled.emit()

    def _on_load_image(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择书法图片",
            str(IMAGES_DIR),
            "图片文件 (*.jpg *.jpeg *.png *.bmp);;所有文件 (*)",
        )
        if not file_path:
            return

        image = self._read_image_chinese(file_path)
        if image is None:
            QMessageBox.warning(self, "读取失败", "无法读取所选图片，请换一张再试。")
            return

        self.current_frame = image.copy()
        self.source_label.setText(f"输入来源：图片 / {Path(file_path).name}")
        self._set_camera_state("图片模式", "working")
        self.status_label.setText("正在使用载入的图片进行评测...")
        self._set_action_hint("系统会先检查这张图片里是不是单个毛笔字，再进入评分。", "图片模式")

        display_frame = self._add_guide_overlay(image)
        height, width, channels = display_frame.shape
        bytes_per_line = channels * width
        qt_image = QImage(display_frame.data, width, height, bytes_per_line, QImage.Format.Format_BGR888)
        pixmap = QPixmap.fromImage(qt_image)
        scaled = pixmap.scaled(
            self.preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_label.setPixmap(scaled)

        self._evaluate_image(image, Path(file_path))

    def _evaluate_image(self, image: np.ndarray, original_path: Path) -> None:
        self.btn_load.setEnabled(False)
        self.btn_load.setText("评测中...")

        try:
            result = self._run_evaluation(image, original_path)
            self._set_camera_state("完成", "ready")
            self.status_label.setText("图片评测完成，正在打开结果页。")
            self._set_action_hint(
                "图片评测已完成。若要继续演示，建议换一张不同书体或不同得分的作品。",
                "评测完成",
            )
            self.capture_completed.emit(result)
        except PreprocessingError as exc:
            self._handle_preprocessing_failure(exc, "图片内容不符合评测条件")
        except Exception as exc:  # noqa: BLE001
            self._set_camera_state("异常", "error")
            self.status_label.setText("评测流程中断，请查看错误信息。")
            self._set_action_hint("图片评测中断。建议换一张更干净、更居中的作品图片。", "系统异常")
            QMessageBox.critical(self, "评测失败", str(exc))
        finally:
            self.btn_load.setEnabled(True)
            self.btn_load.setText("载入图片评测")

    def _read_image_chinese(self, file_path: str) -> np.ndarray | None:
        try:
            with open(file_path, "rb") as file:
                data = np.frombuffer(file.read(), dtype=np.uint8)
            return cv2.imdecode(data, cv2.IMREAD_COLOR)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("读取图片失败: %s", exc)
            return None

    def cleanup(self) -> None:
        self._stop_camera()
