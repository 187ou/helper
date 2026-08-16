"""高频模板自动固化（基于使用频次 + 质量门槛检测）。

固化门槛：
- 频次 >= 5 次（避免一次性任务污染模板库）
- 平均得分 >= 70 分（确保固化的是高质量流程）
"""
import json
import logging
from typing import Any

from memory_store.sqlite_db import get_conn, now_str
from memory_store.user_weight import get_all_habits

logger = logging.getLogger(__name__)

# ── 固化门槛 ──
MIN_TEMPLATE_FREQ = 5       # 最低频次（避免一次性任务污染）
MIN_AVG_SCORE = 70.0        # 最低平均分（确保高质量流程）


def check_and_save_template(task_text: str, steps: list[dict]) -> dict[str, Any] | None:
    """检查任务是否高频且高质量，若是则固化为模板。

    双重门槛：
    1. 频次 >= MIN_TEMPLATE_FREQ（默认 5 次）
    2. 历史平均得分 >= MIN_AVG_SCORE（默认 70 分）
    """
    # 提取习惯关键词
    from evolution_core.weight_evolve import _extract_habit_key
    habit_key = _extract_habit_key(task_text)

    # 检查频次
    conn = get_conn()
    habit = conn.execute(
        "SELECT * FROM user_habit_weight WHERE habit_key = ?", (habit_key,)
    ).fetchone()

    if not habit or habit["freq_count"] < MIN_TEMPLATE_FREQ:
        conn.close()
        return None  # 频次不够，不固化

    # 检查平均得分（从历史任务计算）
    avg_score = _calc_habit_avg_score(conn, habit_key)
    conn.close()

    if avg_score < MIN_AVG_SCORE:
        logger.debug("模板固化跳过 %s: 平均分 %.1f < %.1f", habit_key, avg_score, MIN_AVG_SCORE)
        return None  # 质量不达标，不固化

    # 检查是否已有同名模板
    conn = get_conn()
    existing = conn.execute(
        "SELECT id FROM custom_template WHERE name = ?", (habit_key,)
    ).fetchone()

    if existing:
        conn.close()
        logger.info("模板已存在: %s", habit_key)
        return None

    # 固化模板
    flow = {
        "source_task": task_text,
        "habit_key": habit_key,
        "freq_count": habit["freq_count"],
        "avg_score": round(avg_score, 1),
        "steps": steps,
    }
    conn = get_conn()
    conn.execute(
        "INSERT INTO custom_template (name, task_flow_json) VALUES (?, ?)",
        (habit_key, json.dumps(flow, ensure_ascii=False)),
    )
    conn.commit()
    conn.close()
    logger.info("固化模板: %s (频次 %d, 均分 %.1f)", habit_key, habit["freq_count"], avg_score)
    return {"name": habit_key, "freq": habit["freq_count"], "avg_score": round(avg_score, 1)}


def _calc_habit_avg_score(conn, habit_key: str) -> float:
    """计算某习惯关键词的历史平均得分。"""
    try:
        keyword = f"%{habit_key}%"
        row = conn.execute(
            """SELECT AVG(work_score) as avg_work, AVG(life_score) as avg_life, COUNT(*) as cnt
               FROM task_list
               WHERE (task_content LIKE ? OR tags LIKE ?)
                 AND status IN ('done', 'success')
                 AND (work_score > 0 OR life_score > 0)""",
            (keyword, keyword),
        ).fetchone()

        if not row or row["cnt"] == 0:
            return 0.0

        # 取 work_score 和 life_score 中有效的一个
        scores = []
        if row["avg_work"] and row["avg_work"] > 0:
            scores.append(row["avg_work"])
        if row["avg_life"] and row["avg_life"] > 0:
            scores.append(row["avg_life"])

        return sum(scores) / len(scores) if scores else 0.0
    except Exception:
        return 0.0


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
