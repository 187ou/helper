"""健康服务：久坐、喝水、作息、睡眠（真实可用）。"""
import logging
from datetime import datetime, timedelta
from typing import Any

from memory_store.sqlite_db import get_conn, now_str
from config.path_config import USER_DATA_DIR

logger = logging.getLogger(__name__)


def get_health_reminders() -> list[dict[str, Any]]:
    """获取健康提醒配置。"""
    from service.schedule_service import _load_reminders
    reminders = _load_reminders()
    result = []
    for name, cfg in reminders.items():
        result.append({
            "type": name,
            "title": _reminder_title(name),
            "interval_min": cfg.get("interval_min", 60),
            "enabled": cfg.get("enabled", True),
            "last_remind": cfg.get("last_remind", ""),
        })
    return result


def _reminder_title(name: str) -> str:
    titles = {
        "sedentary": "⏰ 久坐提醒",
        "drink_water": "💧 喝水提醒",
        "sleep": "🌙 作息提醒",
    }
    return titles.get(name, "健康提醒")


def record_sleep(bed_time: str, wake_time: str) -> dict[str, Any]:
    """记录睡眠，自动计算时长。

    Args:
        bed_time: 入睡时间 "HH:MM" 或 "YYYY-MM-DD HH:MM"
        wake_time: 起床时间 "HH:MM" 或 "YYYY-MM-DD HH:MM"

    Returns:
        包含睡眠时长（小时）和质量的字典
    """
    try:
        # 解析时间
        now = datetime.now()
        if len(bed_time) <= 5:  # "HH:MM" 格式
            bed_dt = datetime.strptime(f"{now.strftime('%Y-%m-%d')} {bed_time}", "%Y-%m-%d %H:%M")
            wake_dt = datetime.strptime(f"{now.strftime('%Y-%m-%d')} {wake_time}", "%Y-%m-%d %H:%M")
            # 如果起床时间 < 入睡时间，说明是次日
            if wake_dt < bed_dt:
                wake_dt += timedelta(days=1)
        else:
            bed_dt = datetime.strptime(bed_time, "%Y-%m-%d %H:%M")
            wake_dt = datetime.strptime(wake_time, "%Y-%m-%d %H:%M")

        duration = (wake_dt - bed_dt).total_seconds() / 3600
        if duration <= 0 or duration > 24:
            return {"bed_time": bed_time, "wake_time": wake_time, "duration_hours": 0, "quality": "invalid"}

        # 睡眠质量评估
        if duration < 5:
            quality = "不足"
        elif duration < 6:
            quality = "偏少"
        elif duration <= 9:
            quality = "正常"
        else:
            quality = "偏多"

        # 写入数据库
        conn = get_conn()
        cursor = conn.execute(
            "INSERT INTO health_record (record_type, value, note, record_date) VALUES (?, ?, ?, ?)",
            ("sleep", round(duration, 1), f"入睡 {bed_time} 起床 {wake_time}", wake_dt.strftime("%Y-%m-%d")),
        )
        conn.commit()
        rid = cursor.lastrowid
        conn.close()

        logger.info("睡眠记录: %.1f小时 (%s)", duration, quality)
        return {
            "id": rid,
            "bed_time": bed_time,
            "wake_time": wake_time,
            "duration_hours": round(duration, 1),
            "quality": quality,
        }
    except ValueError as e:
        logger.error("睡眠记录时间格式错误: %s", e)
        return {"bed_time": bed_time, "wake_time": wake_time, "duration_hours": 0, "quality": "format_error", "error": str(e)}


def get_sedentary_status() -> dict[str, Any]:
    """获取久坐状态（基于最近活动时间估算）。"""
    conn = get_conn()
    # 查找最近一条行为记录
    last_activity = conn.execute(
        "SELECT create_time FROM behavior_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()

    if not last_activity:
        return {"sitting_minutes": 0, "need_break": False, "last_activity": None}

    last_time = datetime.strptime(last_activity["create_time"], "%Y-%m-%d %H:%M:%S")
    sitting_minutes = int((datetime.now() - last_time).total_seconds() / 60)
    need_break = sitting_minutes >= 60  # 60 分钟需要休息

    return {
        "sitting_minutes": sitting_minutes,
        "need_break": need_break,
        "last_activity": last_activity["create_time"],
        "threshold_minutes": 60,
    }


def record_health_metric(record_type: str, value: float, note: str = "", record_date: str = "") -> dict[str, Any]:
    """记录健康指标（通用）。

    Args:
        record_type: 类型 (sleep/water/exercise/weight/sedentary)
        value: 数值（睡眠小时、喝水杯数、运动分钟、体重kg）
        note: 备注
        record_date: 日期（默认今天）
    """
    valid_types = {"sleep", "water", "exercise", "weight", "sedentary"}
    if record_type not in valid_types:
        return {"ok": False, "error": f"无效类型: {record_type}"}

    if not record_date:
        record_date = datetime.now().strftime("%Y-%m-%d")

    conn = get_conn()
    cursor = conn.execute(
        "INSERT INTO health_record (record_type, value, note, record_date) VALUES (?, ?, ?, ?)",
        (record_type, value, note, record_date),
    )
    conn.commit()
    rid = cursor.lastrowid
    conn.close()

    logger.info("健康记录: %s = %.1f (%s)", record_type, value, record_date)
    return {"id": rid, "type": record_type, "value": value, "date": record_date, "ok": True}


def get_health_summary(days: int = 7) -> dict[str, Any]:
    """获取近 N 天的健康汇总。"""
    conn = get_conn()
    today = datetime.now().strftime("%Y-%m-%d")

    # 今日数据
    today_sleep = conn.execute(
        "SELECT value FROM health_record WHERE record_type='sleep' AND record_date=?", (today,)
    ).fetchone()
    today_water = conn.execute(
        "SELECT COALESCE(SUM(value),0) FROM health_record WHERE record_type='water' AND record_date=?", (today,)
    ).fetchone()[0]
    today_exercise = conn.execute(
        "SELECT COALESCE(SUM(value),0) FROM health_record WHERE record_type='exercise' AND record_date=?", (today,)
    ).fetchone()[0]

    # 近 N 天平均
    avg_sleep = conn.execute(
        "SELECT AVG(value) FROM health_record WHERE record_type='sleep' AND record_date >= date('now', ?)",
        (f"-{days} days",)
    ).fetchone()[0]
    avg_exercise = conn.execute(
        "SELECT AVG(value) FROM health_record WHERE record_type='exercise' AND record_date >= date('now', ?)",
        (f"-{days} days",)
    ).fetchone()[0]

    conn.close()
    return {
        "today": {
            "sleep": today_sleep["value"] if today_sleep else 0,
            "water": today_water,
            "exercise": today_exercise,
        },
        "avg_sleep_7d": round(avg_sleep, 1) if avg_sleep else 0,
        "avg_exercise_7d": round(avg_exercise, 1) if avg_exercise else 0,
        "days": days,
    }
