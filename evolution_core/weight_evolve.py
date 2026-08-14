"""用户记忆权重迭代（基于打分+频次+时间衰减）。"""
import logging
from datetime import datetime
from typing import Any

from memory_store.user_weight import (
    inc_freq, get_all_habits, set_weight, decay_expired
)
from memory_store.sqlite_db import get_conn
from config.app_const import WEIGHT_DECAY_DAYS, EVOLUTION_THRESHOLD

logger = logging.getLogger(__name__)


def evolve_from_task(task_text: str, score: float) -> None:
    """根据任务结果迭代权重。"""
    # 提取习惯关键词（从任务文本中提取关键行为）
    habit_key = _extract_habit_key(task_text)

    # 打分高于阈值 → 提权；低于阈值 → 降权
    if score >= EVOLUTION_THRESHOLD:
        delta = min(1.0, (score - EVOLUTION_THRESHOLD) / 40)  # 最高 +1
        inc_freq(habit_key, delta)
        logger.info("提权: %s (+%.2f), 得分 %.1f", habit_key, delta, score)
    else:
        delta = -0.5
        conn = get_conn()
        existing = conn.execute(
            "SELECT weight FROM user_habit_weight WHERE habit_key = ?", (habit_key,)
        ).fetchone()
        if existing:
            new_w = max(0, existing["weight"] + delta)
            conn.execute(
                "UPDATE user_habit_weight SET weight = ? WHERE habit_key = ?",
                (new_w, habit_key),
            )
            conn.commit()
        conn.close()
        logger.info("降权: %s (%.2f), 得分 %.1f", habit_key, delta, score)


def run_decay() -> int:
    """执行过期降权。"""
    return decay_expired(WEIGHT_DECAY_DAYS)


def get_top_habits(n: int = 10) -> list[dict[str, Any]]:
    """获取高权重习惯。"""
    return get_all_habits(valid_only=True)[:n]


def _extract_habit_key(task_text: str) -> str:
    """从任务文本提取习惯关键词。"""
    # 常见模式匹配
    patterns = {
        "周报": ["周报", "周总结", "weekly"],
        "月报": ["月报", "月总结", "monthly"],
        "记账": ["记账", "开销", "收支", "账单"],
        "日程": ["日程", "计划", "排班"],
        "报销": ["报销", "票据"],
        "会议纪要": ["会议纪要", "会议记录"],
        "桌面整理": ["整理", "归档", "归类"],
    }
    for key, keywords in patterns.items():
        for kw in keywords:
            if kw in task_text:
                return key
    # 兜底：取前 10 字符
    return task_text[:10]
