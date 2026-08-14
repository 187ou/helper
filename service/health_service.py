"""健康服务：久坐、喝水、作息、睡眠（骨架）。"""
import logging
from typing import Any

logger = logging.getLogger(__name__)


def get_health_reminders() -> list[dict[str, Any]]:
    """获取健康提醒列表。"""
    return [
        {"type": "sedentary", "title": "久坐提醒", "interval_min": 60, "enabled": True},
        {"type": "drink_water", "title": "喝水提醒", "interval_min": 45, "enabled": True},
        {"type": "sleep", "title": "作息提醒", "interval_min": 0, "enabled": True},
    ]


def record_sleep(bed_time: str, wake_time: str) -> dict[str, Any]:
    """记录睡眠。"""
    logger.info("睡眠记录: %s - %s", bed_time, wake_time)
    return {"bed_time": bed_time, "wake_time": wake_time, "duration_hours": 0}


def get_sedentary_status() -> dict[str, Any]:
    return {"sitting_minutes": 0, "need_break": False}
