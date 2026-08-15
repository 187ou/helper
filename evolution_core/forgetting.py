"""遗忘机制：防止过期数据污染演化引擎。

核心能力：
1. 偏好过期：长期未使用的偏好自动降权/清除
2. 权重衰减增强：基于时间衰减的权重降低
3. 数据清理：归档/删除过期反馈、低置信度模式
4. 时间窗口：滑动窗口统计替代全量统计

设计原则：
- 遗忘不是删除，而是降权（保留证据但降低影响）
- 衰减曲线：指数衰减（近期影响大，远期影响小）
- 可配置：过期天数、衰减率可调
"""
import logging
import math
from datetime import datetime, timedelta
from typing import Any

from memory_store.sqlite_db import get_conn, now_str
from config.app_const import WEIGHT_DECAY_DAYS
from evolution_core.safe_ops import safe_divide, clamp_value

logger = logging.getLogger(__name__)

# ── 配置 ──
FORGET_CONFIG = {
    "preference_expire_days": 90,       # 偏好过期天数
    "preference_decay_rate": 0.1,       # 偏好每日衰减率
    "weight_decay_days": 30,            # 权重衰减天数
    "weight_decay_rate": 0.15,          # 权重衰减率（每周期）
    "feedback_retention_days": 180,     # 反馈保留天数
    "pattern_min_confidence": 0.2,      # 模式最低置信度（低于此值清理）
    "pattern_expire_days": 60,          # 模式过期天数（未使用）
    "habit_expire_days": 90,            # 习惯过期天数
    "stats_window_days": 90,            # 统计时间窗口
}


# ── 偏好过期 ──

def decay_preferences() -> dict[str, Any]:
    """执行偏好过期衰减。

    对长期未使用的偏好按指数衰减：
    new_confidence = old_confidence * (1 - decay_rate) ^ days
    """
    expire_days = FORGET_CONFIG["preference_expire_days"]
    decay_rate = FORGET_CONFIG["preference_decay_rate"]

    conn = get_conn()
    try:
        # 获取所有偏好
        rows = conn.execute(
            "SELECT * FROM user_preference WHERE confidence > 0"
        ).fetchall()

        decayed_count = 0
        expired_count = 0

        for row in rows:
            pref_key = row["pref_key"]
            last_update = row["update_time"]
            current_confidence = row["confidence"]

            # 计算距今天数
            try:
                last_dt = datetime.strptime(last_update, "%Y-%m-%d %H:%M:%S")
                days_passed = (datetime.now() - last_dt).days
            except (ValueError, TypeError):
                days_passed = 0

            if days_passed <= 0:
                continue

            # 指数衰减
            decay_factor = (1 - decay_rate) ** days_passed
            new_confidence = current_confidence * decay_factor

            if new_confidence < 0.05:
                # 过期：清除偏好
                conn.execute("DELETE FROM user_preference WHERE pref_key = ?", (pref_key,))
                expired_count += 1
                logger.info("偏好过期清除: %s (%.3f → %.3f)", pref_key, current_confidence, new_confidence)
            elif days_passed >= expire_days:
                # 衰减
                conn.execute(
                    "UPDATE user_preference SET confidence = ? WHERE pref_key = ?",
                    (round(new_confidence, 3), pref_key)
                )
                decayed_count += 1

        conn.commit()
        logger.info("偏好衰减完成: %d 衰减, %d 过期清除", decayed_count, expired_count)
        return {"decayed": decayed_count, "expired": expired_count}
    except Exception as e:
        logger.error("偏好衰减失败: %s", e)
        return {"decayed": 0, "expired": 0, "error": str(e)}
    finally:
        conn.close()


