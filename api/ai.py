"""本地 AI 能力 API：模式切换、文本处理、连接测试。"""
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from agent_core.llm_client import chat
from config.settings import get_run_mode, set_run_mode, get

logger = logging.getLogger(__name__)
router = APIRouter()


# ═══════════════════════════════════════════
# 6.1 AI 模式管理
# ═══════════════════════════════════════════

@router.get("/mode")
def get_mode():
    """获取当前 AI 模式。"""
    mode = get_run_mode()
    return {
        "mode": mode,
        "configured": bool(get("llm.api_key") and get("llm.base_url")),
        "model": get("llm.model_name", ""),
        "base_url": get("llm.base_url", ""),
    }


@router.post("/mode")
def switch_mode(body: dict):
    """切换 AI 模式（online / offline）。"""
    mode = body.get("mode", "")
    if mode not in ("online", "offline"):
        raise HTTPException(status_code=400, detail="无效模式，可选: online / offline")

    set_run_mode(mode)

    # 切换模式后重置 LLM 客户端
    from agent_core.llm_client import reset_client
    reset_client()

    return {"ok": True, "mode": mode}


@router.post("/test")
def test_connection(body: dict):
    """测试 LLM 连接（支持 Ollama 和在线 API）。"""
    base_url = (body.get("base_url") or get("llm.base_url", "")).strip()
    api_key = (body.get("api_key") or get("llm.api_key", "")).strip()
    model = (body.get("model_name") or get("llm.model_name", "")).strip()

    if not base_url:
        return {"ok": False, "error": "请提供 Base URL"}

    try:
        from openai import OpenAI
        client = OpenAI(
            base_url=base_url,
            api_key=api_key or "ollama",  # Ollama 不需要真实 key
            timeout=15.0,
            max_retries=0,
        )
        resp = client.chat.completions.create(
            model=model or "llama3.2",
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=5,
        )
        content = (resp.choices[0].message.content or "").strip()
        return {"ok": True, "message": content[:50] or "连接成功"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


@router.post("/test/ollama")
def test_ollama(body: dict):
    """专门测试 Ollama 本地连接。"""
    base_url = (body.get("base_url") or "http://localhost:11434/v1").strip()
    model = (body.get("model_name") or "").strip()

    try:
        from openai import OpenAI
        client = OpenAI(base_url=base_url, api_key="ollama", timeout=10.0, max_retries=0)

        # 获取可用模型列表
        try:
            models = client.models.list()
            available = [m.id for m in models.data][:10]
        except Exception:
            available = []

        # 测试推理
        test_model = model or (available[0] if available else "llama3.2")
        resp = client.chat.completions.create(
            model=test_model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=5,
        )
        content = (resp.choices[0].message.content or "").strip()

        return {
            "ok": True,
            "message": content[:50] or "连接成功",
            "available_models": available,
            "current_model": test_model,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


# ═══════════════════════════════════════════
# 6.3 文本智能处理
# ═══════════════════════════════════════════

@router.post("/text/rewrite")
def text_rewrite(body: dict):
    """文本改写。"""
    text = body.get("text", "")
    style = body.get("style", "正式")
    if not text.strip():
        raise HTTPException(status_code=400, detail="请提供文本")

    prompt = f"""请将以下文本改写为{style}风格：

原文：
{text}

要求：
1. 保持原意不变
2. 语言流畅自然
3. 只输出改写后的文本，不要解释"""

    result = chat([
        {"role": "system", "content": "你是一位专业的文本改写专家。"},
        {"role": "user", "content": prompt},
    ], temperature=0.5, max_tokens=2000)

    return {"result": result, "style": style, "original_length": len(text)}


@router.post("/text/summarize")
def text_summarize(body: dict):
    """文本精简/摘要。"""
    text = body.get("text", "")
    max_length = body.get("max_length", 200)
    if not text.strip():
        raise HTTPException(status_code=400, detail="请提供文本")

    prompt = f"""请将以下文本精简为 {max_length} 字以内的摘要：

原文：
{text}

要求：
1. 保留核心信息和关键数据
2. 语言简洁有力
3. 不要空泛概括"""

    result = chat([
        {"role": "system", "content": "你是一位专业的文本精简专家。"},
        {"role": "user", "content": prompt},
    ], temperature=0.4, max_tokens=1000)

    return {"result": result, "max_length": max_length}


@router.post("/text/expand")
def text_expand(body: dict):
    """文本扩写。"""
    text = body.get("text", "")
    target_length = body.get("target_length", 500)
    if not text.strip():
        raise HTTPException(status_code=400, detail="请提供文本")

    prompt = f"""请将以下文本扩写到约 {target_length} 字：

原文：
{text}

要求：
1. 保持原意和风格
2. 补充合理细节和论据
3. 不要偏离主题"""

    result = chat([
        {"role": "system", "content": "你是一位专业的文本扩写专家。"},
        {"role": "user", "content": prompt},
    ], temperature=0.6, max_tokens=2000)

    return {"result": result, "target_length": target_length}


@router.post("/text/format")
def text_format(body: dict):
    """文本格式规整。"""
    text = body.get("text", "")
    if not text.strip():
        raise HTTPException(status_code=400, detail="请提供文本")

    prompt = f"""请对以下文本进行格式规整：

原文：
{text}

要求：
1. 清理冗余文字和重复内容
2. 统一段落格式
3. 修正标点符号
4. 保持原意不变
5. 输出 Markdown 格式"""

    result = chat([
        {"role": "system", "content": "你是一位专业的文本编辑专家。"},
        {"role": "user", "content": prompt},
    ], temperature=0.3, max_tokens=2000)

    return {"result": result}


@router.post("/text/polish")
def text_polish(body: dict):
    """文本润色（综合处理）。"""
    text = body.get("text", "")
    goals = body.get("goals", ["精简", "规范"])
    if not text.strip():
        raise HTTPException(status_code=400, detail="请提供文本")

    goals_text = "、".join(goals)
    prompt = f"""请对以下文本进行润色处理：

原文：
{text}

处理目标：{goals_text}

要求：
1. 根据目标灵活处理
2. 保持原意和风格
3. 输出高质量文本"""

    result = chat([
        {"role": "system", "content": "你是一位专业的文本润色专家。"},
        {"role": "user", "content": prompt},
    ], temperature=0.5, max_tokens=2000)

    return {"result": result, "goals": goals}
