"""对话 API。"""
import logging
from fastapi import APIRouter

from agent_core.task_scheduler import run as run_task
from config.settings import is_llm_configured

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/configured")
def check_configured():
    return {"configured": is_llm_configured()}


@router.post("/send")
def send_message(body: dict):
    text = (body.get("text") or "").strip()
    if not text:
        return {"ok": False, "error": "empty"}
    if not is_llm_configured():
        return {"ok": False, "error": "llm_not_configured"}

    result = run_task(text)
    return {"ok": True, **result}
