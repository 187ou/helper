"""完整记忆系统 API：情感 + 推理 + 叙事。"""
import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter()


# ── 情感记忆 ──

@router.get("/emotion/trend")
def emotion_trend(days: int = 7):
    """获取情绪趋势。"""
    from agent_core.emotional_memory import get_emotion_trend
    return get_emotion_trend(days)


@router.get("/emotion/alert")
def emotion_alert():
    """检查情绪预警。"""
    from agent_core.emotional_memory import check_emotion_alert
    alert = check_emotion_alert()
    return {"alert": alert, "has_alert": alert is not None}


@router.get("/emotion/guidance")
def emotion_guidance():
    """获取情绪适配建议。"""
    from agent_core.emotional_memory import get_emotional_guidance
    return {"guidance": get_emotional_guidance()}


# ── 主动推理 ──

@router.get("/predict")
def predict_needs(task_text: str = "", task_type: str = ""):
    """预测用户下一步需求。"""
    from agent_core.proactive_reasoning import predict_next_needs
    return {"predictions": predict_next_needs(task_text, task_type)}


@router.get("/proactive-suggestion")
def proactive_suggestion():
    """生成主动建议。"""
    from agent_core.proactive_reasoning import generate_proactive_suggestion
    suggestion = generate_proactive_suggestion()
    return {"suggestion": suggestion, "has_suggestion": suggestion is not None}


# ── 长期叙事 ──

@router.post("/narrative/generate")
def generate_narrative(body: dict = None):
    """生成生活叙事。"""
    period = (body or {}).get("period", "monthly")
    from agent_core.life_narrative import generate_life_narrative
    return generate_life_narrative(period=period)


@router.get("/narrative/latest")
def latest_narrative(period: str = "monthly"):
    """获取最新叙事。"""
    from agent_core.life_narrative import get_latest_narrative
    return get_latest_narrative(period)


@router.get("/narrative/story")
def story_so_far():
    """获取"你的故事"摘要。"""
    from agent_core.life_narrative import get_story_so_far
    return {"story": get_story_so_far()}
