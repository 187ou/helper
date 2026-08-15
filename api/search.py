"""全文检索 API。"""
import logging

from fastapi import APIRouter

from service.search_service import global_search

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
def search(q: str = "", limit: int = 5):
    """全局检索。"""
    if not q.strip():
        return {"tasks": [], "schedules": [], "bills": [], "logs": []}
    return global_search(q, limit_per_type=limit)


# 兼容无斜杠访问
@router.get("")
def search_no_slash(q: str = "", limit: int = 5):
    """全局检索（兼容无斜杠）。"""
    if not q.strip():
        return {"tasks": [], "schedules": [], "bills": [], "logs": []}
    return global_search(q, limit_per_type=limit)
