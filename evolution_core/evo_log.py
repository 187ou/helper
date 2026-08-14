"""演化日志记录：将优化操作写入 evolution_log 表。"""
import json
import logging
from typing import Any

from memory_store.sqlite_db import get_conn, now_str
from config.app_const import EvoType

logger = logging.getLogger(__name__)


def log_evo(evo_type: str, before: str, after: str) -> int:
    """记录一次演化操作，返回记录 ID。"""
    conn = get_conn()
    cursor = conn.execute(
        """INSERT INTO evolution_log (evo_type, before_content, after_content)
           VALUES (?, ?, ?)""",
        (evo_type, before, after),
    )
    conn.commit()
    rid = cursor.lastrowid
    conn.close()
    logger.info("演化日志 [%s]: %s → %s", evo_type, before[:50], after[:50])
    return rid


def log_flow_optimize(before_steps: list, after_steps: list) -> int:
    """记录流程优化。"""
    before_text = " → ".join(s.get("name", "?") for s in before_steps)
    after_text = " → ".join(s.get("name", "?") for s in after_steps)
    return log_evo(EvoType.FLOW.value, before_text, after_text)


def log_weight_change(habit_key: str, old_w: float, new_w: float) -> int:
    """记录权重变化。"""
    return log_evo(
        EvoType.WEIGHT.value,
        f"{habit_key} = {old_w:.1f}",
        f"{habit_key} = {new_w:.1f}",
    )


def log_template_save(name: str, freq: int) -> int:
    """记录模板固化。"""
    return log_evo(
        EvoType.TEMPLATE.value,
        f"高频任务: {name}",
        f"固化模板 (频次 {freq})",
    )


def list_logs(evo_type: str = "", limit: int = 50) -> list[dict[str, Any]]:
    """列出演化日志。"""
    conn = get_conn()
    sql = "SELECT * FROM evolution_log"
    params: list = []
    if evo_type:
        sql += " WHERE evo_type = ?"
        params.append(evo_type)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats() -> dict[str, int]:
    """获取演化统计。"""
    conn = get_conn()
    flow_count = conn.execute(
        "SELECT COUNT(*) FROM evolution_log WHERE evo_type = ?", (EvoType.FLOW.value,)
    ).fetchone()[0]
    weight_count = conn.execute(
        "SELECT COUNT(*) FROM evolution_log WHERE evo_type = ?", (EvoType.WEIGHT.value,)
    ).fetchone()[0]
    tpl_count = conn.execute("SELECT COUNT(*) FROM custom_template").fetchone()[0]
    tool_count = conn.execute(
        "SELECT COUNT(*) FROM evolution_log WHERE evo_type = ?", (EvoType.TOOL.value,)
    ).fetchone()[0]
    conn.close()
    return {
        "flow_optimizations": flow_count,
        "weight_changes": weight_count,
        "template_count": tpl_count,
        "tool_count": tool_count,
    }
