"""高频模板自动固化（基于使用频次检测）。"""
import json
import logging
from typing import Any

from memory_store.sqlite_db import get_conn, now_str
from memory_store.user_weight import get_all_habits

logger = logging.getLogger(__name__)


def check_and_save_template(task_text: str, steps: list[dict]) -> dict[str, Any] | None:
    """检查任务是否高频，若是则固化为模板。"""
    # 提取习惯关键词
    from evolution_core.weight_evolve import _extract_habit_key
    habit_key = _extract_habit_key(task_text)

    # 检查频次
    conn = get_conn()
    habit = conn.execute(
        "SELECT * FROM user_habit_weight WHERE habit_key = ?", (habit_key,)
    ).fetchone()

    if not habit or habit["freq_count"] < 2:
        conn.close()
        return None  # 频次不够，不固化

    # 检查是否已有同名模板
    existing = conn.execute(
        "SELECT id FROM custom_template WHERE name = ?", (habit_key,)
    ).fetchone()
    conn.close()

    if existing:
        logger.info("模板已存在: %s", habit_key)
        return None

    # 固化模板
    flow = {
        "source_task": task_text,
        "habit_key": habit_key,
        "freq_count": habit["freq_count"],
        "steps": steps,
    }
    conn = get_conn()
    conn.execute(
        "INSERT INTO custom_template (name, task_flow_json) VALUES (?, ?)",
        (habit_key, json.dumps(flow, ensure_ascii=False)),
    )
    conn.commit()
    conn.close()
    logger.info("固化模板: %s (频次 %d)", habit_key, habit["freq_count"])
    return {"name": habit_key, "freq": habit["freq_count"]}


def list_templates() -> list[dict[str, Any]]:
    """列出所有模板。"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM custom_template ORDER BY create_time DESC"
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        flow = json.loads(r["task_flow_json"]) if r["task_flow_json"] else {}
        result.append({
            "id": r["id"],
            "name": r["name"],
            "steps": flow.get("steps", []),
            "freq": flow.get("freq_count", 0),
            "create_time": r["create_time"],
        })
    return result


def get_template(name: str) -> dict[str, Any] | None:
    """获取指定模板。"""
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM custom_template WHERE name = ?", (name,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    return json.loads(row["task_flow_json"]) if row["task_flow_json"] else None
