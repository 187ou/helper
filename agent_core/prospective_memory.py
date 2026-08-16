"""前瞻记忆（Prospective Memory）：记住未来要做的事。

解决缺口：当前系统只能被动响应，无法主动记住用户的未来意图。

核心能力：
1. 承诺管理：用户说"记住下周三提醒我交周报" → 解析并存储
2. 时间触发：到指定时间 → 生成提醒
3. 事件触发：特定事件发生时 → 生成提醒
4. 条件触发：满足条件时 → 生成提醒
5. 周期性提醒：每天/每周/每月重复
"""
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


# ── 承诺解析 ──

def parse_and_store_intent(user_text: str) -> dict[str, Any] | None:
    """解析用户意图并存储到前瞻记忆（含重复检测）。

    支持的自然语言模式：
    - "记住下周三提醒我交周报" → 时间触发
    - "记得明天下午3点开会" → 时间触发
    - "每次收到发票时提醒我报销" → 事件触发
    - "连续3天没记账时提醒我" → 条件触发
    - "每天早上9点提醒我写日报" → 周期性时间触发

    Returns:
        解析结果，不符合前瞻意图时返回 None
    """
    intent = _detect_intent(user_text)
    if not intent:
        return None

    # 重复检测：检查是否有相似的待处理提醒
    if _is_duplicate_intent(intent):
        logger.info("前瞻记忆重复，跳过: %s", user_text[:30])
        return None

    # 存储到数据库
    memory_id = _store_intent(intent)
    intent["id"] = memory_id

    logger.info("前瞻记忆已存储: %s → %s (%s)", user_text[:30], intent["trigger_type"], intent["trigger_value"])
    return intent


def _is_duplicate_intent(intent: dict[str, Any]) -> bool:
    """检查是否有相似的待处理提醒（防止重复存储）。"""
    try:
        from memory_store.sqlite_db import get_conn

        trigger_value = intent.get("trigger_value", "")
        trigger_type = intent.get("trigger_type", "")

        conn = get_conn()
        try:
            # 检查相同触发类型+相似触发值的待处理提醒
            row = conn.execute(
                """SELECT COUNT(*) as cnt FROM prospective_memory
                   WHERE trigger_type = ? AND trigger_value = ? AND status = 'pending'""",
                (trigger_type, trigger_value),
            ).fetchone()

            return row["cnt"] > 0 if row else False
        finally:
            conn.close()
    except Exception:
        return False


def _detect_intent(text: str) -> dict[str, Any] | None:
    """检测用户输入是否包含前瞻意图并解析。"""
    text = text.strip()

    # 前瞻意图关键词
    INTENT_KEYWORDS = ["记住", "记得", "提醒", "别忘了", "不要忘记", "到时", "记得去", "记得要"]
    has_intent = any(kw in text for kw in INTENT_KEYWORDS)
    if not has_intent:
        return None

    # 尝试解析时间触发
    time_intent = _parse_time_trigger(text)
    if time_intent:
        return time_intent

    # 尝试解析事件触发
    event_intent = _parse_event_trigger(text)
    if event_intent:
        return event_intent

    # 尝试解析条件触发
    condition_intent = _parse_condition_trigger(text)
    if condition_intent:
        return condition_intent

    # 无法解析具体时间/事件，但有前瞻意图 → 存为通用提醒
    return {
        "trigger_type": "time",
        "trigger_value": text,
        "trigger_time": "",
        "priority": 1,
        "recurrence": "",
        "note": text,
    }


