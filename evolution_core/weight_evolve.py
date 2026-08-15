"""用户记忆权重迭代（深化版）：上下文感知 + 任务类型分化（含完整边缘处理）。

边缘情况处理：
1. 空任务文本 → 跳过不处理
2. 权重溢出 → clamp 到 [0, 10]
3. 零除（无历史数据）→ 返回默认值
4. DB 失败 → 记录日志 + 不中断主流程
5. 未知任务类型 → 使用默认权重配置
6. 负分/超高分 → clamp 到合理范围
7. 关联传导时目标类型不存在 → 静默跳过
"""
import logging
from datetime import datetime
from typing import Any

from memory_store.user_weight import (
    inc_freq, get_all_habits, set_weight, decay_expired, get_habit,
)
from memory_store.sqlite_db import get_conn
from config.app_const import WEIGHT_DECAY_DAYS, EVOLUTION_THRESHOLD
from evolution_core.safe_ops import safe_divide, clamp_value, sanitize_text

logger = logging.getLogger(__name__)

_WEIGHT_CONFIG = {
    "base_boost": 0.5,
    "score_multiplier": 0.02,
    "success_bonus": 0.3,
    "fail_penalty": 0.5,
    "max_weight": 10.0,
    "min_weight": 0.0,
    "decay_rate": 0.1,
}

_TYPE_TRANSFER = {
    "work": {"mix": 0.2},
    "life": {"mix": 0.2},
    "mix": {"work": 0.1, "life": 0.1},
}

_HABIT_PATTERNS: dict[str, dict[str, list[str]]] = {
    "work": {
        "周报": ["周报", "周总结", "weekly"],
        "月报": ["月报", "月总结", "monthly"],
        "日报": ["日报", "日总结", "daily"],
        "报销": ["报销", "票据", "发票"],
        "会议纪要": ["会议纪要", "会议记录", "会议总结"],
        "文书": ["报告", "总结", "方案", "计划", "公文"],
        "Excel": ["Excel", "表格", "数据", "台账"],
        "归档": ["归档", "整理", "归类", "收纳"],
    },
    "life": {
        "记账": ["记账", "开销", "收支", "账单", "消费"],
        "日程": ["日程", "计划", "排班", "出行"],
        "购物": ["购物", "买菜", "购物清单"],
        "家务": ["家务", "清洁", "打扫"],
    },
    "health": {
        "睡眠": ["睡眠", "睡觉", "作息"],
        "运动": ["运动", "健身", "跑步", "锻炼"],
        "饮食": ["饮食", "喝水", "忌口", "食谱"],
        "久坐": ["久坐", "休息", "活动"],
    },
}


def evolve_from_task(task_text: str, score: float, task_type: str = "work",
                     success: bool = True, duration: float = 0) -> dict[str, float]:
    """根据任务结果迭代权重（上下文感知版）。"""
    # 边缘：空文本跳过
    if not task_text or not task_text.strip():
        return {}

    task_text = sanitize_text(task_text, max_length=200)
    score = clamp_value(score, 0, 100)
    duration = max(0, duration)

    habit_keys = _extract_habit_keys(task_text, task_type)
    if not habit_keys:
        habit_keys = [_extract_generic_key(task_text)]

    changes = {}
    for habit_key in habit_keys:
        try:
            delta = _calculate_weight_delta(habit_key, score, task_type, success, duration)
            if delta != 0:
                _apply_delta(habit_key, delta)
                changes[habit_key] = round(delta, 3)
        except Exception as e:
            logger.warning("权重更新失败 [%s]: %s", habit_key, e)

    # 关联传导
    if changes:
        try:
            _transfer_weight(task_type, changes)
        except Exception as e:
            logger.warning("权重传导失败: %s", e)

    if changes:
        logger.info("权重迭代: %s (类型 %s, 得分 %.1f)", changes, task_type, score)

    return changes


def run_decay() -> int:
    """执行过期降权。"""
    try:
        return decay_expired(WEIGHT_DECAY_DAYS)
    except Exception as e:
        logger.error("过期降权失败: %s", e)
        return 0


def get_top_habits(n: int = 10) -> list[dict[str, Any]]:
    """获取高权重习惯。"""
    n = clamp_value(n, 1, 100)
    try:
        return get_all_habits(valid_only=True)[:int(n)]
    except Exception:
        return []


def get_habit_profile() -> dict[str, list[dict]]:
    """获取按类型分组的习惯画像。"""
    try:
        habits = get_all_habits(valid_only=True)
    except Exception:
        return {"work": [], "life": [], "health": [], "other": []}

    profile: dict[str, list[dict]] = {"work": [], "life": [], "health": [], "other": []}
    for habit in habits:
        habit_type = _classify_habit_type(habit["habit_key"])
        profile[habit_type].append(habit)
    return profile


