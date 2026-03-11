"""
InkPi 书法评测系统 - 数据库服务

使用 SQLite3 进行数据持久化存储
"""
import sqlite3
from typing import List, Optional
from datetime import datetime
import logging
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DB_CONFIG, DB_PATH
from models.evaluation_result import EvaluationResult


class DatabaseService:
    """数据库服务"""
    
    def __init__(self, db_path: Path = None):
        self.logger = logging.getLogger(__name__)
        self.db_path = db_path or DB_PATH
        self.table_name = DB_CONFIG["table_name"]
        self.max_records = DB_CONFIG["max_records"]
        
        # 初始化数据库
        self._init_database()
        
    def _init_database(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute(f"""
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
                character_name TEXT
            )
        """)
        
        # 创建索引
        cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_timestamp 
            ON {self.table_name}(timestamp DESC)
        """)
        
        conn.commit()
        conn.close()
        
        self.logger.info(f"数据库初始化完成: {self.db_path}")
        
    def save(self, result: EvaluationResult) -> int:
        """
        保存评测结果
        
        Args:
            result: 评测结果
            
        Returns:
            插入的记录ID
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute(f"""
            INSERT INTO {self.table_name} 
            (total_score, structure_score, stroke_score, balance_score, rhythm_score,
             feedback, timestamp, image_path, processed_image_path, character_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result.total_score,
            result.detail_scores.get("结构", 0),
            result.detail_scores.get("笔画", 0),
            result.detail_scores.get("平衡", 0),
            result.detail_scores.get("韵律", 0),
            result.feedback,
            result.timestamp.isoformat(),
            result.image_path,
            result.processed_image_path,
            result.character_name
        ))
        
        record_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        self.logger.info(f"保存评测记录: id={record_id}, score={result.total_score}")
        
        # 检查是否超过最大记录数
        self._cleanup_old_records()
        
        return record_id
    
    def get_by_id(self, record_id: int) -> Optional[EvaluationResult]:
        """
        根据ID获取评测记录
        
        Args:
            record_id: 记录ID
            
        Returns:
            EvaluationResult 或 None
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute(f"""
            SELECT id, total_score, structure_score, stroke_score, balance_score, 
                   rhythm_score, feedback, timestamp, image_path, processed_image_path, 
                   character_name
            FROM {self.table_name}
            WHERE id = ?
        """, (record_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return self._row_to_result(row)
        return None
    
    def get_all(self, limit: int = 100, offset: int = 0) -> List[EvaluationResult]:
        """
        获取所有评测记录
        
        Args:
            limit: 最大返回数量
            offset: 偏移量
            
        Returns:
            EvaluationResult 列表
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute(f"""
            SELECT id, total_score, structure_score, stroke_score, balance_score, 
                   rhythm_score, feedback, timestamp, image_path, processed_image_path, 
                   character_name
            FROM {self.table_name}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_result(row) for row in rows]
    
    def get_recent(self, count: int = 10) -> List[EvaluationResult]:
        """
        获取最近的评测记录
        
        Args:
            count: 返回数量
            
        Returns:
            EvaluationResult 列表
        """
        return self.get_all(limit=count)
    
    def get_by_date_range(
        self, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[EvaluationResult]:
        """
        获取指定日期范围内的记录
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            EvaluationResult 列表
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute(f"""
            SELECT id, total_score, structure_score, stroke_score, balance_score, 
                   rhythm_score, feedback, timestamp, image_path, processed_image_path, 
                   character_name
            FROM {self.table_name}
            WHERE timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp DESC
        """, (start_date.isoformat(), end_date.isoformat()))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_result(row) for row in rows]
    
    def get_by_character(self, character: str) -> List[EvaluationResult]:
        """
        获取指定字符的评测记录
        
        Args:
            character: 字符名称
            
        Returns:
            EvaluationResult 列表
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute(f"""
            SELECT id, total_score, structure_score, stroke_score, balance_score, 
                   rhythm_score, feedback, timestamp, image_path, processed_image_path, 
                   character_name
            FROM {self.table_name}
            WHERE character_name = ?
            ORDER BY timestamp DESC
        """, (character,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_result(row) for row in rows]
    
    def delete(self, record_id: int) -> bool:
        """
        删除评测记录
        
        Args:
            record_id: 记录ID
            
        Returns:
            是否删除成功
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute(f"DELETE FROM {self.table_name} WHERE id = ?", (record_id,))
        
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        if deleted:
            self.logger.info(f"删除评测记录: id={record_id}")
            
        return deleted
    
    def get_statistics(self) -> dict:
        """
        获取统计数据
        
        Returns:
            统计信息字典
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # 总记录数
        cursor.execute(f"SELECT COUNT(*) FROM {self.table_name}")
        total_count = cursor.fetchone()[0]
        
        # 平均分
        cursor.execute(f"SELECT AVG(total_score) FROM {self.table_name}")
        avg_score = cursor.fetchone()[0] or 0
        
        # 最高分
        cursor.execute(f"SELECT MAX(total_score) FROM {self.table_name}")
        max_score = cursor.fetchone()[0] or 0
        
        # 最低分
        cursor.execute(f"SELECT MIN(total_score) FROM {self.table_name}")
        min_score = cursor.fetchone()[0] or 0
        
        # 各维度平均分
        cursor.execute(f"""
            SELECT AVG(structure_score), AVG(stroke_score), 
                   AVG(balance_score), AVG(rhythm_score)
            FROM {self.table_name}
        """)
        row = cursor.fetchone()
        avg_details = {
            "结构": row[0] or 0,
            "笔画": row[1] or 0,
            "平衡": row[2] or 0,
            "韵律": row[3] or 0,
        }
        
        conn.close()
        
        return {
            "total_count": total_count,
            "average_score": round(avg_score, 1),
            "max_score": max_score,
            "min_score": min_score,
            "average_details": avg_details,
        }
    
    def get_score_trend(self, limit: int = 30) -> List[dict]:
        """
        获取分数趋势数据
        
        Args:
            limit: 返回数量
            
        Returns:
            趋势数据列表
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute(f"""
            SELECT timestamp, total_score, structure_score, stroke_score, 
                   balance_score, rhythm_score
            FROM {self.table_name}
            ORDER BY timestamp ASC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        trend = []
        for row in rows:
            trend.append({
                "timestamp": row[0],
                "total_score": row[1],
                "结构": row[2],
                "笔画": row[3],
                "平衡": row[4],
                "韵律": row[5],
            })
            
        return trend
    
    def _row_to_result(self, row: tuple) -> EvaluationResult:
        """将数据库行转换为 EvaluationResult"""
        (
            id_, total_score, structure_score, stroke_score, balance_score,
            rhythm_score, feedback, timestamp, image_path, processed_image_path,
            character_name
        ) = row
        
        # 解析时间戳
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
            
        return EvaluationResult(
            id=id_,
            total_score=total_score,
            detail_scores={
                "结构": structure_score,
                "笔画": stroke_score,
                "平衡": balance_score,
                "韵律": rhythm_score,
            },
            feedback=feedback,
            timestamp=timestamp,
            image_path=image_path,
            processed_image_path=processed_image_path,
            character_name=character_name,
        )
    
    def _cleanup_old_records(self):
        """清理超出最大记录数的旧记录"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute(f"SELECT COUNT(*) FROM {self.table_name}")
        count = cursor.fetchone()[0]
        
        if count > self.max_records:
            # 删除最旧的记录
            delete_count = count - self.max_records
            cursor.execute(f"""
                DELETE FROM {self.table_name}
                WHERE id IN (
                    SELECT id FROM {self.table_name}
                    ORDER BY timestamp ASC
                    LIMIT ?
                )
            """, (delete_count,))
            conn.commit()
            self.logger.info(f"清理了 {delete_count} 条旧记录")
            
        conn.close()


# 创建全局服务实例
database_service = DatabaseService()