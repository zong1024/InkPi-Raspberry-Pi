"""SQLite persistence for the dual-script InkPi runtime."""

from __future__ import annotations

import json
import logging
import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DB_CONFIG, DB_PATH
from models.evaluation_framework import normalize_script
from models.evaluation_result import EvaluationResult


class DatabaseService:
    """Persist and query dual-script evaluation records."""

    def __init__(self, db_path: Path | None = None):
        self.logger = logging.getLogger(__name__)
        self.db_path = Path(db_path or DB_PATH)
        self.table_name = DB_CONFIG["table_name"]
        self.max_records = int(DB_CONFIG["max_records"])
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
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._managed_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    total_score INTEGER NOT NULL,
                    feedback TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    image_path TEXT,
                    processed_image_path TEXT,
                    script TEXT NOT NULL DEFAULT 'regular',
                    character_name TEXT,
                    ocr_confidence REAL,
                    quality_level TEXT,
                    quality_confidence REAL,
                    dimension_scores_json TEXT,
                    score_debug_json TEXT
                )
                """
            )

            cursor.execute(f"PRAGMA table_info({self.table_name})")
            existing_columns = {row[1] for row in cursor.fetchall()}
            for column_name, column_type in (
                ("script", "TEXT NOT NULL DEFAULT 'regular'"),
                ("dimension_scores_json", "TEXT"),
                ("score_debug_json", "TEXT"),
            ):
                if column_name not in existing_columns:
                    cursor.execute(f"ALTER TABLE {self.table_name} ADD COLUMN {column_name} {column_type}")

            if "script" in {row[1] for row in conn.execute(f"PRAGMA table_info({self.table_name})").fetchall()}:
                conn.execute(
                    f"""
                    UPDATE {self.table_name}
                    SET script = 'regular'
                    WHERE script IS NULL OR TRIM(script) = ''
                    """
                )

            cursor.execute(
                f"""
                CREATE INDEX IF NOT EXISTS idx_{self.table_name}_timestamp
                ON {self.table_name}(timestamp DESC)
                """
            )
            cursor.execute(
                f"""
                CREATE INDEX IF NOT EXISTS idx_{self.table_name}_script_timestamp
                ON {self.table_name}(script, timestamp DESC)
                """
            )
            conn.commit()

        self.logger.info("Database initialized: %s", self.db_path)

    def save(self, result: EvaluationResult) -> int:
        """Save a result locally and trigger cloud sync in the background."""

        with self._managed_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                INSERT INTO {self.table_name}
                (
                    total_score,
                    feedback,
                    timestamp,
                    image_path,
                    processed_image_path,
                    script,
                    character_name,
                    ocr_confidence,
                    quality_level,
                    quality_confidence,
                    dimension_scores_json,
                    score_debug_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.total_score,
                    result.feedback,
                    result.timestamp.isoformat(),
                    result.image_path,
                    result.processed_image_path,
                    result.get_script(),
                    result.character_name,
                    result.ocr_confidence,
                    result.quality_level,
                    result.quality_confidence,
                    json.dumps(result.get_dimension_scores(), ensure_ascii=False)
                    if result.get_dimension_scores() is not None
                    else None,
                    json.dumps(result.score_debug, ensure_ascii=False) if result.score_debug is not None else None,
                ),
            )
            record_id = int(cursor.lastrowid)
            conn.commit()

        self.logger.info("Saved evaluation record: id=%s score=%s script=%s", record_id, result.total_score, result.get_script())

        try:
            from services.cloud_sync_service import cloud_sync_service

            cloud_sync_service.upload_result_async(result, local_record_id=record_id)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Cloud sync bootstrap failed: %s", exc)

        self._cleanup_old_records()
        return record_id

    def get_by_id(self, record_id: int) -> Optional[EvaluationResult]:
        with self._managed_connection() as conn:
            row = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?",
                (record_id,),
            ).fetchone()
        return self._row_to_result(row) if row else None

    def get_all(self, limit: int = 100, offset: int = 0, script: str | None = None) -> list[EvaluationResult]:
        params: list[object] = []
        where_clause = ""
        if script:
            where_clause = "WHERE script = ?"
            params.append(normalize_script(script))
        params.extend([limit, offset])
        with self._managed_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM {self.table_name}
                {where_clause}
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
                """,
                params,
            ).fetchall()
        return [self._row_to_result(row) for row in rows]

    def get_recent(self, count: int = 10, script: str | None = None) -> list[EvaluationResult]:
        return self.get_all(limit=count, script=script)

    def get_by_date_range(self, start_date: datetime, end_date: datetime, script: str | None = None) -> list[EvaluationResult]:
        params: list[object] = [start_date.isoformat(), end_date.isoformat()]
        where_clause = "WHERE timestamp >= ? AND timestamp <= ?"
        if script:
            where_clause += " AND script = ?"
            params.append(normalize_script(script))
        with self._managed_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM {self.table_name}
                {where_clause}
                ORDER BY timestamp DESC
                """,
                params,
            ).fetchall()
        return [self._row_to_result(row) for row in rows]

    def get_by_character(self, character: str, script: str | None = None) -> list[EvaluationResult]:
        params: list[object] = [character]
        where_clause = "WHERE character_name = ?"
        if script:
            where_clause += " AND script = ?"
            params.append(normalize_script(script))
        with self._managed_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM {self.table_name}
                {where_clause}
                ORDER BY timestamp DESC
                """,
                params,
            ).fetchall()
        return [self._row_to_result(row) for row in rows]

    def delete(self, record_id: int) -> bool:
        with self._managed_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {self.table_name} WHERE id = ?", (record_id,))
            deleted = cursor.rowcount > 0
            conn.commit()

        if deleted:
            self.logger.info("Deleted evaluation record: id=%s", record_id)
        return deleted

    def get_statistics(self) -> dict:
        with self._managed_connection() as conn:
            total_count = conn.execute(f"SELECT COUNT(*) FROM {self.table_name}").fetchone()[0]
            avg_score = conn.execute(f"SELECT AVG(total_score) FROM {self.table_name}").fetchone()[0] or 0
            max_score = conn.execute(f"SELECT MAX(total_score) FROM {self.table_name}").fetchone()[0] or 0
            min_score = conn.execute(f"SELECT MIN(total_score) FROM {self.table_name}").fetchone()[0] or 0
            script_rows = conn.execute(
                f"""
                SELECT script, COUNT(*) AS count
                FROM {self.table_name}
                GROUP BY script
                """
            ).fetchall()

        return {
            "total_count": int(total_count),
            "average_score": round(float(avg_score), 1) if total_count else 0,
            "max_score": int(max_score),
            "min_score": int(min_score),
            "script_counts": {
                normalize_script(row["script"]): int(row["count"])
                for row in script_rows
            },
        }

    def get_score_trend(self, limit: int = 30, script: str | None = None) -> list[dict]:
        params: list[object] = [limit]
        where_clause = ""
        if script:
            where_clause = "WHERE script = ?"
            params = [normalize_script(script), limit]
        with self._managed_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT timestamp, total_score, quality_level, character_name, script
                FROM {self.table_name}
                {where_clause}
                ORDER BY timestamp ASC
                LIMIT ?
                """,
                params,
            ).fetchall()

        return [
            {
                "timestamp": row["timestamp"],
                "total_score": row["total_score"],
                "quality_level": row["quality_level"],
                "character_name": row["character_name"],
                "script": normalize_script(row["script"]),
            }
            for row in rows
        ]

    def _row_to_result(self, row: sqlite3.Row) -> EvaluationResult:
        timestamp = row["timestamp"]
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)

        return EvaluationResult(
            id=row["id"],
            total_score=row["total_score"],
            feedback=row["feedback"],
            timestamp=timestamp,
            image_path=row["image_path"],
            processed_image_path=row["processed_image_path"],
            script=normalize_script(row["script"]),
            character_name=row["character_name"],
            ocr_confidence=row["ocr_confidence"],
            quality_level=row["quality_level"] or "medium",
            quality_confidence=row["quality_confidence"],
            dimension_scores=self._load_json_blob(row["dimension_scores_json"]),
            score_debug=self._load_json_blob(row["score_debug_json"]),
        )

    def _cleanup_old_records(self) -> None:
        with self._managed_connection() as conn:
            count = conn.execute(f"SELECT COUNT(*) FROM {self.table_name}").fetchone()[0]
            if count <= self.max_records:
                return

            delete_count = count - self.max_records
            conn.execute(
                f"""
                DELETE FROM {self.table_name}
                WHERE id IN (
                    SELECT id FROM {self.table_name}
                    ORDER BY timestamp ASC
                    LIMIT ?
                )
                """,
                (delete_count,),
            )
            conn.commit()

        self.logger.info("Trimmed %s old local records", delete_count)

    @staticmethod
    def _load_json_blob(value: str | None) -> dict | None:
        if not value:
            return None
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None


database_service = DatabaseService()
