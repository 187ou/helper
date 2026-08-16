"""反思与抽象 API：生成反思报告 + 获取洞察 + 历史。"""
import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/generate")
def generate_report(body: dict = None):
    """生成反思报告。

    请求体（可选）: {"period": "weekly" | "monthly"}
    """
    period = (body or {}).get("period", "weekly")
    if period not in ("weekly", "monthly"):
        period = "weekly"

    from agent_core.reflection import generate_reflection_report
    report = generate_reflection_report(period=period)
    return {"ok": True, **report}


@router.get("/latest")
def get_latest(period: str = "weekly"):
    """获取最新反思报告。"""
    from agent_core.reflection import get_latest_reflection
    return get_latest_reflection(period=period)


@router.get("/insights")
def get_insights():
    """获取最新洞察（快捷入口）。"""
    from agent_core.memory_consolidation import get_latest_insights
    return {"insights": get_latest_insights()}
