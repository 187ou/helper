"""Repository 基类。"""
import sqlite3
import logging
from typing import Any
from config.path_config import DB_PATH, ensure_dirs

logger = logging.getLogger(__name__)


class BaseRepository:
    """通用 SQLite Repository。"""

    def __init__(self, db_path: str = ""):
        self.db_path = db_path or str(DB_PATH)

    def _conn(self) -> sqlite3.Connection:
        """获取连接。"""
        ensure_dirs()
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _execute(self, sql: str, params: tuple = ()) -> list[dict]:
        """执行查询，返回字典列表。"""
        conn = self._conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def _execute_one(self, sql: str, params: tuple = ()) -> dict | None:
        """执行查询，返回单条。"""
        conn = self._conn()
        try:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def _insert(self, sql: str, params: tuple = ()) -> int:
        """插入并返回 lastrowid。"""
        conn = self._conn()
        try:
            cursor = conn.execute(sql, params)
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def _update(self, sql: str, params: tuple = ()) -> int:
        """更新并返回影响行数。"""
        conn = self._conn()
        try:
            cursor = conn.execute(sql, params)
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()
