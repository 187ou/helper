"""全文检索服务：聚合搜索任务/日程/记账/演化日志。"""
import logging
from typing import Any

from memory_store.sqlite_db import get_conn

logger = logging.getLogger(__name__)


def global_search(keyword: str, limit_per_type: int = 5) -> dict[str, list[dict[str, Any]]]:
    """全局检索，返回分类结果。"""
    if not keyword or not keyword.strip():
        return {"tasks": [], "schedules": [], "bills": [], "logs": []}

    kw = f"%{keyword.strip()}%"
    conn = get_conn()

    # 任务
    tasks = conn.execute(
        """SELECT id, task_content, task_type, status, priority, create_time
           FROM task_list
           WHERE task_content LIKE ? OR tags LIKE ?
           ORDER BY create_time DESC LIMIT ?""",
        (kw, kw, limit_per_type),
    ).fetchall()
    tasks = [dict(r) | {"_ref": f"/tasks/{r['id']}"} for r in tasks]

    # 日程
    schedules = conn.execute(
        """SELECT id, title, category, schedule_date, schedule_time, status
           FROM daily_schedule
           WHERE title LIKE ? OR note LIKE ?
           ORDER BY schedule_date DESC LIMIT ?""",
        (kw, kw, limit_per_type),
    ).fetchall()
    schedules = [dict(r) for r in schedules]

    # 记账
    bills = conn.execute(
        """SELECT id, bill_type, amount, category, description, bill_date
           FROM bill_record
           WHERE description LIKE ? OR category LIKE ?
           ORDER BY bill_date DESC LIMIT ?""",
        (kw, kw, limit_per_type),
    ).fetchall()
    bills = [dict(r) for r in bills]

    # 演化日志
    logs = conn.execute(
        """SELECT id, evo_type, before_content, after_content, evo_time
           FROM evolution_log
           WHERE before_content LIKE ? OR after_content LIKE ?
           ORDER BY id DESC LIMIT ?""",
        (kw, kw, limit_per_type),
    ).fetchall()
    logs = [dict(r) for r in logs]

    conn.close()
    return {"tasks": tasks, "schedules": schedules, "bills": bills, "logs": logs}
