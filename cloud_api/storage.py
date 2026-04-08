"""SQLite storage for the InkPi cloud API."""

from __future__ import annotations

from collections import defaultdict
import json
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from werkzeug.security import check_password_hash, generate_password_hash


DIMENSION_KEYS = ("structure", "stroke", "integrity", "stability")
PASSWORD_HASH_METHOD = "pbkdf2:sha256:600000"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_password_hash(password: str) -> str:
    """Use a lower-memory password hash that survives constrained hosts."""

    return generate_password_hash(password, method=PASSWORD_HASH_METHOD)


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
                    dimension_scores_json TEXT,
                    score_debug_json TEXT,
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
                ("dimension_scores_json", "TEXT"),
                ("score_debug_json", "TEXT"),
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
                (username, build_password_hash(password), display_name, utcnow_iso()),
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
                    (username, build_password_hash(password), display_name, created_at),
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
        dimension_scores_json = self._coerce_json_text(
            payload.get("dimension_scores_json"),
            payload.get("dimension_scores"),
        )
        score_debug_json = self._coerce_json_text(
            payload.get("score_debug_json"),
            payload.get("score_debug"),
        )

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
                        dimension_scores_json = ?,
                        score_debug_json = ?,
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
                        dimension_scores_json,
                        score_debug_json,
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
                        dimension_scores_json,
                        score_debug_json,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        dimension_scores_json,
                        score_debug_json,
                        changed_at,
                        changed_at,
                    ),
                )
                result_id = int(cursor.lastrowid)

            conn.commit()

        return self.get_result(result_id)

    def list_results(
        self,
        limit: int = 50,
        offset: int = 0,
        keyword: str = "",
        quality_level: str = "all",
        device_name: str = "all",
        date_range: str = "all",
        sort: str = "latest",
    ) -> dict[str, Any]:
        limit = max(1, min(limit, 100))
        offset = max(0, offset)
        where_sql, params = self._build_filter_clause(
            keyword=keyword,
            quality_level=quality_level,
            device_name=device_name,
            date_range=date_range,
        )
        order_sql = self._build_sort_clause(sort)

        with self._managed_connection() as conn:
            total = conn.execute(
                f"SELECT COUNT(*) FROM results {where_sql}",
                params,
            ).fetchone()[0]
            rows = conn.execute(
                """
                SELECT *
                FROM results
                {where_sql}
                ORDER BY {order_sql}
                LIMIT ? OFFSET ?
                """.format(where_sql=where_sql, order_sql=order_sql),
                (*params, limit, offset),
            ).fetchall()

        return {
            "total": int(total),
            "offset": offset,
            "limit": limit,
            "items": [self._result_row_to_dict(row) for row in rows],
        }

    def get_summary(
        self,
        keyword: str = "",
        quality_level: str = "all",
        device_name: str = "all",
        date_range: str = "all",
    ) -> dict[str, Any]:
        where_sql, params = self._build_filter_clause(
            keyword=keyword,
            quality_level=quality_level,
            device_name=device_name,
            date_range=date_range,
        )
        now = datetime.now()
        recent_cutoff = now - timedelta(days=7)
        previous_cutoff = now - timedelta(days=14)
        trend_window_days = 10

        with self._managed_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    id,
                    timestamp,
                    total_score,
                    quality_level,
                    character_name,
                    device_name,
                    dimension_scores_json
                FROM results
                {where_sql}
                ORDER BY timestamp DESC, id DESC
                """,
                params,
            ).fetchall()
            device_rows = conn.execute(
                """
                SELECT device_name
                FROM results
                GROUP BY device_name
                ORDER BY MAX(timestamp) DESC, device_name ASC
                """
            ).fetchall()

        available_devices = [row["device_name"] for row in device_rows]
        empty_trend_points = self._build_empty_trend_points(now=now, days=trend_window_days)
        quality_counts = {"good": 0, "medium": 0, "bad": 0}

        if not rows:
            return {
                "total": 0,
                "average_score": None,
                "best_score": None,
                "worst_score": None,
                "latest_score": None,
                "latest_character": None,
                "latest_timestamp": None,
                "device_count": 0,
                "unique_characters": 0,
                "quality_counts": quality_counts,
                "recent_average": None,
                "recent_total": 0,
                "previous_average": None,
                "previous_total": 0,
                "progress_delta": None,
                "progress_trend": "flat",
                "score_distribution": {"90_plus": 0, "80_89": 0, "70_79": 0, "below_70": 0},
                "qualified_rate": None,
                "excellent_rate": None,
                "dimension_averages": {},
                "top_characters": [],
                "top_devices": [],
                "available_devices": available_devices,
                "trend_points": empty_trend_points,
                "insight": self._build_summary_insight(
                    total=0,
                    average_score=None,
                    recent_average=None,
                    progress_delta=None,
                    quality_counts=quality_counts,
                    top_character=None,
                    top_device=None,
                ),
            }

        latest_row = rows[0]
        score_distribution = {"90_plus": 0, "80_89": 0, "70_79": 0, "below_70": 0}
        scores: list[int] = []
        recent_scores: list[int] = []
        previous_scores: list[int] = []
        character_stats: dict[str, dict[str, float]] = defaultdict(lambda: {"count": 0, "score_total": 0.0})
        device_stats: dict[str, dict[str, float]] = defaultdict(lambda: {"count": 0, "score_total": 0.0})
        dimension_totals: dict[str, float] = defaultdict(float)
        dimension_counts: dict[str, int] = defaultdict(int)
        trend_buckets = {
            point["date"]: {"count": 0, "score_total": 0.0}
            for point in empty_trend_points
        }

        for row in rows:
            score = int(row["total_score"] or 0)
            scores.append(score)

            quality = row["quality_level"] or "medium"
            if quality in quality_counts:
                quality_counts[quality] += 1

            if score >= 90:
                score_distribution["90_plus"] += 1
            elif score >= 80:
                score_distribution["80_89"] += 1
            elif score >= 70:
                score_distribution["70_79"] += 1
            else:
                score_distribution["below_70"] += 1

            character_name = row["character_name"] or "未识别"
            character_stats[character_name]["count"] += 1
            character_stats[character_name]["score_total"] += score

            current_device_name = row["device_name"] or "InkPi-Raspberry-Pi"
            device_stats[current_device_name]["count"] += 1
            device_stats[current_device_name]["score_total"] += score

            timestamp = self._parse_timestamp(row["timestamp"])
            if timestamp is not None:
                if timestamp >= recent_cutoff:
                    recent_scores.append(score)
                elif timestamp >= previous_cutoff:
                    previous_scores.append(score)

                trend_key = timestamp.date().isoformat()
                if trend_key in trend_buckets:
                    trend_buckets[trend_key]["count"] += 1
                    trend_buckets[trend_key]["score_total"] += score

            for key, value in (self._load_json_blob(row["dimension_scores_json"]) or {}).items():
                if key not in DIMENSION_KEYS or value is None:
                    continue
                dimension_totals[key] += float(value)
                dimension_counts[key] += 1

        total = len(rows)
        average_score = round(sum(scores) / total, 1)
        recent_average = round(sum(recent_scores) / len(recent_scores), 1) if recent_scores else None
        previous_average = round(sum(previous_scores) / len(previous_scores), 1) if previous_scores else None
        progress_delta = (
            round(recent_average - previous_average, 1)
            if recent_average is not None and previous_average is not None
            else None
        )
        progress_trend = "flat"
        if progress_delta is not None:
            if progress_delta >= 2:
                progress_trend = "up"
            elif progress_delta <= -2:
                progress_trend = "down"

        top_characters = [
            {
                "character_name": character_name,
                "count": int(stats["count"]),
                "average_score": round(stats["score_total"] / stats["count"], 1),
            }
            for character_name, stats in sorted(
                character_stats.items(),
                key=lambda item: (-int(item[1]["count"]), -(item[1]["score_total"] / item[1]["count"]), item[0]),
            )[:8]
        ]
        top_devices = [
            {
                "device_name": current_device_name,
                "count": int(stats["count"]),
                "average_score": round(stats["score_total"] / stats["count"], 1),
            }
            for current_device_name, stats in sorted(
                device_stats.items(),
                key=lambda item: (-int(item[1]["count"]), -(item[1]["score_total"] / item[1]["count"]), item[0]),
            )[:3]
        ]
        dimension_averages = {
            key: round(dimension_totals[key] / dimension_counts[key], 1)
            for key in DIMENSION_KEYS
            if dimension_counts[key]
        }
        trend_points = []
        for point in empty_trend_points:
            bucket = trend_buckets[point["date"]]
            count = int(bucket["count"])
            trend_points.append(
                {
                    "date": point["date"],
                    "label": point["label"],
                    "count": count,
                    "average_score": round(bucket["score_total"] / count, 1) if count else None,
                }
            )

        top_character = top_characters[0]["character_name"] if top_characters else None
        top_device = top_devices[0]["device_name"] if top_devices else None

        return {
            "total": total,
            "average_score": average_score,
            "best_score": max(scores),
            "worst_score": min(scores),
            "latest_score": int(latest_row["total_score"]),
            "latest_character": latest_row["character_name"],
            "latest_timestamp": latest_row["timestamp"],
            "device_count": len({(row["device_name"] or "InkPi-Raspberry-Pi") for row in rows}),
            "unique_characters": len({(row["character_name"] or "未识别") for row in rows}),
            "quality_counts": quality_counts,
            "recent_average": recent_average,
            "recent_total": len(recent_scores),
            "previous_average": previous_average,
            "previous_total": len(previous_scores),
            "progress_delta": progress_delta,
            "progress_trend": progress_trend,
            "score_distribution": score_distribution,
            "qualified_rate": round(((quality_counts["good"] + quality_counts["medium"]) / total) * 100, 1),
            "excellent_rate": round((quality_counts["good"] / total) * 100, 1),
            "dimension_averages": dimension_averages,
            "top_characters": top_characters,
            "top_devices": top_devices,
            "available_devices": available_devices,
            "trend_points": trend_points,
            "insight": self._build_summary_insight(
                total=total,
                average_score=average_score,
                recent_average=recent_average,
                progress_delta=progress_delta,
                quality_counts=quality_counts,
                top_character=top_character,
                top_device=top_device,
            ),
        }

    def get_result(self, result_id: int) -> dict[str, Any] | None:
        with self._managed_connection() as conn:
            row = conn.execute("SELECT * FROM results WHERE id = ?", (result_id,)).fetchone()
        return self._result_row_to_dict(row, include_debug=True) if row else None

    def delete_result(self, result_id: int) -> bool:
        with self._managed_connection() as conn:
            cursor = conn.execute("DELETE FROM results WHERE id = ?", (result_id,))
            conn.commit()
        return cursor.rowcount > 0

    def delete_results(self, result_ids: list[int]) -> int:
        valid_ids = [int(result_id) for result_id in result_ids if str(result_id).strip()]
        if not valid_ids:
            return 0

        placeholders = ",".join("?" for _ in valid_ids)
        with self._managed_connection() as conn:
            cursor = conn.execute(
                f"DELETE FROM results WHERE id IN ({placeholders})",
                valid_ids,
            )
            conn.commit()
        return int(cursor.rowcount or 0)

    def _build_filter_clause(
        self,
        keyword: str = "",
        quality_level: str = "all",
        device_name: str = "all",
        date_range: str = "all",
    ) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []

        keyword = keyword.strip()
        if keyword:
            like_value = f"%{keyword}%"
            clauses.append(
                "("
                "COALESCE(character_name, '') LIKE ? OR "
                "COALESCE(feedback, '') LIKE ? OR "
                "COALESCE(device_name, '') LIKE ?"
                ")"
            )
            params.extend([like_value, like_value, like_value])

        if quality_level and quality_level != "all":
            clauses.append("quality_level = ?")
            params.append(quality_level)

        if device_name and device_name != "all":
            clauses.append("device_name = ?")
            params.append(device_name)

        if date_range in {"1d", "7d", "30d"}:
            days = {"1d": 1, "7d": 7, "30d": 30}[date_range]
            clauses.append("timestamp >= ?")
            params.append((datetime.now() - timedelta(days=days)).isoformat())

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return where_sql, params

    def _build_sort_clause(self, sort: str) -> str:
        sort_map = {
            "latest": "timestamp DESC, id DESC",
            "highest": "total_score DESC, timestamp DESC, id DESC",
            "lowest": "total_score ASC, timestamp DESC, id DESC",
        }
        return sort_map.get(sort, sort_map["latest"])

    def _build_summary_insight(
        self,
        total: int,
        average_score: float | None,
        recent_average: float | None,
        progress_delta: float | None,
        quality_counts: dict[str, int],
        top_character: str | None,
        top_device: str | None,
    ) -> str:
        if total == 0:
            return "还没有云端历史记录，完成一次评测后这里会自动生成总结。"

        insight_parts = []
        if average_score is not None:
            insight_parts.append(f"当前平均分 {average_score:.1f}")
        if recent_average is not None:
            insight_parts.append(f"近 7 天均分 {recent_average:.1f}")
        if progress_delta is not None:
            if progress_delta >= 2:
                insight_parts.append(f"最近一周较前一周提升 {progress_delta:.1f} 分")
            elif progress_delta <= -2:
                insight_parts.append(f"最近一周较前一周回落 {abs(progress_delta):.1f} 分")
        if top_character:
            insight_parts.append(f"出现最多的字是“{top_character}”")
        if top_device:
            insight_parts.append(f"主要数据来自 {top_device}")

        dominant_level = max(quality_counts.items(), key=lambda item: item[1])[0] if any(quality_counts.values()) else None
        if dominant_level == "good":
            insight_parts.append("整体状态偏稳定")
        elif dominant_level == "medium":
            insight_parts.append("目前成绩集中在中段")
        elif dominant_level == "bad":
            insight_parts.append("近期低分样本偏多，建议重点回看")

        return "，".join(insight_parts) + "。"

    def _build_empty_trend_points(self, now: datetime, days: int) -> list[dict[str, str]]:
        start_date = now.date() - timedelta(days=days - 1)
        return [
            {
                "date": (start_date + timedelta(days=offset)).isoformat(),
                "label": (start_date + timedelta(days=offset)).strftime("%m-%d"),
            }
            for offset in range(days)
        ]

    def _parse_timestamp(self, raw_value: str | None) -> datetime | None:
        if not raw_value:
            return None
        try:
            parsed = datetime.fromisoformat(raw_value)
        except ValueError:
            return None
        if parsed.tzinfo is not None:
            return parsed.astimezone().replace(tzinfo=None)
        return parsed

    def _result_row_to_dict(self, row: sqlite3.Row | None, include_debug: bool = False) -> dict[str, Any] | None:
        if row is None:
            return None
        payload = {
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
            "dimension_scores": self._load_json_blob(row["dimension_scores_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        if include_debug:
            payload["score_debug"] = self._load_json_blob(row["score_debug_json"])
        return payload

    def _coerce_json_text(self, raw_text: Any, raw_value: Any) -> str | None:
        if isinstance(raw_text, str) and raw_text.strip():
            return raw_text
        if raw_value is None:
            return None
        return json.dumps(raw_value, ensure_ascii=False)

    def _load_json_blob(self, raw_text: str | None) -> dict[str, Any] | None:
        if not raw_text:
            return None
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
