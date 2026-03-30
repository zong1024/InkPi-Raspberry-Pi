"""Local WebUI for InkPi."""

from __future__ import annotations

import base64
import io
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from flask import Flask, jsonify, request, send_file, send_from_directory

from config import APP_CONFIG, IMAGES_DIR, IS_RASPBERRY_PI, LOG_CONFIG
from models.evaluation_result import EvaluationResult
from services.camera_service import camera_service
from services.database_service import database_service
from services.evaluation_service import evaluation_service
from services.preprocessing_service import PreprocessingError, preprocessing_service
from services.speech_service import speech_service


GUIDANCE_BY_ERROR = {
    "too_dark": "请把作品移到更亮的位置，再让镜头正对纸面。",
    "too_bright": "请避开强反光和直射光，让纸面亮但不过曝。",
    "low_contrast": "请换一张更清晰的作品，或让墨迹和背景更分离。",
    "empty_shot": "请只保留一个汉字，并把主体放到画面中央。",
    "obstruction": "请移开手部、桌面杂物和边框遮挡，只保留作品主体。",
    "not_calligraphy": "当前画面不像单个毛笔字，请重新对准作品后再试。",
    "too_fragmented": "画面内容过于零散，请靠近一点并只保留单个汉字。",
    "scattered_content": "主体过散，请让目标汉字更集中地落在取景框中央。",
    "ocr_failed": "系统暂时没能稳定认出这个字，请让主体更完整、更居中后重拍。",
}

LEVEL_LABELS = {
    "good": "好",
    "medium": "中",
    "bad": "坏",
}


@dataclass
class WebUiState:
    """Shared in-process UI state."""

    last_result_id: int | None = None
    last_result: EvaluationResult | None = None
    camera_online: bool = False
    camera_last_error: str | None = None
    updated_at: float = field(default_factory=time.time)
    lock: threading.RLock = field(default_factory=threading.RLock)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "camera_online": self.camera_online,
                "camera_last_error": self.camera_last_error,
                "last_result_id": self.last_result_id,
                "updated_at": self.updated_at,
            }


state = WebUiState()


def _setup_logging() -> None:
    if logging.getLogger().handlers:
        return

    log_file = LOG_CONFIG.get("log_file")
    handlers = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=getattr(logging, str(LOG_CONFIG.get("level", "INFO")).upper(), logging.INFO),
        format=LOG_CONFIG.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
        handlers=handlers,
    )


def create_app() -> Flask:
    """Build the Flask app."""

    _setup_logging()
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.logger.setLevel(logging.INFO)

    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.get("/api/health")
    def health():
        return jsonify(
            {
                "status": "ok",
                "app_name": APP_CONFIG["app_name"],
                "version": APP_CONFIG["version"],
                "raspberry_pi": IS_RASPBERRY_PI,
                "camera_available": camera_service.available,
                "timestamp": time.time(),
            }
        )

    @app.get("/api/bootstrap")
    def bootstrap():
        stats = database_service.get_statistics()
        recent_results = database_service.get_recent(8)
        return jsonify(
            {
                "app": {
                    "name": APP_CONFIG["app_name"],
                    "version": APP_CONFIG["version"],
                    "mode": "raspberry-pi" if IS_RASPBERRY_PI else "desktop",
                },
                "camera": _get_camera_status(),
                "stats": _serialize_stats(stats),
                "history": [_serialize_result(result) for result in recent_results],
                "last_result": _serialize_result(state.last_result) if state.last_result else None,
            }
        )

    @app.get("/api/history")
    def history():
        limit = min(max(int(request.args.get("limit", 40)), 1), 200)
        records = database_service.get_all(limit=limit)
        return jsonify({"items": [_serialize_result(item) for item in records]})

    @app.get("/api/results/<int:record_id>")
    def result_detail(record_id: int):
        result = database_service.get_by_id(record_id)
        if result is None:
            return jsonify({"error": "not_found", "message": "未找到该评测记录。"}), 404
        return jsonify(_serialize_result(result))

    @app.get("/api/results/<int:record_id>/image/<kind>")
    def result_image(record_id: int, kind: str):
        result = database_service.get_by_id(record_id)
        if result is None:
            return jsonify({"error": "not_found", "message": "未找到该评测记录。"}), 404

        path = result.image_path if kind == "original" else result.processed_image_path
        if not path:
            return jsonify({"error": "not_found", "message": "当前记录没有对应图像。"}), 404

        file_path = Path(path)
        if not file_path.exists():
            return jsonify({"error": "not_found", "message": "图像文件不存在。"}), 404
        return send_file(file_path)

    @app.get("/api/camera/frame")
    def camera_frame():
        if not _ensure_camera():
            return jsonify({"error": "camera_unavailable", "message": state.camera_last_error or "摄像头不可用。"}), 503

        frame = camera_service.capture_frame()
        if frame is None:
            _mark_camera_error("未能获取实时取景。")
            return jsonify({"error": "capture_failed", "message": "未能获取实时取景。"}), 503

        _mark_camera_ready()
        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
        if not ok:
            return jsonify({"error": "encoding_failed", "message": "无法编码预览图像。"}), 500
        return send_file(io.BytesIO(encoded.tobytes()), mimetype="image/jpeg")

    @app.post("/api/evaluate/capture")
    def evaluate_capture():
        if not _ensure_camera():
            return jsonify({"error": "camera_unavailable", "message": state.camera_last_error or "摄像头不可用。"}), 503

        frame = camera_service.capture_high_res()
        if frame is None:
            frame = camera_service.capture_frame()
        if frame is None:
            _mark_camera_error("未能从摄像头捕获图像。")
            return jsonify({"error": "capture_failed", "message": "未能从摄像头捕获图像。"}), 503

        try:
            result = _evaluate_and_store(frame, source_name="camera_capture.jpg")
        except PreprocessingError as exc:
            return _preprocessing_error_response(exc)
        except Exception as exc:  # noqa: BLE001
            app.logger.exception("Capture evaluation failed: %s", exc)
            return jsonify({"error": "evaluation_failed", "message": str(exc)}), 500

        return jsonify({"result": _serialize_result(result)})

    @app.post("/api/evaluate/upload")
    def evaluate_upload():
        image = None
        source_name = "uploaded_image.jpg"

        uploaded = request.files.get("image")
        if uploaded and uploaded.filename:
            data = np.frombuffer(uploaded.read(), dtype=np.uint8)
            image = cv2.imdecode(data, cv2.IMREAD_COLOR)
            source_name = Path(uploaded.filename).name
        else:
            payload = request.get_json(silent=True) or {}
            image_data = payload.get("image_data")
            if image_data:
                image = _decode_data_url(image_data)
            source_name = payload.get("filename") or source_name

        if image is None:
            return jsonify({"error": "invalid_image", "message": "没有收到可解析的图像。"}), 400

        try:
            result = _evaluate_and_store(image, source_name=source_name)
        except PreprocessingError as exc:
            return _preprocessing_error_response(exc)
        except Exception as exc:  # noqa: BLE001
            app.logger.exception("Upload evaluation failed: %s", exc)
            return jsonify({"error": "evaluation_failed", "message": str(exc)}), 500

        return jsonify({"result": _serialize_result(result)})

    return app


