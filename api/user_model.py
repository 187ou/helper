"""用户模型 API：构建 + 查询 + 个性化指导。"""
import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/build")
def build_model():
    """构建/更新用户模型。"""
    from agent_core.user_model import build_user_model
    model = build_user_model()
    return {"ok": True, **model}


@router.get("/latest")
def get_latest():
    """获取最新用户模型。"""
    from agent_core.user_model import get_user_model
    return get_user_model()


@router.get("/guidance")
def get_guidance(task_type: str = ""):
    """获取个性化指导（供 prompt 注入）。"""
    from agent_core.user_model import get_personalized_guidance
    return {"guidance": get_personalized_guidance(task_type)}


# ── 关联记忆 API ──

@router.get("/memory/related")
def get_related(memory_type: str, memory_key: str, max_depth: int = 2):
    """获取关联记忆。"""
    from agent_core.memory_graph import get_related_memories
    return {"related": get_related_memories(memory_type, memory_key, max_depth)}


# ── 深度反思 API ──

@router.post("/reflection/deep")
def deep_reflect(body: dict = None):
    """生成深度反思。"""
    period = (body or {}).get("period", "weekly")
    from agent_core.deep_reflection import generate_deep_reflection
    return generate_deep_reflection(period=period)


@router.get("/reflection/latest")
def latest_reflection(period: str = "weekly"):
    """获取最新深度反思。"""
    from agent_core.deep_reflection import get_latest_deep_reflection
    return get_latest_deep_reflection(period)
