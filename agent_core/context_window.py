"""上下文窗口管理：防止 LLM 输入超出 token 限制。

核心能力：
1. Token 估算（中文约 1.5 char/token，英文约 4 char/token）
2. 按优先级填充上下文，超出窗口时截断低优先级内容
3. 截断时保留关键信息，避免语义断裂

优先级（从高到低）：
- 系统指令（不可截断）
- 当前步骤/查询（不可截断）
- 记忆上下文（偏好/历史/知识）
- 前序步骤结果（可截断）
- 原始指令（可截断）
"""
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ── 配置 ──
DEFAULT_MAX_TOKENS = 6000      # 默认最大上下文 token 数
MAX_CONTEXT_RATIO = 0.8        # 使用最大上下文的比例（留 buffer）


def estimate_tokens(text: str) -> int:
    """估算文本的 token 数。

    规则：
    - 中文：约 1.5 字符/token
    - 英文/数字：约 4 字符/token
    - 标点和空格也计入
    """
    if not text:
        return 0

    # 统计中文字符数
    chinese_chars = len(re.findall(r'[一-鿿]', text))
    # 非中文字符数
    other_chars = len(text) - chinese_chars

    # 估算：中文 1.5 char/token，英文 4 char/token
    tokens = chinese_chars / 1.5 + other_chars / 4
    return int(tokens) + 1


def fit_context(parts: list[tuple[str, int]], max_tokens: int = DEFAULT_MAX_TOKENS,
                priority_threshold: int = 3) -> str:
    """按优先级填充上下文，超出窗口时截断低优先级内容。

    Args:
        parts: [(文本, 优先级)] 优先级 1-5，1 最高（系统指令），5 最低（可截断）
        max_tokens: 最大 token 数
        priority_threshold: 低于此优先级的内容会被截断

    Returns:
        拼接后的上下文字符串
    """
    if not parts:
        return ""

    max_tokens = int(max_tokens * MAX_CONTEXT_RATIO)
    result_parts: list[str] = []
    current_tokens = 0

    # 按优先级排序（数字小的优先）
    sorted_parts = sorted(parts, key=lambda x: x[1])

    for text, priority in sorted_parts:
        if not text:
            continue

        text_tokens = estimate_tokens(text)

        # 高优先级内容：尽量保留
        if priority <= priority_threshold:
            if current_tokens + text_tokens <= max_tokens:
                result_parts.append(text)
                current_tokens += text_tokens
            else:
                # 尝试截断
                remaining = max_tokens - current_tokens
                if remaining > 50:  # 至少留 50 token
                    truncated = truncate_text(text, remaining)
                    if truncated:
                        result_parts.append(truncated)
                        current_tokens += estimate_tokens(truncated)
                # 高优先级内容被截断时记录警告
                if text_tokens > remaining:
                    logger.debug("高优先级内容被截断: priority=%d, %d→%d tokens",
                                 priority, text_tokens, remaining)
        else:
            # 低优先级内容：有空间才放
            if current_tokens + text_tokens <= max_tokens:
                result_parts.append(text)
                current_tokens += text_tokens
            else:
                # 低优先级内容直接跳过
                logger.debug("低优先级内容跳过: priority=%d, %d tokens", priority, text_tokens)

    return "\n\n".join(result_parts)


def truncate_text(text: str, max_tokens: int) -> str:
    """将文本截断到指定 token 数，尽量在句子边界截断。"""
    if estimate_tokens(text) <= max_tokens:
        return text

    # 按句子边界截断（优先在句号、换行处截断）
    sentences = re.split(r'(?<=[。！？\n])', text)
    result = []
    current_tokens = 0

    for sent in sentences:
        sent_tokens = estimate_tokens(sent)
        if current_tokens + sent_tokens <= max_tokens:
            result.append(sent)
            current_tokens += sent_tokens
        else:
            # 当前句子放不下了，尝试截断句子
            remaining = max_tokens - current_tokens
            if remaining > 20:
                # 简单截断到字符数
                char_limit = int(remaining * 3)  # 保守估计
                truncated = sent[:char_limit].rsplit(' ', 1)[0]  # 避免截断单词
                if truncated:
                    result.append(truncated + "...")
            break

    return "".join(result)


def build_context_with_window(system_prompt: str, user_query: str,
                               memory_context: str = "",
                               prior_results: list[str] | None = None,
                               original_instruction: str = "",
                               max_tokens: int = DEFAULT_MAX_TOKENS) -> str:
    """构建带窗口管理的上下文（一站式入口）。

    优先级：
    1. 系统指令（不可截断）
    2. 当前查询（不可截断）
    3. 记忆上下文（偏好/历史/知识）
    4. 前序步骤结果（可截断）
    5. 原始指令（可截断）
    """
    parts: list[tuple[str, int]] = []

    # 优先级 1：系统指令
    if system_prompt:
        parts.append((system_prompt, 1))

    # 优先级 2：当前查询
    if user_query:
        parts.append((user_query, 2))

    # 优先级 3：记忆上下文
    if memory_context:
        parts.append((memory_context, 3))

    # 优先级 4：前序步骤结果
    if prior_results:
        for i, result in enumerate(prior_results):
            # 最近的结果优先级更高
            priority = 4 if i < 2 else 5
            parts.append((f"[前序步骤 {i+1}]\n{result}", priority))

    # 优先级 5：原始指令
    if original_instruction and original_instruction != user_query:
        parts.append((f"[原始指令]\n{original_instruction}", 5))

    return fit_context(parts, max_tokens)
