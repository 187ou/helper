"""LLM 客户端：封装 OpenAI 兼容 API 调用，支持联网/离线双模式。"""
import json
import logging
import re
from typing import Any

from config.settings import (
    get_api_base_url,
    get_api_key,
    get_model_name,
    get_run_mode,
    is_llm_configured,
)
from config.app_const import RunMode

logger = logging.getLogger(__name__)

# 全局客户端缓存
_client = None


def get_client():
    """获取/初始化 OpenAI 客户端。"""
    global _client
    if _client is None:
        _client = _create_client()
    return _client


def _create_client():
    """创建新的 OpenAI 客户端实例。"""
    try:
        from openai import OpenAI
        client = OpenAI(
            base_url=get_api_base_url(),
            api_key=get_api_key(),
            timeout=60.0,          # 单次请求 60 秒超时
            max_retries=2,         # 失败自动重试 2 次
        )
        logger.info("LLM 客户端初始化: %s", get_api_base_url())
        return client
    except Exception as e:
        logger.error("LLM 客户端初始化失败: %s", e)
        return None


def reset_client():
    """重置客户端（配置变更后调用）。"""
    global _client
    _client = None
    logger.info("LLM 客户端已重置")


def chat(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    response_format: dict | None = None,
) -> str:
    """调用 LLM 聊天接口，返回文本。

    Args:
        messages: OpenAI 格式消息列表 [{"role":"user","content":"..."}]
        model: 模型名，None 则用配置默认
        temperature: 温度
        max_tokens: 最大 token
        response_format: 如 {"type": "json_object"} 强制 JSON 输出
    """
    if get_run_mode() == RunMode.OFFLINE:
        return _offline_reply(messages)

    if not is_llm_configured():
        logger.warning("LLM 未配置，使用离线模拟")
        return _offline_reply(messages)

    client = get_client()
    if client is None:
        return _offline_reply(messages)

    try:
        kwargs: dict[str, Any] = {
            "model": model or get_model_name(),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format

        resp = client.chat.completions.create(**kwargs)
        content = resp.choices[0].message.content or ""
        logger.info("LLM 响应: %d chars", len(content))
        return content
    except Exception as e:
        logger.error("LLM 调用失败: %s", e)
        return f"[LLM 调用失败: {e}]"


def chat_json(messages: list[dict[str, str]], **kwargs) -> dict:
    """调用 LLM 并解析 JSON 响应（空响应自动重试一次）。

    注意：不使用 response_format={"type": "json_object"}，因为第三方代理
    （如 api.longcat.chat）可能不支持，导致返回空内容。
    改为依赖 prompt 约束 + 容错解析。
    """
    for attempt in range(2):
        text = chat(messages, **kwargs)
        text = text.strip()
        # 去除可能的 markdown 代码块
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                # 尝试从文本中提取 JSON 片段（应对截断或多余内容）
                match = re.search(r'\{.*\}', text, re.DOTALL)
                if match:
                    try:
                        return json.loads(match.group())
                    except json.JSONDecodeError:
                        pass
                logger.warning("LLM 返回非 JSON: %s", text[:200])
                return {"raw": text}
        logger.warning("LLM 返回空响应，重试 %d", attempt + 1)
    return {}


def _offline_reply(messages: list[dict[str, str]]) -> str:
    """离线模式回复（模拟）。"""
    user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    return (
        f"[离线模拟模式] 收到指令: {user_msg[:80]}...\n"
        "（当前为离线模式或 LLM 未配置，联网后将获得真实 AI 响应）"
    )
