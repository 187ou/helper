"""行为采集 API（2.1）。"""
import logging
from fastapi import APIRouter, HTTPException

from service.behavior_service import log_event, list_events, get_statistics, clear_all
from service.evolution_config_service import is_tracking_enabled

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/log")
def log(body: dict):
    """记录行为事件。"""
    event_type = body.get("event_type", "")
    event_data = body.get("event_data", {})

    if not is_tracking_enabled():
        return {"ok": False, "reason": "tracking_disabled"}

    log_id = log_event(event_type, event_data)
    return {"ok": True, "id": log_id}


@router.get("/list")
def list_(event_type: str = "", limit: int = 100):
    """查询行为日志。"""
    return list_events(event_type=event_type, limit=limit)


@router.get("/stats")
def stats():
    """行为统计。"""
    return get_statistics()


@router.delete("/clear")
def clear():
    """清空行为数据。"""
    count = clear_all()
    return {"ok": True, "cleared": count}
