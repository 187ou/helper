"""元记忆 API：记忆系统的自我监控和可靠性展示。"""
import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
def system_health():
    """记忆系统健康状态（整体概览）。"""
    from agent_core.metamemory import get_system_health
    return get_system_health()


@router.get("/memories")
def list_memories(memory_type: str = "", limit: int = 20):
    """获取记忆列表（含可靠性信息）。"""
    from agent_core.metamemory import get_memory_with_reliability
    return {"memories": get_memory_with_reliability(memory_type, limit)}


@router.get("/reliability")
def get_reliability(memory_type: str, memory_key: str):
    """获取某条记忆的可靠性信息。"""
    from agent_core.metamemory import get_memory_reliability
    result = get_memory_reliability(memory_type, memory_key)
    if result is None:
        return {"found": False, "message": "未找到该记忆的元数据"}
    return {"found": True, **result}


@router.get("/conflicts")
def list_conflicts():
    """列出所有记忆冲突。"""
    from agent_core.metamemory import check_conflicts
    return {"conflicts": check_conflicts()}


@router.post("/sync")
def sync_metamemory():
    """同步元记忆（从实际记忆表同步状态）。"""
    from agent_core.metamemory import sync_metamemory
    return sync_metamemory()
