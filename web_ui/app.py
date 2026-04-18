"""Local WebUI server for InkPi."""

from __future__ import annotations

import base64
from collections.abc import Iterator
import io
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
from flask import Flask, Response, jsonify, request, send_file, send_from_directory, stream_with_context
import numpy as np

from config import APP_CONFIG, IMAGES_DIR, IS_RASPBERRY_PI, LOG_CONFIG
from models.evaluation_framework import get_script_label, normalize_script
from models.evaluation_result import EvaluationResult
from services.camera_service import camera_service
from services.database_service import database_service
from services.evaluation_service import evaluation_service
from services.operations_monitor_service import operations_monitor_service
from services.preprocessing_service import PreprocessingError, preprocessing_service
from services.speech_service import speech_service


GUIDANCE_BY_ERROR = {
    "too_dark": "画面偏暗，请增加光照后重试。",
    "too_bright": "画面反光过强，请避开直射光。",
    "low_contrast": "字和背景对比度不足，请重新对准作品。",
    "empty_shot": "没有检测到单字主体，请让作品更靠近取景框中央。",
    "obstruction": "请移开手部或杂物遮挡，只保留作品主体。",
    "not_calligraphy": "当前画面不像单字书法作品，请重新对准后再试。",
    "too_fragmented": "画面内容过于零散，请只保留一个字。",
    "scattered_content": "主体太分散，请让目标单字更集中。",
    "ocr_failed": "系统没能稳定识别这个字，请让主体更完整、更居中后重试。",
}

LEVEL_LABELS = {
    "good": "甲",
    "medium": "乙",
    "bad": "丙",
}


