"""进化中心 API。"""
from fastapi import APIRouter

from evolution_core.evo_log import get_stats, list_logs
from evolution_core.weight_evolve import get_top_habits

router = APIRouter()


@router.get("/stats")
def stats():
    return get_stats()


@router.get("/logs")
def logs(evo_type: str = ""):
    return list_logs(evo_type=evo_type or "")


@router.get("/weights")
def weights(limit: int = 10):
    return get_top_habits(limit)
