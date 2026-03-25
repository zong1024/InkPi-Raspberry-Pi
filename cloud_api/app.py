"""Flask cloud API for login and shared evaluation history."""

from __future__ import annotations

import os
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from flask import Flask, jsonify, request

try:
    from cloud_api.storage import CloudDatabase
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from storage import CloudDatabase


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
        return jsonify({"ok": True, **db.list_results(limit=limit, offset=offset)})

    @app.get("/api/results/<int:result_id>")
    @auth_required
    def result_detail(result_id: int):
        result = db.get_result(result_id)
        if not result:
            return json_error("result_not_found", 404)
        return jsonify({"ok": True, "result": result})

    @app.post("/api/device/results")
    def upload_result():
        device_key = request.headers.get("X-Device-Key", "").strip()
        if not device_key or device_key != app.config["DEVICE_KEY"]:
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

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("INKPI_CLOUD_PORT", "5001")), debug=False)