def get_active_preferences(days: int = 90, min_confidence: float = 0.3) -> list[dict]:
    """获取活跃的偏好（时间窗口内 + 置信度达标）。"""
    days = clamp_value(days, 1, 365)
    min_confidence = clamp_value(min_confidence, 0, 1)

    cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT * FROM user_preference
               WHERE update_time >= ? AND confidence >= ?
               ORDER BY confidence DESC, evidence_count DESC""",
            (cutoff_date, min_confidence)
        ).fetchall()
    except Exception:
        return []
    finally:
        conn.close()

    result = []
    for row in rows:
        try:
            value = row["pref_value"]
            # 尝试 JSON 解析
            import json
            value = json.loads(value)
        except (Exception,):
            pass
        result.append({
            "key": row["pref_key"],
            "value": value,
            "confidence": row["confidence"],
            "evidence_count": row["evidence_count"],
            "last_evidence": row["last_evidence"],
            "update_time": row["update_time"],
        })
    return result


# ── 权重衰减增强 ──

def enhanced_weight_decay() -> dict[str, Any]:
    """增强版权重衰减（基于时间指数衰减）。

    相比原来的固定比例衰减，使用指数衰减曲线：
    new_weight = old_weight * e^(-λ * days)
    """
    decay_days = FORGET_CONFIG["weight_decay_days"]
    decay_rate = FORGET_CONFIG["weight_decay_rate"]

    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM user_habit_weight WHERE weight > 0"
        ).fetchall()

        decayed_count = 0
        expired_count = 0

        for row in rows:
            habit_key = row["habit_key"]
            last_use = row["last_use_time"] if row["last_use_time"] else ""
            current_weight = row["weight"]

            if not last_use:
                continue

            try:
                last_dt = datetime.strptime(last_use, "%Y-%m-%d %H:%M:%S")
                days_passed = (datetime.now() - last_dt).days
            except (ValueError, TypeError):
                continue

            if days_passed < decay_days:
                continue

            # 指数衰减：w * e^(-λ * days)
            overdue_days = days_passed - decay_days
            decay_factor = math.exp(-decay_rate * overdue_days / decay_days)
            new_weight = current_weight * decay_factor

            if new_weight < 0.1:
                # 过期清除
                conn.execute("DELETE FROM user_habit_weight WHERE habit_key = ?", (habit_key,))
                expired_count += 1
                logger.info("习惯过期清除: %s (%.2f → %.2f, %d天未用)",
                           habit_key, current_weight, new_weight, days_passed)
            else:
                conn.execute(
                    "UPDATE user_habit_weight SET weight = ? WHERE habit_key = ?",
                    (round(new_weight, 2), habit_key)
                )
                decayed_count += 1

        conn.commit()
        logger.info("权重衰减完成: %d 衰减, %d 过期清除", decayed_count, expired_count)
        return {"decayed": decayed_count, "expired": expired_count}
    except Exception as e:
        logger.error("权重衰减失败: %s", e)
        return {"decayed": 0, "expired": 0, "error": str(e)}
    finally:
        conn.close()


# ── 数据清理 ──

def cleanup_expired_data() -> dict[str, int]:
    """清理过期数据（反馈 + 低置信度模式）。"""
    results = {}

    # 1. 清理过期反馈
    feedback_retention = FORGET_CONFIG["feedback_retention_days"]
    cutoff_date = (datetime.now() - timedelta(days=feedback_retention)).strftime("%Y-%m-%d %H:%M:%S")

    conn = get_conn()
    try:
        # 归档：先统计
        old_count = conn.execute(
            "SELECT COUNT(*) FROM user_feedback WHERE create_time < ?", (cutoff_date,)
        ).fetchone()[0]

        if old_count > 0:
            conn.execute(
                "DELETE FROM user_feedback WHERE create_time < ?", (cutoff_date,)
            )
            results["feedback_cleaned"] = old_count
            logger.info("清理过期反馈: %d 条", old_count)
        else:
            results["feedback_cleaned"] = 0

        # 2. 清理低置信度模式
        min_confidence = FORGET_CONFIG["pattern_min_confidence"]
        pattern_expire = FORGET_CONFIG["pattern_expire_days"]
        pattern_cutoff = (datetime.now() - timedelta(days=pattern_expire)).strftime("%Y-%m-%d %H:%M:%S")

        # 删除：低置信度 且 长期未使用
        patterns = conn.execute(
            "SELECT * FROM task_pattern WHERE confidence < ?", (min_confidence,)
        ).fetchall()

        pattern_cleaned = 0
        for p in patterns:
            last_use = p["last_use_time"] if p["last_use_time"] else ""
            if last_use:
                try:
                    last_dt = datetime.strptime(last_use, "%Y-%m-%d %H:%M:%S")
                    if (datetime.now() - last_dt).days > pattern_expire:
                        conn.execute("DELETE FROM task_pattern WHERE id = ?", (p["id"],))
                        pattern_cleaned += 1
                except (ValueError, TypeError):
                    continue

        results["patterns_cleaned"] = pattern_cleaned
        if pattern_cleaned > 0:
            logger.info("清理低置信度模式: %d 个", pattern_cleaned)

        # 3. 清理过期习惯（保留至少 1 天的）
        habit_expire = FORGET_CONFIG["habit_expire_days"]
        habit_cutoff = (datetime.now() - timedelta(days=habit_expire)).strftime("%Y-%m-%d %H:%M:%S")

        habits = conn.execute(
            "SELECT * FROM user_habit_weight WHERE weight < 0.5 AND last_use_time < ?",
            (habit_cutoff,)
        ).fetchall()

        habit_cleaned = 0
        for h in habits:
            conn.execute("DELETE FROM user_habit_weight WHERE habit_key = ?", (h["habit_key"],))
            habit_cleaned += 1

        results["habits_cleaned"] = habit_cleaned
        if habit_cleaned > 0:
            logger.info("清理过期习惯: %d 个", habit_cleaned)

        conn.commit()
        return results
    except Exception as e:
        logger.error("数据清理失败: %s", e)
        return {"error": str(e)}
    finally:
        conn.close()


# ── 时间窗口统计 ──

def get_windowed_stats(days: int = 90) -> dict[str, Any]:
    """滑动窗口统计（替代全量统计）。

    只统计最近 N 天的数据，避免历史数据干扰当前判断。
    """
    days = clamp_value(days, 1, 365)
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    conn = get_conn()
    try:
        # 窗口内任务统计
        total = conn.execute(
            "SELECT COUNT(*) FROM task_list WHERE create_time >= ?", (cutoff,)
        ).fetchone()[0]

        success = conn.execute(
            "SELECT COUNT(*) FROM task_list WHERE create_time >= ? AND status = 'success'",
            (cutoff,)
        ).fetchone()[0]

        avg_score = conn.execute(
            "SELECT AVG(work_score) FROM task_list WHERE create_time >= ? AND work_score > 0",
            (cutoff,)
        ).fetchone()[0]

        # 窗口内反馈统计
        feedback_total = conn.execute(
            "SELECT COUNT(*) FROM user_feedback WHERE create_time >= ?", (cutoff,)
        ).fetchone()[0]

        praise = conn.execute(
            "SELECT COUNT(*) FROM user_feedback WHERE create_time >= ? AND feedback_type = 'praise'",
            (cutoff,)
        ).fetchone()[0]

        return {
            "window_days": days,
            "task_total": total,
            "task_success": success,
            "success_rate": round(safe_divide(success, total) * 100, 1),
            "average_score": round(avg_score, 1) if avg_score else 0,
            "feedback_total": feedback_total,
            "satisfaction": round(safe_divide(praise, feedback_total), 3) if feedback_total else 0,
        }
    except Exception as e:
        logger.error("窗口统计失败: %s", e)
        return {}
    finally:
        conn.close()


# ── 一键执行 ──

def run_forgetting_cycle() -> dict[str, Any]:
    """执行完整的遗忘周期。

    应在低峰期定期调用（如每天凌晨）。
    """
    logger.info("═══ 开始遗忘周期 ═══")

    results = {
        "preferences": decay_preferences(),
        "weights": enhanced_weight_decay(),
        "cleanup": cleanup_expired_data(),
        "stats": get_windowed_stats(),
    }

    logger.info("═══ 遗忘周期完成 ═══")
    return results