def _serialize_stats(stats: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_count": int(stats.get("total_count", 0)),
        "average_score": round(float(stats.get("average_score", 0)), 1),
        "max_score": int(stats.get("max_score", 0)),
        "min_score": int(stats.get("min_score", 0)),
    }


def _serialize_result(result: EvaluationResult | None) -> dict[str, Any] | None:
    if result is None:
        return None

    return {
        "id": result.id,
        "total_score": int(result.total_score),
        "grade": LEVEL_LABELS.get(result.quality_level, "中"),
        "quality_level": result.quality_level,
        "quality_label": LEVEL_LABELS.get(result.quality_level, "中"),
        "color": result.get_color(),
        "feedback": result.feedback,
        "timestamp": result.timestamp.isoformat() if result.timestamp else None,
        "display_time": result.timestamp.strftime("%m-%d %H:%M") if result.timestamp else "--",
        "character_name": result.character_name or "未识别",
        "ocr_confidence": result.ocr_confidence,
        "quality_confidence": result.quality_confidence,
        "image_path": result.image_path,
        "processed_image_path": result.processed_image_path,
    }


def _decode_data_url(image_data: str) -> np.ndarray | None:
    if "," in image_data:
        _, image_data = image_data.split(",", 1)
    try:
        raw = base64.b64decode(image_data)
    except Exception:
        return None
    array = np.frombuffer(raw, dtype=np.uint8)
    return cv2.imdecode(array, cv2.IMREAD_COLOR)


def _ensure_camera() -> bool:
    with state.lock:
        if state.camera_online:
            return True

    if camera_service.open():
        _mark_camera_ready()
        return True

    _mark_camera_error("摄像头暂时不可用，请检查连接或先使用图片评测。")
    return False


def _mark_camera_ready() -> None:
    with state.lock:
        state.camera_online = True
        state.camera_last_error = None
        state.updated_at = time.time()


def _mark_camera_error(message: str) -> None:
    with state.lock:
        state.camera_online = False
        state.camera_last_error = message
        state.updated_at = time.time()


def _get_camera_status() -> dict[str, Any]:
    snapshot = state.snapshot()
    return {
        "online": bool(snapshot["camera_online"]),
        "message": snapshot["camera_last_error"] or ("摄像头已连接" if snapshot["camera_online"] else "等待连接摄像头"),
        "available": camera_service.available,
    }


def _evaluate_and_store(image: np.ndarray, source_name: str) -> EvaluationResult:
    timestamp = int(time.time() * 1000)
    original_path = IMAGES_DIR / f"webui_{timestamp}_{Path(source_name).stem}.jpg"
    cv2.imwrite(str(original_path), image)

    processed, processed_path = preprocessing_service.preprocess(image, save_processed=True)
    ocr_image = preprocessing_service.prepare_ocr_image(image)
    result = evaluation_service.evaluate(
        processed,
        original_image_path=str(original_path),
        processed_image_path=processed_path,
        ocr_image=ocr_image,
    )
    result.id = database_service.save(result)

    try:
        speech_service.speak_score(result.total_score, result.feedback)
    except Exception:
        logging.getLogger(__name__).debug("Skip speech output", exc_info=True)

    try:
        preprocessing_service.release_memory()
    except Exception:
        logging.getLogger(__name__).debug("Skip preprocessing cleanup", exc_info=True)

    with state.lock:
        state.last_result = result
        state.last_result_id = result.id
        state.updated_at = time.time()

    return result


def _preprocessing_error_response(exc: PreprocessingError):
    return (
        jsonify(
            {
                "error": exc.error_type,
                "message": str(exc),
                "guidance": GUIDANCE_BY_ERROR.get(exc.error_type, "请调整画面后重新拍摄。"),
            }
        ),
        422,
    )


app = create_app()


def main() -> None:
    """Run the local WebUI server."""

    host = APP_CONFIG.get("server", {}).get("host", "0.0.0.0")
    port = int(APP_CONFIG.get("server", {}).get("port", 5000))
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
