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
        self.compact_mode = False
        self.guide_steps: list[QLabel] = []
        self.focus_chips: list[QLabel] = []
        self._init_ui()

    def _init_ui(self) -> None:
        self.content_layout = QHBoxLayout(self)
        self.content_layout.setContentsMargins(4, 4, 4, 4)
        self.content_layout.setSpacing(12)

        preview_card = QFrame()
        preview_card.setObjectName("previewCard")
        self.preview_layout = QVBoxLayout(preview_card)
        self.preview_layout.setContentsMargins(16, 16, 16, 16)
        self.preview_layout.setSpacing(8)

        preview_header = QHBoxLayout()
        preview_title = QLabel("实时取景")
        preview_title.setObjectName("sectionTitle")
        preview_title.setFont(app_font(16, QFont.Weight.Bold))
        preview_header.addWidget(preview_title)
        preview_header.addStretch()

        self.camera_state = QLabel("准备中")
        self.camera_state.setObjectName("statusPill")
        preview_header.addWidget(self.camera_state)
        self.preview_layout.addLayout(preview_header)

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
        self.preview_layout.addWidget(self.preview_frame, stretch=1)

        self.preview_hint = QLabel("只保留单个汉字主体，尽量不要把整页练习纸、边框和大段注释一起拍进来。")
        self.preview_hint.setObjectName("sectionSubtitle")
        self.preview_hint.setWordWrap(True)
        self.preview_layout.addWidget(self.preview_hint)

        self.content_layout.addWidget(preview_card, stretch=7)

        self.side_widget = QWidget()
        self.side_layout = QVBoxLayout(self.side_widget)
        self.side_layout.setContentsMargins(0, 0, 0, 0)
        self.side_layout.setSpacing(10)

        self.guide_card = QFrame()
        self.guide_card.setObjectName("guideCard")
        guide_layout = QVBoxLayout(self.guide_card)
        guide_layout.setContentsMargins(16, 16, 16, 16)
        guide_layout.setSpacing(6)

        guide_title = QLabel("自动评测链路")
        guide_title.setObjectName("sectionTitle")
        guide_title.setFont(app_font(15, QFont.Weight.Bold))
        guide_layout.addWidget(guide_title)

        for text in [
            "1. 先提取单字主体，判断画面是否适合评测。",
            "2. 用本地官方 OCR 自动识别当前汉字。",
            "3. 再交给 ONNX 评分模型输出总分与等级。",
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

        self.action_hint = QLabel("让目标汉字落在取景框中央，再开始拍照。")
        self.action_hint.setObjectName("sectionSubtitle")
        self.action_hint.setWordWrap(True)
        self.action_hint.setFont(app_font(10))
        guide_layout.addWidget(self.action_hint)

        self.side_layout.addWidget(self.guide_card)

        self.focus_card = QFrame()
        self.focus_card.setObjectName("panelCard")
        focus_layout = QVBoxLayout(self.focus_card)
        focus_layout.setContentsMargins(16, 16, 16, 16)
        focus_layout.setSpacing(8)

        focus_title = QLabel("拍摄要求")
        focus_title.setObjectName("sectionTitle")
        focus_title.setFont(app_font(14, QFont.Weight.Bold))
        focus_layout.addWidget(focus_title)

        for text, name in [
            ("主体完整", "successChip"),
            ("尽量居中", "accentChip"),
            ("背景干净", "chipLabel"),
        ]:
            label = QLabel(text)
            label.setObjectName(name)
            focus_layout.addWidget(label, alignment=Qt.AlignmentFlag.AlignLeft)
            self.focus_chips.append(label)

        self.side_layout.addWidget(self.focus_card)

        self.action_card = QFrame()
        self.action_card.setObjectName("panelCard")
        action_layout = QVBoxLayout(self.action_card)
        action_layout.setContentsMargins(16, 16, 16, 16)
        action_layout.setSpacing(8)

        self.action_target = QLabel("当前为全自动识别评测模式")
        self.action_target.setObjectName("mutedLabel")
        self.action_target.setWordWrap(True)
        action_layout.addWidget(self.action_target)

        self.zoom_status = QLabel("取景：广角 / 1.0x")
        self.zoom_status.setObjectName("mutedLabel")
        self.zoom_status.setWordWrap(True)
        action_layout.addWidget(self.zoom_status)

        lens_layout = QHBoxLayout()
        lens_layout.setSpacing(6)
        self.btn_lens_wide = QPushButton("广角")
        self.btn_lens_standard = QPushButton("标准")
        self.btn_lens_detail = QPushButton("近景")
        for key, button in (
            ("wide", self.btn_lens_wide),
            ("standard", self.btn_lens_standard),
            ("detail", self.btn_lens_detail),
        ):
            button.setObjectName("ghostButton")
            button.setCheckable(True)
            button.setMinimumHeight(34)
            button.clicked.connect(lambda checked=False, lens=key: self._set_lens_mode(lens))
            lens_layout.addWidget(button)
        action_layout.addLayout(lens_layout)

        zoom_layout = QHBoxLayout()
        zoom_layout.setSpacing(8)
        self.btn_zoom_out = QPushButton("-")
        self.btn_zoom_out.setObjectName("ghostButton")
        self.btn_zoom_out.setMinimumHeight(34)
        self.btn_zoom_out.clicked.connect(lambda: self._nudge_zoom(-1))
        zoom_layout.addWidget(self.btn_zoom_out)

        self.btn_zoom_reset = QPushButton("重置取景")
        self.btn_zoom_reset.setObjectName("secondaryButton")
        self.btn_zoom_reset.setMinimumHeight(34)
        self.btn_zoom_reset.clicked.connect(self._reset_camera_view)
        zoom_layout.addWidget(self.btn_zoom_reset, stretch=1)

        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_in.setObjectName("ghostButton")
        self.btn_zoom_in.setMinimumHeight(34)
        self.btn_zoom_in.clicked.connect(lambda: self._nudge_zoom(1))
        zoom_layout.addWidget(self.btn_zoom_in)
        action_layout.addLayout(zoom_layout)

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
        self.btn_cancel.clicked.connect(self.cancelled.emit)
        action_layout.addWidget(self.btn_cancel)

        self.side_layout.addWidget(self.action_card)
        self.side_layout.addStretch()

        self.side_widget.setMaximumWidth(232)
        self.content_layout.addWidget(self.side_widget, stretch=3)
        self.side_layout.setStretch(0, 3)
        self.side_layout.setStretch(1, 2)
        self._refresh_camera_controls()

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

    def _set_action_hint(self, text: str) -> None:
        self.action_hint.setText(text)

    def _refresh_camera_controls(self) -> None:
        settings = camera_service.get_view_settings()
        self.zoom_status.setText(f"取景：{settings['lens_label']} / {settings['total_zoom']:.1f}x")
        self.btn_lens_wide.setChecked(settings["lens_mode"] == "wide")
        self.btn_lens_standard.setChecked(settings["lens_mode"] == "standard")
        self.btn_lens_detail.setChecked(settings["lens_mode"] == "detail")

    def _set_lens_mode(self, lens_mode: str) -> None:
        settings = camera_service.set_view_settings(lens_mode=lens_mode)
        self._refresh_camera_controls()
        self._set_action_hint(f"当前取景已切到{settings['lens_label']}，可以观察构图后再拍照。")

    def _nudge_zoom(self, direction: int) -> None:
        settings = camera_service.nudge_zoom(direction)
        self._refresh_camera_controls()
        self._set_action_hint(f"当前数码变焦为 {settings['total_zoom']:.1f}x，请确认主体仍在取景框中央。")

    def _reset_camera_view(self) -> None:
        settings = camera_service.reset_view_settings()
        self._refresh_camera_controls()
        self._set_action_hint(f"取景已重置为默认{settings['lens_label']}视图。")

    def _start_camera(self) -> None:
        self._refresh_camera_controls()
        self._set_camera_state("连接中", "working")
        self.status_label.setText("正在尝试连接树莓派摄像头...")
        self._set_action_hint("正在连接相机，请稍等；看到实时画面后再开始拍照。")

        if not camera_service.open():
            self.preview_label.setText("相机暂时不可用\n你仍然可以载入图片完成评测。")
            self.btn_capture.setEnabled(False)
            self._set_camera_state("离线", "error")
            self.status_label.setText("未能打开摄像头，建议检查连接，或先使用图片评测继续演示。")
            self._set_action_hint("如现场摄像头异常，可以先用“载入图片评测”继续演示流程。")
            return

        self.btn_capture.setEnabled(True)
        self._set_camera_state("在线", "ready")
        self.status_label.setText("相机已就绪，请将单个汉字放到取景框中央。")
        self._set_action_hint("保持主体清晰、居中、无遮挡，系统会自动识别当前汉字。")

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

        settings = camera_service.get_view_settings()
        caption = f"AUTO OCR · {settings['lens_label']} {settings['total_zoom']:.1f}x"
        caption_width = max(152, 18 + len(caption) * 10)
        cv2.rectangle(overlay, (x1, y2 + 10), (x1 + caption_width, y2 + 40), (34, 25, 19), -1)
        cv2.putText(
            overlay,
            caption,
            (x1 + 10, y2 + 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (245, 235, 222),
            1,
        )

        return overlay

    def _build_retry_guidance(self, exc: PreprocessingError) -> str:
        error_guidance = {
            "too_dark": "把纸张移到更亮的位置，再让镜头正对作品后重拍。",
            "too_bright": "避开顶灯反光或窗边强光，让纸面亮但不过曝。",
            "low_contrast": "请换一张更清晰的作品，或让墨迹和背景分离得更明显。",
            "empty_shot": "把单个汉字移到取景框中央，尽量占满参考框的大部分。",
            "obstruction": "移开手、桌面杂物和纸张边缘，只保留要评测的字。",
            "not_calligraphy": "当前画面不像单个毛笔字。请重新对准作品，避免拍到大块色块、边框或空白纸面。",
            "too_fragmented": "画面里的内容太散。请只保留一个字，尽量不要把整页一起拍进去。",
            "scattered_content": "请再靠近一点，让目标汉字更集中地落在取景框中央。",
            "ocr_failed": "系统这次没能稳定识别这个字，请让主体更完整、更居中后重拍。",
        }
        return error_guidance.get(exc.error_type, "请按照取景框重新对准单个汉字后再试一次。")

    def _handle_preprocessing_failure(self, exc: PreprocessingError, dialog_title: str) -> None:
        retry_guidance = self._build_retry_guidance(exc)
        self._set_camera_state("需重拍", "error")
        self.status_label.setText(str(exc))
        self._set_action_hint(retry_guidance)
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
        self._release_preprocessing_memory()
        return result

    def _on_capture(self) -> None:
        if self.current_frame is None:
            QMessageBox.information(self, "暂无画面", "请等待摄像头预览稳定后再拍照。")
            return

        self.btn_capture.setEnabled(False)
        self._set_camera_state("评测中", "working")
        self.status_label.setText("正在预处理图像并生成评测结果...")
        self._set_action_hint("系统会先自动识别当前汉字，再直接给出总分与等级。")

        timestamp = int(time.time() * 1000)
        original_path = IMAGES_DIR / f"original_{timestamp}.jpg"
        cv2.imwrite(str(original_path), self.current_frame)

        try:
            result = self._run_evaluation(self.current_frame, original_path)
            self._set_camera_state("完成", "ready")
            self.status_label.setText("评测完成，正在打开结果页。")
            self._set_action_hint("本次结果已经生成。你可以继续拍下一张，或直接向评委讲解识别字、总分和等级。")
            self.capture_completed.emit(result)
        except PreprocessingError as exc:
            self._handle_preprocessing_failure(exc, "请调整拍摄画面")
            self.btn_capture.setEnabled(True)
        except Exception as exc:  # noqa: BLE001
            self._set_camera_state("异常", "error")
            self.status_label.setText("评测流程中断，请查看错误信息。")
            self._set_action_hint("评测流程意外中断。可以先回到首页，再重新进入拍照页。")
            QMessageBox.critical(self, "评测失败", str(exc))
            self.btn_capture.setEnabled(True)

    def _release_preprocessing_memory(self) -> None:
        try:
            preprocessing_service.release_memory()
        except Exception as exc:  # noqa: BLE001
            self.logger.debug("Skip preprocessing memory cleanup: %s", exc)

    def _on_load_image(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择书法图片",
            str(IMAGES_DIR),
            "图片文件 (*.jpg *.jpeg *.png *.bmp);;所有文件(*)",
        )
        if not file_path:
            return

        image = self._read_image(file_path)
        if image is None:
            QMessageBox.warning(self, "读取失败", "无法读取所选图片，请换一张再试。")
            return

        self.current_frame = image.copy()
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
        self._set_camera_state("图片模式", "working")
        self.status_label.setText("正在使用载入的图片进行评测...")
        self._set_action_hint("系统会先自动 OCR 识别，再进入 ONNX 评分。")

        try:
            result = self._run_evaluation(image, original_path)
            self._set_camera_state("完成", "ready")
            self.status_label.setText("图片评测完成，正在打开结果页。")
            self._set_action_hint("图片评测已经完成。若要继续演示，建议换一张不同字形或不同质量的作品。")
            self.capture_completed.emit(result)
        except PreprocessingError as exc:
            self._handle_preprocessing_failure(exc, "图片内容不符合评测条件")
        except Exception as exc:  # noqa: BLE001
            self._set_camera_state("异常", "error")
            self.status_label.setText("评测流程中断，请查看错误信息。")
            self._set_action_hint("图片评测中断。建议换一张更干净、更居中的作品图片。")
            QMessageBox.critical(self, "评测失败", str(exc))
        finally:
            self.btn_load.setEnabled(True)
            self.btn_load.setText("载入图片评测")

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
        if compact == self.compact_mode:
            return

        self.compact_mode = compact
        self.content_layout.setDirection(QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight)
        self.content_layout.setSpacing(8 if compact else 12)
        self.preview_layout.setContentsMargins(12 if compact else 16, 12 if compact else 16, 12 if compact else 16, 12 if compact else 16)
        self.side_layout.setSpacing(8 if compact else 10)
        self.preview_label.setMinimumSize(240 if compact else 430, 136 if compact else 270)
        self.preview_hint.setVisible(not compact)
        self.side_widget.setMaximumWidth(16777215 if compact else 232)
        self.action_target.setText("全自动识别评测" if compact else "当前为全自动识别评测模式")
        self.focus_card.setVisible(True)

        for index, label in enumerate(self.guide_steps):
            label.setVisible(not compact or index == 0)

        for index, label in enumerate(self.focus_chips):
            label.setVisible(not compact or index < 2)

        self.btn_capture.setMinimumHeight(42 if compact else 48)
        self.btn_load.setMinimumHeight(40 if compact else 46)
        self.btn_cancel.setMinimumHeight(38 if compact else 42)