def get_weight_trend(habit_key: str, window: int = 30) -> dict[str, Any]:
    """获取权重变化趋势。"""
    if not habit_key:
        return {"trend": "no_data", "average": 0, "count": 0}

    window = clamp_value(window, 1, 365)
    from memory_store.sqlite_db import get_conn
    conn = get_conn()
    try:
        keyword = f"%{habit_key}%"
        rows = conn.execute(
            """SELECT work_score, life_score, status, create_time FROM task_list
               WHERE task_content LIKE ? OR tags LIKE ?
               ORDER BY create_time DESC LIMIT ?""",
            (keyword, keyword, int(window)),
        ).fetchall()
    except Exception:
        return {"trend": "no_data", "average": 0, "count": 0}
    finally:
        conn.close()

    if not rows:
        return {"trend": "no_data", "average": 0, "count": 0}

    scores = [r["work_score"] for r in rows if r["work_score"] > 0]
    avg_score = safe_avg(scores)
    recent_avg = safe_avg(scores[:5])

    return {
        "trend": "improving" if recent_avg > avg_score + 3 else "declining" if recent_avg < avg_score - 3 else "stable",
        "average": round(avg_score, 1),
        "recent_average": round(recent_avg, 1),
        "count": len(rows),
    }


# ── 内部实现 ──

def _calculate_weight_delta(habit_key: str, score: float, task_type: str, success: bool, duration: float) -> float:
    """计算权重变化量（多因子）。"""
    if score >= EVOLUTION_THRESHOLD:
        base_delta = _WEIGHT_CONFIG["base_boost"]
        score_bonus = (score - EVOLUTION_THRESHOLD) * _WEIGHT_CONFIG["score_multiplier"]
        delta = base_delta + score_bonus

        if success:
            delta += _WEIGHT_CONFIG["success_bonus"]

        # 效率加成
        if 0 < duration < 30 and score >= 80:
            delta += 0.2
    else:
        delta = -_WEIGHT_CONFIG["fail_penalty"]
        if not success:
            delta -= 0.3

    return delta


def _apply_delta(habit_key: str, delta: float) -> None:
    """应用权重变更（带上下限）。"""
    try:
        habit = get_habit(habit_key)
        if habit:
            current = habit["weight"]
            new_weight = clamp_value(current + delta, _WEIGHT_CONFIG["min_weight"], _WEIGHT_CONFIG["max_weight"])
            set_weight(habit_key, round(new_weight, 2))
            inc_freq(habit_key, delta)
        else:
            from memory_store.user_weight import create_habit
            new_weight = clamp_value(5.0 + delta, _WEIGHT_CONFIG["min_weight"], _WEIGHT_CONFIG["max_weight"])
            create_habit(habit_key, weight=new_weight)
    except Exception as e:
        logger.warning("权重应用失败 [%s]: %s", habit_key, e)


def _transfer_weight(source_type: str, changes: dict[str, float]) -> None:
    """权重传导。"""
    transfers = _TYPE_TRANSFER.get(source_type, {})
    if not transfers:
        return

    avg_delta = safe_avg(list(changes.values()))
    if avg_delta <= 0:
        return

    for target_type, ratio in transfers.items():
        transfer_delta = avg_delta * ratio
        try:
            habits = get_all_habits(valid_only=True)
            for habit in habits:
                if _classify_habit_type(habit["habit_key"]) == target_type:
                    _apply_delta(habit["habit_key"], transfer_delta * 0.5)
        except Exception:
            pass


def _extract_habit_keys(task_text: str, task_type: str) -> list[str]:
    """从任务文本提取习惯关键词。"""
    if not task_text:
        return []
    patterns = _HABIT_PATTERNS.get(task_type, {})
    matched = []
    for habit_key, keywords in patterns.items():
        for kw in keywords:
            if kw in task_text:
                matched.append(habit_key)
                break
    return matched


def _extract_generic_key(task_text: str) -> str:
    """兜底：提取通用关键词。"""
    if not task_text:
        return "unknown"
    return task_text[:10] if len(task_text) >= 4 else f"task_{abs(hash(task_text)) % 1000}"


def _classify_habit_type(habit_key: str) -> str:
    """判断习惯属于哪个任务类型。"""
    for habit_type, patterns in _HABIT_PATTERNS.items():
        if habit_key in patterns:
            return habit_type
    return "other"
