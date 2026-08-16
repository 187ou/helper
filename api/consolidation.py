"""记忆巩固 API：触发巩固 + 查看洞察 + 巩固历史。"""
import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/run")
def run_consolidation(body: dict = None):
    """手动触发记忆巩固（通常由定时调度器自动调用）。

    请求体（可选）: {"days": 1}
    """
    days = (body or {}).get("days", 1)
    from agent_core.memory_consolidation import run_consolidation
    result = run_consolidation(days=days)
    return {"ok": True, **result}


@router.get("/insights")
def get_insights():
    """获取最新洞察。"""
    from agent_core.memory_consolidation import get_latest_insights
    return {"insights": get_latest_insights()}


@router.get("/history")
def get_history(limit: int = 10):
    """获取巩固历史。"""
    from agent_core.memory_consolidation import get_consolidation_history
    return {"history": get_consolidation_history(limit=limit)}