@dataclass
class WebUiState:
    """Shared in-process WebUI state."""

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
    operations_monitor_service.attach_logging()

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

    @app.get("/api/ops/bootstrap")
    def ops_bootstrap():
        return jsonify(
            {
                "snapshot": operations_monitor_service.build_snapshot(),
                "logs": operations_monitor_service.get_logs(limit=120),
                "pipeline": operations_monitor_service.get_pipeline_events(limit=40),
                "runtime_logs": operations_monitor_service.get_runtime_log_tails(max_lines=24),
            }
        )

    @app.get("/api/ops/status")
    def ops_status():
        return jsonify({"snapshot": operations_monitor_service.build_snapshot()})

    @app.get("/api/ops/logs")
    def ops_logs():
        since_id = max(int(request.args.get("since", 0)), 0)
        limit = min(max(int(request.args.get("limit", 100)), 1), 300)
        return jsonify(
            {
                "items": operations_monitor_service.get_logs(since_id=since_id, limit=limit),
                "runtime_logs": operations_monitor_service.get_runtime_log_tails(max_lines=24),
            }
        )

    @app.get("/api/ops/pipeline")
    def ops_pipeline():
        since_id = max(int(request.args.get("since", 0)), 0)
        limit = min(max(int(request.args.get("limit", 60)), 1), 200)
        return jsonify({"items": operations_monitor_service.get_pipeline_events(since_id=since_id, limit=limit)})

    @app.get("/api/ops/stream")
    def ops_stream():
        def generate() -> Iterator[str]:
            log_cursor = 0
            pipeline_cursor = 0
            while True:
                logs = operations_monitor_service.get_logs(since_id=log_cursor, limit=100)
                pipeline = operations_monitor_service.get_pipeline_events(since_id=pipeline_cursor, limit=40)
                if logs:
                    log_cursor = int(logs[-1]["id"])
                if pipeline:
                    pipeline_cursor = int(pipeline[-1]["id"])

                payload = {
                    "snapshot": operations_monitor_service.build_snapshot(),
                    "logs": logs,
                    "pipeline": pipeline,
                    "runtime_logs": operations_monitor_service.get_runtime_log_tails(max_lines=24),
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                time.sleep(2)

        return Response(stream_with_context(generate()), mimetype="text/event-stream")

    @app.get("/api/history")
    def history():
        limit = min(max(int(request.args.get("limit", 40)), 1), 200)
        script = str(request.args.get("script", "")).strip() or None
        records = database_service.get_all(limit=limit, script=script)
        return jsonify({"items": [_serialize_result(item) for item in records]})

    @app.get("/api/results/<int:record_id>")
    def result_detail(record_id: int):
        result = database_service.get_by_id(record_id)
        if result is None:
            return jsonify({"error": "not_found", "message": "未找到该评测记录。"}), 404
        return jsonify(_serialize_result(result, include_debug=True))

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
            message = state.camera_last_error or "摄像头不可用。"
            operations_monitor_service.record_pipeline("camera", "error", message)
            return jsonify({"error": "camera_unavailable", "message": message}), 503

        frame = camera_service.capture_frame()
        if frame is None:
            _mark_camera_error("未能获取实时取景。")
            operations_monitor_service.record_pipeline("camera", "error", "Failed to capture preview frame.")
            return jsonify({"error": "capture_failed", "message": "未能获取实时取景。"}), 503

        _mark_camera_ready()
        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
        if not ok:
            return jsonify({"error": "encoding_failed", "message": "无法编码预览图像。"}), 500
        return send_file(io.BytesIO(encoded.tobytes()), mimetype="image/jpeg")

    @app.post("/api/evaluate/capture")
    def evaluate_capture():
        payload = request.get_json(silent=True) or {}
        script, script_error = _parse_script_from_request(payload)
        if script_error:
            return jsonify({"error": "invalid_script", "message": script_error}), 400
        if not _ensure_camera():
            message = state.camera_last_error or "摄像头不可用。"
            return jsonify({"error": "camera_unavailable", "message": message}), 503

        frame = camera_service.capture_high_res()
        if frame is None:
            frame = camera_service.capture_frame()
        if frame is None:
            _mark_camera_error("未能从摄像头获取图像。")
            operations_monitor_service.record_pipeline("camera", "error", "Failed to capture evaluation frame.")
            return jsonify({"error": "capture_failed", "message": "未能从摄像头获取图像。"}), 503

        try:
            result = _evaluate_and_store(frame, source_name="camera_capture.jpg", script=script or "regular")
        except PreprocessingError as exc:
            return _preprocessing_error_response(exc)
        except ValueError as exc:
            return jsonify({"error": "invalid_script", "message": str(exc)}), 400
        except Exception as exc:  # noqa: BLE001
            app.logger.exception("Capture evaluation failed: %s", exc)
            operations_monitor_service.record_pipeline("evaluation", "error", str(exc))
            return jsonify({"error": "evaluation_failed", "message": str(exc)}), 500

        return jsonify({"result": _serialize_result(result)})

    @app.post("/api/evaluate/upload")
    def evaluate_upload():
        image = None
        source_name = "uploaded_image.jpg"
        payload = request.get_json(silent=True) or {}
        script, script_error = _parse_script_from_request(payload)
        if request.files:
            script, script_error = _parse_script_from_request({})
        if script_error:
            return jsonify({"error": "invalid_script", "message": script_error}), 400

        uploaded = request.files.get("image")
        if uploaded and uploaded.filename:
            data = np.frombuffer(uploaded.read(), dtype=np.uint8)
            image = cv2.imdecode(data, cv2.IMREAD_COLOR)
            source_name = Path(uploaded.filename).name
        else:
            image_data = payload.get("image_data")
            if image_data:
                image = _decode_data_url(image_data)
            source_name = payload.get("filename") or source_name

        if image is None:
            return jsonify({"error": "invalid_image", "message": "没有收到可解析的图像。"}), 400

        try:
            result = _evaluate_and_store(image, source_name=source_name, script=script or "regular")
        except PreprocessingError as exc:
            return _preprocessing_error_response(exc)
        except ValueError as exc:
            return jsonify({"error": "invalid_script", "message": str(exc)}), 400
        except Exception as exc:  # noqa: BLE001
            app.logger.exception("Upload evaluation failed: %s", exc)
            operations_monitor_service.record_pipeline("evaluation", "error", str(exc))
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


def _serialize_result(result: EvaluationResult | None, include_debug: bool = False) -> dict[str, Any] | None:
    if result is None:
        return None

    payload = {
        "id": result.id,
        "total_score": int(result.total_score),
        "grade": LEVEL_LABELS.get(result.quality_level, "乙"),
        "quality_level": result.quality_level,
        "quality_label": LEVEL_LABELS.get(result.quality_level, "乙"),
        "color": result.get_color(),
        "feedback": result.feedback,
        "timestamp": result.timestamp.isoformat() if result.timestamp else None,
        "display_time": result.timestamp.strftime("%m-%d %H:%M") if result.timestamp else "--",
        "script": result.get_script(),
        "script_label": result.get_script_label(),
        "character_name": result.character_name or "未识别",
        "ocr_confidence": result.ocr_confidence,
        "quality_confidence": result.quality_confidence,
        "image_path": result.image_path,
        "processed_image_path": result.processed_image_path,
        "dimension_scores": result.get_dimension_scores(),
        "dimension_summary": result.get_dimension_summary(),
    }
    if include_debug:
        payload["score_debug"] = result.score_debug
    return payload


def _decode_data_url(image_data: str) -> np.ndarray | None:
    if "," in image_data:
        _, image_data = image_data.split(",", 1)
    try:
        raw = base64.b64decode(image_data)
    except Exception:
        return None
    array = np.frombuffer(raw, dtype=np.uint8)
    return cv2.imdecode(array, cv2.IMREAD_COLOR)


def _parse_script_from_request(payload: dict[str, Any] | None = None) -> tuple[str | None, str | None]:
    if payload is None:
        payload = {}

    raw_script = None
    if request.form:
        raw_script = request.form.get("script")
    if not raw_script:
        raw_script = payload.get("script")
    if raw_script is None:
        return None, "必须显式选择书体（楷书或行书）。"

    script = normalize_script(raw_script)
    if script not in {"regular", "running"}:
        return None, "当前仅支持楷书与行书单字评测。"
    return script, None


def _ensure_camera() -> bool:
    with state.lock:
        if state.camera_online:
            return True

    if camera_service.open():
        _mark_camera_ready()
        operations_monitor_service.record_pipeline("camera", "done", "Camera connection established.")
        return True

    _mark_camera_error("摄像头暂时不可用，请检查连接或使用图片上传。")
    operations_monitor_service.record_pipeline("camera", "error", "Camera could not be opened.")
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
        "message": snapshot["camera_last_error"] or ("摄像头已连接" if snapshot["camera_online"] else "等待摄像头接入"),
        "available": camera_service.available,
    }


