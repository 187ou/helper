"""结果校验与纠错重试。

检查节点输出是否合法，不合法时调用 LLM 纠错重试。
"""
import logging
import re
from typing import Any

from agent_core.llm_client import chat

logger = logging.getLogger(__name__)


def validate_output(text: str, context: dict) -> tuple[bool, str]:
    """校验 LLM 输出是否合法。

    Returns:
        (是否通过, 失败原因)
    """
    if not text or not text.strip():
        return False, "输出为空"

    if len(text.strip()) < 5:
        return False, "输出过短（< 5 字符）"

    # 检查是否包含错误标记
    error_markers = ["[LLM 调用失败", "请求超时", "API Error", "Connection error"]
    for marker in error_markers:
        if marker in text:
            return False, f"包含错误标记: {marker}"

    return True, ""


def correct_output(original: str, reason: str, context: dict) -> str:
    """调用 LLM 纠错。"""
    prompt = f"""你的前一次输出不合法。请重新生成。

前一次输出: {original[:200]}
失败原因: {reason}
任务描述: {context.get("step_desc", "")}
用户指令: {context.get("task_text", "")}

请给出正确的输出："""

    try:
        corrected = chat([
            {"role": "system", "content": "你是一个任务执行助手，请根据上下文完成任务并返回结果。"},
            {"role": "user", "content": prompt},
        ], temperature=0.3)
        return corrected
    except Exception as e:
        logger.error("纠错调用失败: %s", e)
        return original


def validate_and_retry(text: str, context: dict, max_retries: int = 2) -> tuple[str, bool]:
    """校验 + 自动重试。

    Returns:
        (最终文本, 是否通过校验)
    """
    for attempt in range(max_retries + 1):
        ok, reason = validate_output(text, context)
        if ok:
            return text, True

        if attempt < max_retries:
            logger.warning("校验失败（第 %d 次）: %s，尝试纠错", attempt + 1, reason)
            text = correct_output(text, reason, context)

    return text, False
