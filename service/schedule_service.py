"""定时任务服务：日程 CRUD + 定时推送（健康提醒/归档/汇总）。"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any

from memory_store.sqlite_db import get_conn, now_str
from config.app_const import ScheduleCategory, ScheduleStatus
from config.path_config import USER_DATA_DIR

logger = logging.getLogger(__name__)

# ── 提醒配置默认值 ──
_DEFAULT_REMINDERS = {
    "sedentary": {"enabled": True, "interval_min": 60, "last_remind": ""},
    "drink_water": {"enabled": True, "interval_min": 45, "last_remind": ""},
}

_reminder_state: dict[str, Any] = {}


def _load_reminders() -> dict:
    """加载提醒状态。"""
    global _reminder_state
    if not _reminder_state:
        path = USER_DATA_DIR / "reminders.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                _reminder_state = json.load(f)
        else:
            _reminder_state = dict(_DEFAULT_REMINDERS)
    return _reminder_state


def _save_reminders() -> None:
    path = USER_DATA_DIR / "reminders.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_reminder_state, f, ensure_ascii=False, indent=2)


# ── 日程 CRUD ──
def get_today_schedule() -> list[dict[str, Any]]:
    """获取今日日程。"""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    rows = conn.execute(
        """SELECT * FROM daily_schedule WHERE schedule_date = ?
           ORDER BY schedule_time ASC, priority DESC""",
        (today,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_week_schedule() -> list[dict[str, Any]]:
    """获取本周日程。"""
    today = datetime.now()
    start = today.strftime("%Y-%m-%d")
    end = (today + timedelta(days=7)).strftime("%Y-%m-%d")
    conn = get_conn()
    rows = conn.execute(
        """SELECT * FROM daily_schedule WHERE schedule_date BETWEEN ? AND ?
           ORDER BY schedule_date ASC, schedule_time ASC""",
        (start, end),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_schedule(
    title: str,
    schedule_date: str = "",
    schedule_time: str = "",
    category: str = "work",
    priority: int = 0,
    note: str = "",
) -> dict[str, Any]:
    """添加日程。"""
    if not schedule_date:
        schedule_date = datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    cursor = conn.execute(
        """INSERT INTO daily_schedule (title, schedule_date, schedule_time, category, priority, status, note)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (title, schedule_date, schedule_time, category, priority, ScheduleStatus.PENDING.value, note),
    )
    conn.commit()
    sid = cursor.lastrowid
    conn.close()
    logger.info("添加日程: %s %s %s", schedule_date, schedule_time, title)
    return {"id": sid, "title": title, "date": schedule_date, "time": schedule_time, "status": "pending"}


def complete_schedule(schedule_id: int) -> bool:
    """标记日程完成。"""
    conn = get_conn()
    conn.execute(
        "UPDATE daily_schedule SET status = ? WHERE id = ?",
        (ScheduleStatus.DONE.value, schedule_id),
    )
    conn.commit()
    conn.close()
    return True


def delete_schedule(schedule_id: int) -> bool:
    """删除日程。"""
    conn = get_conn()
    conn.execute("DELETE FROM daily_schedule WHERE id = ?", (schedule_id,))
    conn.commit()
    conn.close()
    return True


# ── 健康提醒 ──
def check_reminders() -> list[dict[str, Any]]:
    """检查哪些提醒需要触发。"""
    reminders = _load_reminders()
    now = datetime.now()
    due = []

    for name, cfg in reminders.items():
        if not cfg.get("enabled", False):
            continue
        interval = cfg.get("interval_min", 60)
        last = cfg.get("last_remind", "")

        if not last:
            due.append({"name": name, "title": _reminder_title(name)})
            continue

        try:
            last_time = datetime.strptime(last, "%Y-%m-%d %H:%M:%S")
            if (now - last_time).total_seconds() >= interval * 60:
                due.append({"name": name, "title": _reminder_title(name)})
        except ValueError:
            due.append({"name": name, "title": _reminder_title(name)})

    return due


def ack_reminder(name: str) -> None:
    """确认提醒（更新最后提醒时间）。"""
    reminders = _load_reminders()
    if name in reminders:
        reminders[name]["last_remind"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _save_reminders()


def _reminder_title(name: str) -> str:
    titles = {
        "sedentary": "⏰ 久坐提醒：该起来活动一下了！",
        "drink_water": "💧 喝水提醒：记得补充水分！",
    }
    return titles.get(name, "提醒")


# ── 归档与汇总 ──
def daily_archive() -> dict[str, Any]:
    """每日归档统计。"""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) FROM daily_schedule WHERE schedule_date = ?", (today,)).fetchone()[0]
    done = conn.execute(
        "SELECT COUNT(*) FROM daily_schedule WHERE schedule_date = ? AND status = ?",
        (today, ScheduleStatus.DONE.value),
    ).fetchone()[0]
    conn.close()
    return {"date": today, "total": total, "completed": done}


def monthly_summary(month: str = "") -> dict[str, Any]:
    """月度日程汇总。"""
    if not month:
        month = datetime.now().strftime("%Y-%m")
    conn = get_conn()
    total = conn.execute(
        "SELECT COUNT(*) FROM daily_schedule WHERE schedule_date LIKE ?", (f"{month}%",)
    ).fetchone()[0]
    done = conn.execute(
        "SELECT COUNT(*) FROM daily_schedule WHERE schedule_date LIKE ? AND status = ?",
        (f"{month}%", ScheduleStatus.DONE.value),
    ).fetchone()[0]
    conn.close()
    return {"month": month, "total": total, "completed": done}
