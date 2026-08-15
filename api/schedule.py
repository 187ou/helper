"""看板/日程 API。"""
import logging
from fastapi import APIRouter

from service.schedule_service import (
    get_today_schedule, add_schedule, complete_schedule,
    delete_schedule, get_week_schedule, daily_archive, monthly_summary,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/today")
def today():
    return get_today_schedule()


@router.get("/week")
def week():
    return get_week_schedule()


@router.post("/add")
def add(body: dict):
    title = (body.get("title") or "").strip()
    if not title:
        return {"ok": False, "error": "empty"}
    category = body.get("category", "work")
    schedule_time = body.get("schedule_time", "")
    result = add_schedule(title, schedule_time=schedule_time, category=category)
    return {"ok": True, **result}


@router.post("/complete")
def complete(body: dict):
    sid = body.get("id")
    if sid is None:
        return {"ok": False, "error": "no_id"}
    complete_schedule(sid)
    return {"ok": True}


@router.delete("/{sid}")
def delete(sid: int):
    delete_schedule(sid)
    return {"ok": True}


@router.get("/archive")
def archive():
    return daily_archive()


@router.get("/summary")
def summary(month: str = ""):
    return monthly_summary(month)
