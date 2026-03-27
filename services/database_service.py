"""SQLite persistence for local evaluation results."""

from __future__ import annotations

import logging
import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DB_CONFIG, DB_PATH
from models.evaluation_result import EvaluationResult


class DatabaseService:
    """Persist and query local evaluation records."""

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
                    structure_score INTEGER NOT NULL,
                    stroke_score INTEGER NOT NULL,
                    balance_score INTEGER NOT NULL,
                    rhythm_score INTEGER NOT NULL,
                    feedback TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    image_path TEXT,
                    processed_image_path TEXT,
                    character_name TEXT,
                    style TEXT,
                    style_confidence REAL,
                    recognition_status TEXT,
                    recognition_confidence REAL,
                    score_mode TEXT,
                    score_explanation TEXT
                )
                """
            )

            cursor.execute(f"PRAGMA table_info({self.table_name})")
            existing_columns = {row[1] for row in cursor.fetchall()}
            for column_name, column_type in (
                ("style", "TEXT"),
                ("style_confidence", "REAL"),
                ("recognition_status", "TEXT"),
                ("recognition_confidence", "REAL"),
                ("score_mode", "TEXT"),
                ("score_explanation", "TEXT"),
            ):
                if column_name not in existing_columns:
                    cursor.execute(
                        f"ALTER TABLE {self.table_name} ADD COLUMN {column_name} {column_type}"
                    )

            cursor.execute(
                f"""
                CREATE INDEX IF NOT EXISTS idx_{self.table_name}_timestamp
                ON {self.table_name}(timestamp DESC)
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
                    structure_score,
                    stroke_score,
                    balance_score,
                    rhythm_score,
                    feedback,
                    timestamp,
                    image_path,
                    processed_image_path,
                    character_name,
                    style,
                    style_confidence,
                    recognition_status,
                    recognition_confidence,
                    score_mode,
                    score_explanation
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.total_score,
                    result.detail_scores.get("结构", result.detail_scores.get("缁撴瀯", 0)),
                    result.detail_scores.get("笔画", result.detail_scores.get("绗旂敾", 0)),
                    result.detail_scores.get("平衡", result.detail_scores.get("骞宠　", 0)),
                    result.detail_scores.get("韵律", result.detail_scores.get("闊靛緥", 0)),
                    result.feedback,
                    result.timestamp.isoformat(),
                    result.image_path,
                    result.processed_image_path,
                    result.character_name,
                    result.style,
                    result.style_confidence,
                    result.recognition_status,
                    result.recognition_confidence,
                    result.score_mode,
                    result.score_explanation,
                ),
            )
            record_id = int(cursor.lastrowid)
            conn.commit()

        self.logger.info("Saved evaluation record: id=%s score=%s", record_id, result.total_score)

        try:
            from services.cloud_sync_service import cloud_sync_service

            cloud_sync_service.upload_result_async(result, local_record_id=record_id)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Cloud sync bootstrap failed: %s", exc)

        self._cleanup_old_records()
        return record_id

    def get_by_id(self, record_id: int) -> Optional[EvaluationResult]:
        """Fetch a single result by id."""
        with self._managed_connection() as conn:
            row = conn.execute(
                f"""
                SELECT id, total_score, structure_score, stroke_score, balance_score,
                       rhythm_score, feedback, timestamp, image_path, processed_image_path,
                       character_name, style, style_confidence, recognition_status,
                       recognition_confidence, score_mode, score_explanation
                FROM {self.table_name}
                WHERE id = ?
                """,
                (record_id,),
            ).fetchone()
        return self._row_to_result(row) if row else None

    def get_all(self, limit: int = 100, offset: int = 0) -> list[EvaluationResult]:
        """Fetch evaluation records ordered from newest to oldest."""
        with self._managed_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT id, total_score, structure_score, stroke_score, balance_score,
                       rhythm_score, feedback, timestamp, image_path, processed_image_path,
                       character_name, style, style_confidence, recognition_status,
                       recognition_confidence, score_mode, score_explanation
                FROM {self.table_name}
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        return [self._row_to_result(row) for row in rows]

    def get_recent(self, count: int = 10) -> list[EvaluationResult]:
        """Fetch the newest records."""
        return self.get_all(limit=count)

    def get_by_date_range(self, start_date: datetime, end_date: datetime) -> list[EvaluationResult]:
        """Fetch records within a time range."""
        with self._managed_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT id, total_score, structure_score, stroke_score, balance_score,
                       rhythm_score, feedback, timestamp, image_path, processed_image_path,
                       character_name, style, style_confidence, recognition_status,
                       recognition_confidence, score_mode, score_explanation
                FROM {self.table_name}
                WHERE timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp DESC
                """,
                (start_date.isoformat(), end_date.isoformat()),
            ).fetchall()
        return [self._row_to_result(row) for row in rows]

    def get_by_character(self, character: str) -> list[EvaluationResult]:
        """Fetch records for a specific character."""
        with self._managed_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT id, total_score, structure_score, stroke_score, balance_score,
                       rhythm_score, feedback, timestamp, image_path, processed_image_path,
                       character_name, style, style_confidence, recognition_status,
                       recognition_confidence, score_mode, score_explanation
                FROM {self.table_name}
                WHERE character_name = ?
                ORDER BY timestamp DESC
                """,
                (character,),
            ).fetchall()
        return [self._row_to_result(row) for row in rows]

    def delete(self, record_id: int) -> bool:
        """Delete a record by id."""
        with self._managed_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {self.table_name} WHERE id = ?", (record_id,))
            deleted = cursor.rowcount > 0
            conn.commit()

        if deleted:
            self.logger.info("Deleted evaluation record: id=%s", record_id)
        return deleted

    def get_statistics(self) -> dict:
        """Aggregate statistics for dashboard widgets."""
        with self._managed_connection() as conn:
            total_count = conn.execute(f"SELECT COUNT(*) FROM {self.table_name}").fetchone()[0]
            avg_score = conn.execute(f"SELECT AVG(total_score) FROM {self.table_name}").fetchone()[0] or 0
            max_score = conn.execute(f"SELECT MAX(total_score) FROM {self.table_name}").fetchone()[0] or 0
            min_score = conn.execute(f"SELECT MIN(total_score) FROM {self.table_name}").fetchone()[0] or 0
            row = conn.execute(
                f"""
                SELECT AVG(structure_score), AVG(stroke_score),
                       AVG(balance_score), AVG(rhythm_score)
                FROM {self.table_name}
                """
            ).fetchone()

        return {
            "total_count": total_count,
            "average_score": round(float(avg_score), 1) if total_count else 0,
            "max_score": max_score,
            "min_score": min_score,
            "average_details": {
                "结构": row[0] or 0,
                "笔画": row[1] or 0,
                "平衡": row[2] or 0,
                "韵律": row[3] or 0,
            },
        }

    def get_score_trend(self, limit: int = 30) -> list[dict]:
        """Return ordered score trend data."""
        with self._managed_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT timestamp, total_score, structure_score, stroke_score,
                       balance_score, rhythm_score
                FROM {self.table_name}
                ORDER BY timestamp ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            {
                "timestamp": row["timestamp"],
                "total_score": row["total_score"],
                "结构": row["structure_score"],
                "笔画": row["stroke_score"],
                "平衡": row["balance_score"],
                "韵律": row["rhythm_score"],
            }
            for row in rows
        ]

    def _row_to_result(self, row: sqlite3.Row) -> EvaluationResult:
        """Convert a database row into an EvaluationResult."""
        timestamp = row["timestamp"]
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)

        return EvaluationResult(
            id=row["id"],
            total_score=row["total_score"],
            detail_scores={
                "结构": row["structure_score"],
                "笔画": row["stroke_score"],
                "平衡": row["balance_score"],
                "韵律": row["rhythm_score"],
            },
            feedback=row["feedback"],
            timestamp=timestamp,
            image_path=row["image_path"],
            processed_image_path=row["processed_image_path"],
            character_name=row["character_name"],
            style=row["style"],
            style_confidence=row["style_confidence"],
            recognition_status=row["recognition_status"],
            recognition_confidence=row["recognition_confidence"],
            score_mode=row["score_mode"],
            score_explanation=row["score_explanation"],
        )

    def _cleanup_old_records(self) -> None:
        """Trim old local records when the table grows too large."""
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


database_service = DatabaseService()
