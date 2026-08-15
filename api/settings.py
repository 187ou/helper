"""设置 API。"""
import logging
from fastapi import APIRouter

from config.settings import load_config, set, get, get_run_mode, set_run_mode
from agent_core.llm_client import reset_client

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
def get_settings():
    cfg = load_config()
    return {
        "base_url": cfg.llm.base_url,
        "api_key": cfg.llm.api_key,
        "model_name": cfg.llm.model_name,
        "run_mode": get_run_mode(),
    }


@router.post("/")
def save_settings(body: dict):
    url = (body.get("base_url") or "").strip()
    key = (body.get("api_key") or "").strip()
    model = (body.get("model_name") or "").strip()
    if not all([url, key, model]):
        return {"ok": False, "error": "incomplete"}

    set("llm.base_url", url)
    set("llm.api_key", key)
    set("llm.model_name", model)
    reset_client()
    return {"ok": True}


@router.post("/test")
def test_connection(body: dict):
    url = (body.get("base_url") or "").strip()
    key = (body.get("api_key") or "").strip()
    model = (body.get("model_name") or "").strip()
    if not all([url, key, model]):
        return {"ok": False, "error": "incomplete"}

    try:
        from openai import OpenAI
        c = OpenAI(base_url=url, api_key=key, timeout=12, max_retries=0)
        r = c.chat.completions.create(
            model=model, messages=[{"role": "user", "content": "hi"}], max_tokens=5
        )
        return {"ok": True, "message": (r.choices[0].message.content or "")[:50]}
    except Exception as e:
        return {"ok": False, "error": str(e)[:100]}
