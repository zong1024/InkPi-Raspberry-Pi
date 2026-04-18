"""Flask cloud API for login and shared evaluation history."""

from __future__ import annotations

import os
from functools import wraps
import io
from pathlib import Path
from typing import Any, Callable

from flask import Flask, jsonify, request

try:
    from cloud_api.storage import CloudDatabase
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from storage import CloudDatabase

from models.evaluation_framework import (
    build_methodology_payload,
    build_practice_profile,
    build_scope_boundary,
    get_dimension_basis,
)


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    """Create the Flask application."""

    project_root = Path(__file__).resolve().parent.parent
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=str(project_root / "data" / "cloud_portal.db"),
        DEVICE_KEY=os.environ.get("INKPI_CLOUD_DEVICE_KEY", "inkpi-demo-device-key"),
        DEFAULT_USERNAME=os.environ.get("INKPI_CLOUD_DEMO_USER", "demo"),
        DEFAULT_PASSWORD=os.environ.get("INKPI_CLOUD_DEMO_PASSWORD", "demo123456"),
        DEFAULT_DISPLAY_NAME=os.environ.get("INKPI_CLOUD_DEMO_DISPLAY_NAME", "InkPi Demo"),
    )
    if test_config:
        app.config.update(test_config)

    db = CloudDatabase(Path(app.config["DATABASE"]))
    db.ensure_default_user(
        app.config["DEFAULT_USERNAME"],
        app.config["DEFAULT_PASSWORD"],
        app.config["DEFAULT_DISPLAY_NAME"],
    )
    app.extensions["cloud_db"] = db

    def json_error(message: str, status_code: int):
        return jsonify({"ok": False, "error": message}), status_code

    def device_key_valid() -> bool:
        device_key = request.headers.get("X-Device-Key", "").strip()
        return bool(device_key) and device_key == app.config["DEVICE_KEY"]

    def summary_filters_from_request() -> dict[str, str]:
        return {
            "keyword": str(request.args.get("keyword", "")).strip(),
            "quality_level": str(request.args.get("quality_level", "all")).strip() or "all",
            "device_name": str(request.args.get("device_name", "all")).strip() or "all",
            "date_range": str(request.args.get("date_range", "all")).strip() or "all",
        }

    def auth_required(fn: Callable):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            if not token:
                token = request.headers.get("X-Auth-Token", "").strip()
            if not token:
                return json_error("missing_token", 401)

            user = db.get_user_by_token(token)
            if not user:
                return json_error("invalid_token", 401)

            request.current_user = user
            return fn(*args, **kwargs)

        return wrapper

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True, "status": "ok"})

    @app.post("/api/auth/register")
    def register():
        payload = request.get_json(silent=True) or {}
        username = str(payload.get("username", "")).strip()
        password = str(payload.get("password", "")).strip()
        display_name = str(payload.get("display_name", "")).strip() or username

        if len(username) < 3 or len(password) < 6:
            return json_error("invalid_credentials", 400)

        try:
            user = db.register_user(username, password, display_name)
        except ValueError:
            return json_error("username_exists", 409)

        return jsonify({"ok": True, "user": user})

    @app.post("/api/auth/login")
    def login():
        payload = request.get_json(silent=True) or {}
        username = str(payload.get("username", "")).strip()
        password = str(payload.get("password", "")).strip()

        auth = db.authenticate_user(username, password)
        if not auth:
            return json_error("invalid_credentials", 401)

        return jsonify({"ok": True, **auth})

    @app.get("/api/auth/me")
    @auth_required
    def me():
        return jsonify({"ok": True, "user": request.current_user})

    @app.get("/api/results")
    @auth_required
    def list_results():
        limit = int(request.args.get("limit", 30))
        offset = int(request.args.get("offset", 0))
        keyword = str(request.args.get("keyword", "")).strip()
        quality_level = str(request.args.get("quality_level", "all")).strip() or "all"
        device_name = str(request.args.get("device_name", "all")).strip() or "all"
        date_range = str(request.args.get("date_range", "all")).strip() or "all"
        sort = str(request.args.get("sort", "latest")).strip() or "latest"
        return jsonify(
            {
                "ok": True,
                **db.list_results(
                    limit=limit,
                    offset=offset,
                    keyword=keyword,
                    quality_level=quality_level,
                    device_name=device_name,
                    date_range=date_range,
                    sort=sort,
                ),
            }
        )

    @app.get("/api/results/summary")
    @auth_required
    def results_summary():
        filters = summary_filters_from_request()
        return jsonify(
            {
                "ok": True,
                "summary": db.get_summary(**filters),
            }
        )

    @app.get("/api/system/methodology")
    @auth_required
    def methodology():
        summary = db.get_summary(**summary_filters_from_request())
        return jsonify(
            {
                "ok": True,
                **build_methodology_payload(summary),
            }
        )

    @app.get("/api/validation/overview")
    @auth_required
    def validation_overview():
        summary = db.get_summary(**summary_filters_from_request())
        methodology_payload = build_methodology_payload(summary)
        return jsonify(
            {
                "ok": True,
                "overview": {
                    "reviewed_result_count": summary.get("reviewed_result_count"),
                    "review_record_count": summary.get("review_record_count"),
                    "pending_review_count": summary.get("pending_review_count"),
                    "review_coverage_rate": summary.get("review_coverage_rate"),
                    "agreement_rate": summary.get("agreement_rate"),
                    "average_manual_score": summary.get("average_manual_score"),
                    "average_score_gap": summary.get("average_score_gap"),
                    "dimension_gap_averages": summary.get("dimension_gap_averages"),
                },
                "validation_snapshot": methodology_payload["validation_snapshot"],
                "validation_plan": methodology_payload["validation_plan"],
            }
        )

    @app.get("/api/results/<int:result_id>")
    @auth_required
    def result_detail(result_id: int):
        result = db.get_result(result_id)
        if not result:
            return json_error("result_not_found", 404)
        result["dimension_basis"] = get_dimension_basis(result.get("dimension_scores"))
        result["practice_profile"] = build_practice_profile(
            result.get("dimension_scores"),
            total_score=int(result.get("total_score") or 0),
            quality_level=str(result.get("quality_level") or "medium"),
            character_name=result.get("character_name"),
        )
        result["scope_boundary"] = build_scope_boundary()
        result["expert_review_summary"] = db.get_result_review_summary(result_id)
        result["expert_reviews"] = db.list_expert_reviews(result_id)
        return jsonify({"ok": True, "result": result})

    @app.get("/api/results/<int:result_id>/reviews")
    @auth_required
    def result_reviews(result_id: int):
        result = db.get_result(result_id)
        if not result:
            return json_error("result_not_found", 404)
        return jsonify(
            {
                "ok": True,
                "items": db.list_expert_reviews(result_id),
                "summary": db.get_result_review_summary(result_id),
            }
        )

    @app.post("/api/results/<int:result_id>/reviews")
    @auth_required
    def add_result_review(result_id: int):
        payload = request.get_json(silent=True) or {}
        try:
            review = db.add_expert_review(result_id, payload)
        except ValueError as exc:
            error_code = str(exc)
            if error_code == "result_not_found":
                return json_error(error_code, 404)
            return json_error(error_code, 400)
        return jsonify({"ok": True, "review": review, "summary": db.get_result_review_summary(result_id)})

    @app.delete("/api/results/<int:result_id>")
    @auth_required
    def delete_result(result_id: int):
        deleted = db.delete_result(result_id)
        if not deleted:
            return json_error("result_not_found", 404)
        return jsonify({"ok": True, "deleted_id": result_id})

    @app.post("/api/results/batch-delete")
    @auth_required
    def batch_delete_results():
        payload = request.get_json(silent=True) or {}
        ids = payload.get("ids") or []
        if not isinstance(ids, list):
            return json_error("invalid_payload", 400)

        deleted_count = db.delete_results(ids)
        return jsonify({"ok": True, "deleted_count": deleted_count})

    @app.post("/api/device/results")
    def upload_result():
        if not device_key_valid():
            return json_error("invalid_device_key", 401)

        payload = request.get_json(silent=True) or {}
        if "local_record_id" not in payload or "total_score" not in payload:
            return json_error("invalid_payload", 400)

        device_name = (
            request.headers.get("X-Device-Name", "").strip()
            or str(payload.get("device_name", "")).strip()
            or "InkPi-Raspberry-Pi"
        )
        result = db.upsert_result(payload, device_name=device_name)
        return jsonify({"ok": True, "result": result})

    @app.post("/api/device/ocr")
    def device_ocr():
        try:
            import cv2
            import numpy as np
        except Exception as exc:  # noqa: BLE001
            return json_error(f"ocr_runtime_unavailable:{exc}", 503)

        if not device_key_valid():
            return json_error("invalid_device_key", 401)

        image_file = request.files.get("image")
        if image_file is None:
            return json_error("missing_image", 400)

        raw = image_file.read()
        if not raw:
            return json_error("empty_image", 400)

        image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            return json_error("invalid_image", 400)

        ocr_service = app.extensions.get("ocr_service")
        if ocr_service is None:
            try:
                from services.local_ocr_service import LocalOcrService

                # Keep the cloud OCR endpoint local-only so it cannot recurse
                # into the same /api/device/ocr endpoint via remote fallback.
                ocr_service = LocalOcrService(allow_remote_fallback=False)
                app.extensions["ocr_service"] = ocr_service
            except Exception as exc:  # noqa: BLE001
                return json_error(f"ocr_service_unavailable:{exc}", 503)

        if not getattr(ocr_service, "available", False):
            return json_error("ocr_service_unavailable", 503)

        recognition = ocr_service.recognize(image)
        if recognition is None:
            return json_error("ocr_failed", 422)

        return jsonify(
            {
                "ok": True,
                "item": {
                    "character": recognition.character,
                    "confidence": recognition.confidence,
                    "source": getattr(recognition, "source", "paddleocr"),
                    "bbox": list(recognition.bbox) if recognition.bbox is not None else None,
                },
            }
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("INKPI_CLOUD_PORT", "5001")), debug=False)