def _evaluate_and_store(image: np.ndarray, source_name: str, script: str) -> EvaluationResult:
    operations_monitor_service.record_pipeline(
        "ingest",
        "running",
        "Image accepted by the local runtime.",
        {"source_name": source_name, "script": script, "script_label": get_script_label(script)},
    )
    timestamp = int(time.time() * 1000)
    original_path = IMAGES_DIR / f"webui_{timestamp}_{Path(source_name).stem}.jpg"
    cv2.imwrite(str(original_path), image)
    operations_monitor_service.record_pipeline(
        "ingest",
        "done",
        "Source image saved.",
        {"image_path": str(original_path)},
    )

    operations_monitor_service.record_pipeline("preprocess", "running", "Preparing image for evaluation.")
    processed, processed_path = preprocessing_service.preprocess(image, save_processed=True)
    ocr_image = preprocessing_service.prepare_ocr_image(image)
    operations_monitor_service.record_pipeline(
        "preprocess",
        "done",
        "Preprocessing completed.",
        {"processed_image_path": processed_path},
    )

    result = evaluation_service.evaluate(
        processed,
        script=script,
        original_image_path=str(original_path),
        processed_image_path=processed_path,
        ocr_image=ocr_image,
    )

    operations_monitor_service.record_pipeline("storage", "running", "Persisting evaluation result.")
    result.id = database_service.save(result)
    operations_monitor_service.record_pipeline(
        "storage",
        "done",
        "Evaluation result stored locally.",
        {"record_id": result.id, "total_score": result.total_score},
    )
    operations_monitor_service.record_result(_serialize_result(result, include_debug=True) or {})

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
    operations_monitor_service.record_pipeline(
        "precheck",
        "error",
        str(exc),
        {"error_type": exc.error_type},
    )
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