def _parse_time_trigger(text: str) -> dict[str, Any] | None:
    """解析时间触发的意图。"""
    now = datetime.now()

    # 模式：每天早上/下午/晚上 X 点
    daily_pattern = r'每天(早上|上午|中午|下午|晚上)?(\d{1,2})点'
    match = re.search(daily_pattern, text)
    if match:
        period = match.group(1) or ""
        hour = int(match.group(2))
        # 根据时段调整小时
        if period in ("下午", "晚上") and hour < 12:
            hour += 12
        trigger_time = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if trigger_time < now:
            trigger_time += timedelta(days=1)
        return {
            "trigger_type": "time",
            "trigger_value": f"每天 {period}{match.group(2)}点",
            "trigger_time": trigger_time.strftime("%Y-%m-%d %H:%M:%S"),
            "priority": 1,
            "recurrence": "daily",
            "note": text,
        }

    # 模式：每周X
    weekly_pattern = r'每(周|星期|礼拜)([一二三四五六日天])'
    match = re.search(weekly_pattern, text)
    if match:
        weekday_map = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
        target_weekday = weekday_map.get(match.group(2), 0)
        days_ahead = (target_weekday - now.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        trigger_time = now + timedelta(days=days_ahead)
        trigger_time = trigger_time.replace(hour=9, minute=0, second=0, microsecond=0)
        return {
            "trigger_type": "time",
            "trigger_value": f"每周{match.group(2)}",
            "trigger_time": trigger_time.strftime("%Y-%m-%d %H:%M:%S"),
            "priority": 1,
            "recurrence": "weekly",
            "note": text,
        }

    # 模式：下X（下周X、下个月X号）
    next_pattern = r'下(周|星期|礼拜)([一二三四五六日天])'
    match = re.search(next_pattern, text)
    if match:
        weekday_map = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
        target_weekday = weekday_map.get(match.group(2), 0)
        days_ahead = (target_weekday - now.weekday()) % 7 + 7  # 下周
        trigger_time = now + timedelta(days=days_ahead)
        trigger_time = trigger_time.replace(hour=9, minute=0, second=0, microsecond=0)
        return {
            "trigger_type": "time",
            "trigger_value": f"下{match.group(1)}{match.group(2)}",
            "trigger_time": trigger_time.strftime("%Y-%m-%d %H:%M:%S"),
            "priority": 1,
            "recurrence": "",
            "note": text,
        }

    # 模式：X月X号 / X月X日
    date_pattern = r'(\d{1,2})月(\d{1,2})[号日]'
    match = re.search(date_pattern, text)
    if match:
        month, day = int(match.group(1)), int(match.group(2))
        try:
            trigger_time = now.replace(month=month, day=day, hour=9, minute=0, second=0, microsecond=0)
            if trigger_time < now:
                trigger_time = trigger_time.replace(year=now.year + 1)
            return {
                "trigger_type": "time",
                "trigger_value": f"{month}月{day}日",
                "trigger_time": trigger_time.strftime("%Y-%m-%d %H:%M:%S"),
                "priority": 2,
                "recurrence": "",
                "note": text,
            }
        except ValueError:
            pass

    # 模式：明天/后天/大后天
    relative_pattern = r'(明天|后天|大后天)'
    match = re.search(relative_pattern, text)
    if match:
        day_map = {"明天": 1, "后天": 2, "大后天": 3}
        days = day_map.get(match.group(1), 1)
        trigger_time = now + timedelta(days=days)
        trigger_time = trigger_time.replace(hour=9, minute=0, second=0, microsecond=0)
        return {
            "trigger_type": "time",
            "trigger_value": match.group(1),
            "trigger_time": trigger_time.strftime("%Y-%m-%d %H:%M:%S"),
            "priority": 1,
            "recurrence": "",
            "note": text,
        }

    # 模式：X分钟后 / X小时后
    later_pattern = r'(\d+)\s*(分钟|小时)后'
    match = re.search(later_pattern, text)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        delta = timedelta(minutes=amount) if unit == "分钟" else timedelta(hours=amount)
        trigger_time = now + delta
        return {
            "trigger_type": "time",
            "trigger_value": f"{amount}{unit}后",
            "trigger_time": trigger_time.strftime("%Y-%m-%d %H:%M:%S"),
            "priority": 1,
            "recurrence": "",
            "note": text,
        }

    return None


def _parse_event_trigger(text: str) -> dict[str, Any] | None:
    """解析事件触发的意图。"""
    # 模式：每次收到/当...时/一...就...
    event_patterns = [
        (r'每次收到(.+?)(?:时|的时候)', '收到'),
        (r'当(.+?)(?:时|的时候)', '当'),
        (r'一(.+?)(?:就)', '一...就'),
        (r'(.+?)(?:之后|以后)提醒', '之后'),
    ]

    for pattern, trigger_prefix in event_patterns:
        match = re.search(pattern, text)
        if match:
            event_desc = match.group(1).strip()
            return {
                "trigger_type": "event",
                "trigger_value": f"{trigger_prefix}{event_desc}",
                "trigger_event": event_desc,
                "priority": 1,
                "recurrence": "event",
                "note": text,
            }

    return None


def _parse_condition_trigger(text: str) -> dict[str, Any] | None:
    """解析条件触发的意图。"""
    # 模式：连续X天没/超过X天
    condition_patterns = [
        (r'连续(\d+)天(没|没有)(.+?)(?:时|的时候)', '连续N天没做'),
        (r'超过(\d+)天(没|没有)(.+?)(?:时|的时候)', '超过N天没做'),
    ]

    for pattern, trigger_prefix in condition_patterns:
        match = re.search(pattern, text)
        if match:
            days = int(match.group(1))
            action = match.group(3).strip()
            return {
                "trigger_type": "condition",
                "trigger_value": f"{trigger_prefix}{action}",
                "trigger_condition": f"连续{days}天未{action}",
                "priority": 1,
                "recurrence": "condition",
                "note": text,
            }

    return None


# ── 数据库操作 ──

def _store_intent(intent: dict[str, Any]) -> int:
    """存储意图到数据库。"""
    from memory_store.sqlite_db import get_conn

    conn = get_conn()
    try:
        cursor = conn.execute(
            """INSERT INTO prospective_memory
               (user_intent, trigger_type, trigger_value, trigger_time, trigger_event,
                trigger_condition, priority, recurrence, note)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                intent.get("note", ""),
                intent.get("trigger_type", "time"),
                intent.get("trigger_value", ""),
                intent.get("trigger_time", ""),
                intent.get("trigger_event", ""),
                intent.get("trigger_condition", ""),
                intent.get("priority", 1),
                intent.get("recurrence", ""),
                intent.get("note", ""),
            ),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


# ── 触发检查 ──

def check_due_reminders(task_text: str = "") -> list[dict[str, Any]]:
    """检查所有到期的提醒（由定时调度器调用）。

    Args:
        task_text: 当前任务文本（用于事件触发检测）

    Returns:
        到期的提醒列表，按优先级排序。
    """
    due = []
    now = datetime.now()

    # 1. 时间触发
    time_due = _check_time_triggers(now)
    due.extend(time_due)

    # 2. 条件触发
    condition_due = _check_condition_triggers(now)
    due.extend(condition_due)

    # 3. 事件触发（当有新任务完成时检测）
    if task_text:
        event_due = _check_event_triggers(task_text, now)
        due.extend(event_due)

    # 去重
    seen_ids = set()
    unique_due = []
    for d in due:
        if d["id"] not in seen_ids:
            seen_ids.add(d["id"])
            unique_due.append(d)

    # 按优先级排序（高优先级在前）
    unique_due.sort(key=lambda x: x.get("priority", 1), reverse=True)

    return unique_due


def _check_event_triggers(task_text: str, now: datetime) -> list[dict[str, Any]]:
    """检查事件触发的提醒（当新任务完成时，检测是否有事件匹配）。

    例如：用户说"每次收到发票时提醒我报销"，当有新任务包含"发票"时触发。
    """
    due = []
    try:
        from memory_store.sqlite_db import get_conn

        conn = get_conn()
        try:
            rows = conn.execute(
                """SELECT * FROM prospective_memory
                   WHERE trigger_type = 'event'
                     AND status = 'pending'"""
            ).fetchall()
        finally:
            conn.close()

        task_lower = task_text.lower()
        for row in rows:
            event_keyword = row["trigger_event"].lower() if row["trigger_event"] else ""
            # 检查任务文本是否包含事件关键词
            if event_keyword and event_keyword in task_lower:
                due.append({
                    "id": row["id"],
                    "user_intent": row["user_intent"],
                    "trigger_type": "event",
                    "trigger_value": row["trigger_value"],
                    "priority": row["priority"],
                    "recurrence": row["recurrence"] if row["recurrence"] else "",
                    "note": row["note"] if row["note"] else "",
                })
                # 标记为已触发
                _mark_triggered(row["id"])

    except Exception as e:
        logger.debug("事件触发检测失败: %s", e)

    return due


def _check_time_triggers(now: datetime) -> list[dict[str, Any]]:
    """检查时间触发的提醒。"""
    from memory_store.sqlite_db import get_conn

    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT * FROM prospective_memory
               WHERE trigger_type = 'time'
                 AND status = 'pending'
                 AND trigger_time IS NOT NULL AND trigger_time != ''
                 AND trigger_time <= ?""",
            (now.strftime("%Y-%m-%d %H:%M:%S"),),
        ).fetchall()
    except Exception:
        return []
    finally:
        conn.close()

    due = []
    for row in rows:
        due.append({
            "id": row["id"],
            "user_intent": row["user_intent"],
            "trigger_type": row["trigger_type"],
            "trigger_value": row["trigger_value"],
            "priority": row["priority"],
            "recurrence": row["recurrence"],
            "note": row["note"],
        })

        # 处理周期性提醒
        if row["recurrence"] in ("daily", "weekly", "monthly"):
            _reschedule_recurring(row, now)
        else:
            # 一次性提醒 → 标记为已触发
            _mark_triggered(row["id"])

    return due


def _check_condition_triggers(now: datetime) -> list[dict[str, Any]]:
    """检查条件触发的提醒。"""
    due = []

    # 检查"连续 N 天未做 X"类型的条件
    conditions = _get_active_conditions()
    for cond in conditions:
        if _evaluate_condition(cond, now):
            due.append(cond)

    return due


def _get_active_conditions() -> list[dict[str, Any]]:
    """获取所有待处理的条件触发提醒。"""
    from memory_store.sqlite_db import get_conn

    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT * FROM prospective_memory
               WHERE trigger_type = 'condition'
                 AND status = 'pending'"""
        ).fetchall()
    except Exception:
        return []
    finally:
        conn.close()

    return [dict(r) for r in rows]


def _evaluate_condition(cond: dict, now: datetime) -> bool:
    """评估条件是否满足。"""
    condition = cond.get("trigger_condition", "")

    # 解析"连续 N 天未做 X"
    match = re.search(r'连续(\d+)天未(.+)', condition)
    if not match:
        return False

    days = int(match.group(1))
    action = match.group(2).strip()

    # 查询最近 N 天是否有该动作的记录
    return _check_no_recent_action(action, days, now)


def _check_no_recent_action(action: str, days: int, now: datetime) -> bool:
    """检查最近 N 天是否没有执行某动作。"""
    from memory_store.sqlite_db import get_conn

    cutoff = (now - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    try:
        # 在任务历史中查找
        row = conn.execute(
            """SELECT COUNT(*) as cnt FROM task_list
               WHERE (task_content LIKE ? OR tags LIKE ?)
                 AND create_time >= ?""",
            (f"%{action}%", f"%{action}%", cutoff),
        ).fetchone()
        return row["cnt"] == 0 if row else True
    except Exception:
        return False
    finally:
        conn.close()


def _reschedule_recurring(row: dict, now: datetime) -> None:
    """重新调度周期性提醒。"""
    from memory_store.sqlite_db import get_conn

    try:
        current_time = datetime.strptime(row["trigger_time"], "%Y-%m-%d %H:%M:%S")

        if row["recurrence"] == "daily":
            new_time = current_time + timedelta(days=1)
        elif row["recurrence"] == "weekly":
            new_time = current_time + timedelta(weeks=1)
        elif row["recurrence"] == "monthly":
            # 简单处理：加 30 天
            new_time = current_time + timedelta(days=30)
        else:
            new_time = None

        conn = get_conn()
        try:
            if new_time:
                conn.execute(
                    """UPDATE prospective_memory SET
                        trigger_time = ?,
                        last_triggered = ?,
                        trigger_count = trigger_count + 1
                       WHERE id = ?""",
                    (new_time.strftime("%Y-%m-%d %H:%M:%S"),
                     now.strftime("%Y-%m-%d %H:%M:%S"),
                     row["id"]),
                )
            else:
                _mark_triggered(row["id"])
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.warning("周期性提醒重调度失败: %s", e)


def _mark_triggered(memory_id: int) -> None:
    """标记提醒为已触发。"""
    from memory_store.sqlite_db import get_conn

    conn = get_conn()
    try:
        conn.execute(
            """UPDATE prospective_memory SET
                status = 'triggered',
                last_triggered = ?,
                trigger_count = trigger_count + 1
               WHERE id = ?""",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), memory_id),
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


# ── 管理操作 ──

def complete_reminder(memory_id: int) -> bool:
    """标记提醒为已完成。"""
    from memory_store.sqlite_db import get_conn

    conn = get_conn()
    try:
        conn.execute(
            "UPDATE prospective_memory SET status = 'completed' WHERE id = ?",
            (memory_id,),
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def dismiss_reminder(memory_id: int) -> bool:
    """Dismiss 提醒（用户不想要了）。"""
    from memory_store.sqlite_db import get_conn

    conn = get_conn()
    try:
        conn.execute(
            "UPDATE prospective_memory SET status = 'dismissed' WHERE id = ?",
            (memory_id,),
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def list_reminders(status: str = "pending", limit: int = 20) -> list[dict[str, Any]]:
    """列出提醒。"""
    from memory_store.sqlite_db import get_conn

    conn = get_conn()
    try:
        if status == "all":
            rows = conn.execute(
                "SELECT * FROM prospective_memory ORDER BY priority DESC, created_time DESC LIMIT ?",
                (limit,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM prospective_memory WHERE status = ?
                   ORDER BY priority DESC, created_time DESC LIMIT ?""",
                (status, limit),
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()


def delete_reminder(memory_id: int) -> bool:
    """删除提醒。"""
    from memory_store.sqlite_db import get_conn

    conn = get_conn()
    try:
        conn.execute("DELETE FROM prospective_memory WHERE id = ?", (memory_id,))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()
