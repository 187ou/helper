"""用户习惯权重 CRUD，封装 user_habit_weight 表。"""
import logging
from datetime import datetime
from typing import Any

from memory_store.sqlite_db import get_conn, now_str
from config.app_const import WEIGHT_MAX, WEIGHT_MIN

logger = logging.getLogger(__name__)


def get_habit(habit_key: str) -> dict[str, Any] | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM user_habit_weight WHERE habit_key = ?", (habit_key,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_habits(valid_only: bool = False) -> list[dict[str, Any]]:
    conn = get_conn()
    sql = "SELECT * FROM user_habit_weight"
    if valid_only:
        sql += " WHERE is_valid = 1"
    sql += " ORDER BY weight DESC"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def set_weight(habit_key: str, weight: float) -> None:
    weight = max(WEIGHT_MIN, min(WEIGHT_MAX, weight))
    conn = get_conn()
    conn.execute(
        """INSERT INTO user_habit_weight (habit_key, weight, freq_count, last_use_time, is_valid)
           VALUES (?, ?, 1, ?, 1)
           ON CONFLICT(habit_key) DO UPDATE SET weight = excluded.weight""",
        (habit_key, weight, now_str()),
    )
    conn.commit()
    conn.close()


def inc_freq(habit_key: str, delta_weight: float = 0.1) -> None:
    """触发频次+1，权重微增。"""
    conn = get_conn()
    existing = conn.execute(
        "SELECT weight FROM user_habit_weight WHERE habit_key = ?", (habit_key,)
    ).fetchone()
    if existing:
        new_w = min(WEIGHT_MAX, existing["weight"] + delta_weight)
        conn.execute(
            "UPDATE user_habit_weight SET freq_count = freq_count + 1, weight = ?, last_use_time = ? WHERE habit_key = ?",
            (new_w, now_str(), habit_key),
        )
    else:
        conn.execute(
            "INSERT INTO user_habit_weight (habit_key, weight, freq_count, last_use_time, is_valid) VALUES (?, ?, 1, ?, 1)",
            (habit_key, delta_weight, now_str()),
        )
    conn.commit()
    conn.close()


def decay_expired(days: int = 30) -> int:
    """超过 days 天未使用的习惯降权 50%，返回受影响行数。"""
    conn = get_conn()
    cursor = conn.execute(
        """UPDATE user_habit_weight
           SET weight = MAX(0, weight * 0.5), is_valid = CASE WHEN weight * 0.5 < 0.5 THEN 0 ELSE is_valid END
           WHERE last_use_time < datetime('now', ?)""",
        (f"-days {days}",),
    )
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    logger.info("降权过期习惯 %d 条", affected)
    return affected
