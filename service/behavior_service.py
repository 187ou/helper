"""用户行为全量采集服务（2.1）。"""
import json
import logging
from datetime import datetime
from typing import Any

from memory_store.sqlite_db import get_conn

logger = logging.getLogger(__name__)

# 允许采集的事件类型
VALID_EVENTS = {
    "task_create", "task_update", "task_delete", "task_status_change",
    "task_complete", "task_modify", "task_reject",
    "schedule_add", "schedule_complete",
    "bill_add", "bill_delete",
    "chat_send", "search_query",
    "page_view", "feature_use",
}


def log_event(event_type: str, event_data: dict | None = None) -> int | None:
    """记录一条行为事件。

    如果采集关闭则直接返回 None（由调用方先检查 is_tracking_enabled）。
    """
    if event_type not in VALID_EVENTS:
        return None

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    cursor = conn.execute(
        "INSERT INTO behavior_log (event_type, event_data, create_time) VALUES (?, ?, ?)",
        (event_type, json.dumps(event_data or {}, ensure_ascii=False), now),
    )
    conn.commit()
    log_id = cursor.lastrowid
    conn.close()
    return log_id


def list_events(
    event_type: str = "",
    start_time: str = "",
    end_time: str = "",
    limit: int = 100,
) -> list[dict[str, Any]]:
    """查询行为日志。"""
    sql = "SELECT * FROM behavior_log WHERE 1=1"
    params: list = []

    if event_type:
        sql += " AND event_type = ?"
        params.append(event_type)
    if start_time:
        sql += " AND create_time >= ?"
        params.append(start_time)
    if end_time:
        sql += " AND create_time <= ?"
        params.append(end_time)

    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    conn = get_conn()
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    result = []
    for r in rows:
        d = dict(r)
        try:
            d["event_data"] = json.loads(d.get("event_data", "{}"))
        except json.JSONDecodeError:
            d["event_data"] = {}
        result.append(d)
    return result


def get_statistics() -> dict[str, Any]:
    """行为统计。"""
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) FROM behavior_log").fetchone()[0]

    # 按类型统计
    type_stats = {}
    for row in conn.execute(
        "SELECT event_type, COUNT(*) as cnt FROM behavior_log GROUP BY event_type ORDER BY cnt DESC"
    ):
        type_stats[row["event_type"]] = row["cnt"]

    # 近 7 天活跃度
    daily = conn.execute(
        """SELECT DATE(create_time) as d, COUNT(*) as cnt FROM behavior_log
           WHERE create_time >= datetime('now', '-7 days')
           GROUP BY d ORDER BY d"""
    ).fetchall()
    conn.close()

    return {
        "total": total,
        "by_type": type_stats,
        "daily_active": [{"date": r["d"], "count": r["cnt"]} for r in daily],
    }


def clear_all() -> int:
    """清空所有行为数据。"""
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM behavior_log").fetchone()[0]
    conn.execute("DELETE FROM behavior_log")
    conn.commit()
    conn.close()
    logger.info("清空行为数据 %d 条", count)
    return count
