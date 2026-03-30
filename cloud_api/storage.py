"""SQLite storage for the InkPi cloud API."""

from __future__ import annotations

import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from werkzeug.security import check_password_hash, generate_password_hash


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CloudDatabase:
    """Persist users, sessions, and uploaded evaluation results."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _managed_connection(self):
        conn = self._connect()
        try:
            yield conn
        finally:
            conn.close()

    def _init_database(self) -> None:
        with self._managed_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_name TEXT NOT NULL,
                    local_record_id INTEGER NOT NULL,
                    total_score INTEGER NOT NULL,
                    feedback TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    character_name TEXT,
                    ocr_confidence REAL,
                    quality_level TEXT,
                    quality_confidence REAL,
                    image_path TEXT,
                    processed_image_path TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(device_name, local_record_id)
                )
                """
            )
            cursor.execute("PRAGMA table_info(results)")
            existing_columns = {row[1] for row in cursor.fetchall()}
            for column_name, column_type in (
                ("ocr_confidence", "REAL"),
                ("quality_level", "TEXT"),
                ("quality_confidence", "REAL"),
                ("image_path", "TEXT"),
                ("processed_image_path", "TEXT"),
            ):
                if column_name not in existing_columns:
                    cursor.execute(f"ALTER TABLE results ADD COLUMN {column_name} {column_type}")
            conn.commit()

    def ensure_default_user(self, username: str, password: str, display_name: str) -> None:
        with self._managed_connection() as conn:
            existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            if existing:
                return
            conn.execute(
                """
                INSERT INTO users (username, password_hash, display_name, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (username, generate_password_hash(password), display_name, utcnow_iso()),
            )
            conn.commit()

    def register_user(self, username: str, password: str, display_name: str | None = None) -> dict[str, Any]:
        display_name = display_name or username
        created_at = utcnow_iso()
        with self._managed_connection() as conn:
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO users (username, password_hash, display_name, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (username, generate_password_hash(password), display_name, created_at),
                )
                conn.commit()
            except sqlite3.IntegrityError as exc:
                raise ValueError("username_exists") from exc

        return {"id": int(cursor.lastrowid), "username": username, "display_name": display_name}

    def authenticate_user(self, username: str, password: str) -> dict[str, Any] | None:
        with self._managed_connection() as conn:
            user = conn.execute(
                "SELECT id, username, display_name, password_hash FROM users WHERE username = ?",
                (username,),
            ).fetchone()
            if not user or not check_password_hash(user["password_hash"], password):
                return None

            token = secrets.token_urlsafe(32)
            conn.execute(
                "INSERT INTO sessions (user_id, token, created_at) VALUES (?, ?, ?)",
                (user["id"], token, utcnow_iso()),
            )
            conn.commit()

        return {
            "token": token,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "display_name": user["display_name"],
            },
        }

    def get_user_by_token(self, token: str) -> dict[str, Any] | None:
        with self._managed_connection() as conn:
            row = conn.execute(
                """
                SELECT users.id, users.username, users.display_name
                FROM sessions
                JOIN users ON users.id = sessions.user_id
                WHERE sessions.token = ?
                """,
                (token,),
            ).fetchone()

        if not row:
            return None
        return {"id": row["id"], "username": row["username"], "display_name": row["display_name"]}

    def upsert_result(self, payload: dict[str, Any], device_name: str) -> dict[str, Any]:
        local_record_id = int(payload["local_record_id"])
        timestamp = payload.get("timestamp") or utcnow_iso()
        changed_at = utcnow_iso()

        with self._managed_connection() as conn:
            existing = conn.execute(
                "SELECT id FROM results WHERE device_name = ? AND local_record_id = ?",
                (device_name, local_record_id),
            ).fetchone()

            if existing:
                conn.execute(
                    """
                    UPDATE results
                    SET total_score = ?,
                        feedback = ?,
                        timestamp = ?,
                        character_name = ?,
                        ocr_confidence = ?,
                        quality_level = ?,
                        quality_confidence = ?,
                        image_path = ?,
                        processed_image_path = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        int(payload["total_score"]),
                        payload.get("feedback", ""),
                        timestamp,
                        payload.get("character_name"),
                        payload.get("ocr_confidence"),
                        payload.get("quality_level"),
                        payload.get("quality_confidence"),
                        payload.get("image_path"),
                        payload.get("processed_image_path"),
                        changed_at,
                        existing["id"],
                    ),
                )
                result_id = int(existing["id"])
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO results (
                        device_name,
                        local_record_id,
                        total_score,
                        feedback,
                        timestamp,
                        character_name,
                        ocr_confidence,
                        quality_level,
                        quality_confidence,
                        image_path,
                        processed_image_path,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        device_name,
                        local_record_id,
                        int(payload["total_score"]),
                        payload.get("feedback", ""),
                        timestamp,
                        payload.get("character_name"),
                        payload.get("ocr_confidence"),
                        payload.get("quality_level"),
                        payload.get("quality_confidence"),
                        payload.get("image_path"),
                        payload.get("processed_image_path"),
                        changed_at,
                        changed_at,
                    ),
                )
                result_id = int(cursor.lastrowid)

            conn.commit()

        return self.get_result(result_id)

    def list_results(self, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        limit = max(1, min(limit, 100))
        offset = max(0, offset)
        with self._managed_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM results").fetchone()[0]
            rows = conn.execute(
                """
                SELECT *
                FROM results
                ORDER BY timestamp DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()

        return {
            "total": int(total),
            "offset": offset,
            "limit": limit,
            "items": [self._result_row_to_dict(row) for row in rows],
        }

    def get_result(self, result_id: int) -> dict[str, Any] | None:
        with self._managed_connection() as conn:
            row = conn.execute("SELECT * FROM results WHERE id = ?", (result_id,)).fetchone()
        return self._result_row_to_dict(row) if row else None

    def _result_row_to_dict(self, row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            "id": row["id"],
            "device_name": row["device_name"],
            "local_record_id": row["local_record_id"],
            "total_score": row["total_score"],
            "feedback": row["feedback"],
            "timestamp": row["timestamp"],
            "character_name": row["character_name"],
            "ocr_confidence": row["ocr_confidence"],
            "quality_level": row["quality_level"],
            "quality_confidence": row["quality_confidence"],
            "image_path": row["image_path"],
            "processed_image_path": row["processed_image_path"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
