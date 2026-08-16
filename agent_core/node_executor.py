"""各任务节点执行器（LLM 驱动），含执行重试 + 校验重试 + 流式输出支持。"""
import logging
import time
from typing import Callable, Optional

from agent_core.task_parser import TaskStep
from agent_core.llm_client import chat, chat_stream
from agent_core.result_validator import validate_and_retry
from agent_core.context_window import DEFAULT_MAX_TOKENS

logger = logging.getLogger(__name__)

def _get_execute_prompt() -> str:
    """获取执行 prompt（优先配置文件，降级默认）。"""
    try:
        from config.prompt_manager import get_prompt
        prompt = get_prompt("execute_system_prompt")
        if prompt:
            return prompt
    except Exception:
        pass
    return "你是一个任务执行助手。你会收到一个任务步骤的描述和上下文，需要执行该步骤并返回结果。输出要具体、可操作。"


# 向后兼容
_EXECUTE_PROMPT_CACHE = None


def _get_execute_prompt_static() -> str:
    global _EXECUTE_PROMPT_CACHE
    if _EXECUTE_PROMPT_CACHE is None:
        _EXECUTE_PROMPT_CACHE = _get_execute_prompt()
    return _EXECUTE_PROMPT_CACHE

# ── 重试配置 ──
MAX_EXEC_RETRIES = 2       # 执行失败最大重试次数
RETRY_BACKOFF_BASE = 1.5   # 指数退避基数（秒）


def execute_node(step: TaskStep, state: dict,
                 token_cb: Optional[Callable[[str], None]] = None,
                 max_retries: int = MAX_EXEC_RETRIES) -> dict:
    """执行单个节点，含执行重试（指数退避）+ 校验重试。

    Args:
        step: 任务步骤
        state: 当前状态上下文
        token_cb: 流式回调，每个 token 到达时调用
        max_retries: 执行失败最大重试次数

    Returns:
        执行更新字典，包含 status 字段标记 success/failed
    """
    logger.info("[节点 %d] %s", step.index, step.name)
    new_logs = [f"[{step.index}] {step.name}: {step.description}"]
    context = _build_context(step, state)
    step_result = None
    start = time.time()
    last_error: str = ""

    # ── 执行重试循环（指数退避） ──
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                wait = RETRY_BACKOFF_BASE ** attempt
                logger.info("[节点 %d] 第 %d 次重试（%.1fs 后）...", step.index, attempt, wait)
                time.sleep(wait)
                new_logs.append(f"  🔄 第 {attempt} 次重试")

            # 流式收集完整响应
            result_parts = []
            for token in chat_stream([
                {"role": "system", "content": _get_execute_prompt_static()},
                {"role": "user", "content": context},
            ], temperature=0.5):
                result_parts.append(token)
                if token_cb:
                    token_cb(token)

            result = "".join(result_parts)

            # 校验 + 自动重试
            validated, passed = validate_and_retry(result, {
                "step_desc": step.description,
                "task_text": state.get("task_text", ""),
            })
            if not passed:
                logger.warning("[节点 %d] 校验未通过，使用最后一次输出", step.index)
                new_logs.append("  ⚠️ 校验未通过，使用纠错后输出")

            step_result = {"index": step.index, "name": step.name, "result": validated}
            new_logs.append(f"  → {validated[:100]}...")
            break  # 成功，跳出重试循环

        except Exception as e:
            last_error = str(e)
            logger.error("[节点 %d] 执行异常（第 %d 次）: %s", step.index, attempt + 1, e)
            new_logs.append(f"  → [异常] {e}")

    elapsed = time.time() - start
    success = step_result is not None
    logger.info("[节点 %d] %s，耗时 %.2fs（%d 次尝试）",
                step.index, "成功" if success else "失败", elapsed, attempt + 1)

    update: dict = {
        "logs": new_logs,
        "completed_steps": [step.index] if success else [],
        "cost_time": elapsed,
        "current_step": step.index,
        "status": "success" if success else "failed",
        "attempts": attempt + 1,
    }
    if success:
        update["step_results"] = [step_result]
    else:
        update["error"] = last_error
    return update


def _build_context(step: TaskStep, state: dict) -> str:
    """构建节点执行的上下文（记忆增强 + 窗口管理）。"""
    task_text = state.get("task_text", "")
    prev_results = state.get("step_results", [])

    # 构建记忆增强上下文（含个性化指导 + 关联记忆）
    memory = _build_memory_for_step(step, task_text)

    # 注入个性化指导 + 情绪适配
    try:
        from agent_core.user_model import get_personalized_guidance
        from agent_core.emotional_memory import get_emotional_guidance
        guidance = get_personalized_guidance(detect_task_type_local(task_text))
        emotional = get_emotional_guidance()
        combined = "\n".join(filter(None, [guidance, emotional]))
        if combined:
            memory = f"{combined}\n\n{memory}" if memory else combined
    except Exception:
        pass

    # 格式化前序步骤结果
    prior_texts = []
    for r in prev_results[-3:]:  # 最多引用最近 3 步
        prior_texts.append(f"[{r['name']}] {r['result'][:200]}")

    # 使用上下文窗口管理构建最终 prompt
    from agent_core.context_window import build_context_with_window

    system_prompt = _get_execute_prompt_static()
    user_query = f"## 当前步骤\n名称: {step.name}\n描述: {step.description}"

    return build_context_with_window(
        system_prompt=system_prompt,
        user_query=user_query,
        memory_context=memory,
        prior_results=prior_texts,
        original_instruction=task_text,
        max_tokens=DEFAULT_MAX_TOKENS,
    )


def _build_memory_for_step(step: TaskStep, task_text: str) -> str:
    """为节点执行构建记忆片段（偏好 + 历史 + 知识）。"""
    try:
        from agent_core.memory_context import build_memory_context
        from evolution_core.feedback_learner import generate_execution_guidance

        # 1. 基础记忆上下文（历史参考 + 知识片段）
        query = f"{step.name} {task_text}"
        base_memory = build_memory_context(query, step_name=step.name, top_k=1)

        # 2. 偏好指导摘要（高置信度偏好直接注入）
        task_type = _detect_task_type_simple_local(task_text)
        guidance = generate_execution_guidance(task_type)

        # 3. 拼接：偏好指导优先级更高
        parts = []
        if guidance:
            parts.append(f"## 用户偏好\n{guidance}")
        if base_memory:
            parts.append(base_memory)

        return "\n\n".join(parts) if parts else ""
    except Exception as e:
        logger.debug("节点记忆构建失败: %s", e)
        return ""


def _detect_task_type_simple_local(task_text: str) -> str:
    """推断任务类型（本地副本避免循环导入）。"""
    work_keywords = ["周报", "月报", "日报", "报销", "会议", "Excel", "PDF", "合同", "文书", "归档", "项目"]
    life_keywords = ["记账", "开销", "购物", "家务", "出行", "健身", "睡眠", "饮食"]
    for kw in work_keywords:
        if kw in task_text:
            return "work"
    for kw in life_keywords:
        if kw in task_text:
            return "life"
    return "work"


def detect_task_type_local(task_text: str) -> str:
    """推断任务类型（本地副本，避免循环导入）。"""
    return _detect_task_type_simple_local(task_text)
