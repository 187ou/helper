"""任务数据访问。"""
import json
import logging
from datetime import datetime
from memory_store.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class TaskRepository(BaseRepository):
    """任务列表 CRUD。"""

    def save(self, task_type: str, content: str, steps: list, status: str,
             cost_time: float, work_score: float, life_score: float) -> int:
        """保存任务记录。"""
        sql = """INSERT INTO task_list
                 (task_type, task_content, task_steps, status, cost_time, work_score, life_score)
                 VALUES (?, ?, ?, ?, ?, ?, ?)"""
        task_id = self._insert(sql, (
            task_type, content, json.dumps(steps, ensure_ascii=False),
            status, cost_time, work_score, life_score,
        ))
        logger.debug("任务已保存: id=%d", task_id)
        return task_id

    def list_all(self, limit: int = 50) -> list[dict]:
        """列出最近任务。"""
        return self._execute(
            "SELECT * FROM task_list ORDER BY id DESC LIMIT ?", (limit,)
        )

    def get(self, task_id: int) -> dict | None:
        """按 ID 查询。"""
        return self._execute_one("SELECT * FROM task_list WHERE id = ?", (task_id,))
