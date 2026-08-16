"""各任务节点执行器（LLM 驱动），含执行重试 + 校验重试 + 流式输出支持。"""
import logging
import time
from typing import Callable, Optional

from agent_core.task_parser import TaskStep
from agent_core.llm_client import chat, chat_stream
from agent_core.result_validator import validate_and_retry

logger = logging.getLogger(__name__)

_EXECUTE_SYSTEM_PROMPT = """你是一个任务执行助手。你会收到一个任务步骤的描述和上下文，需要执行该步骤并返回结果。

规则：
1. 根据步骤描述完成具体任务（生成文本、分析数据、整理信息等）
2. 如果步骤需要数据但上下文中没有，明确说明需要什么数据
3. 输出要具体、可操作，不要空泛
4. 保持简洁，重点突出"""

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
                {"role": "system", "content": _EXECUTE_SYSTEM_PROMPT},
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
    """构建节点执行的上下文。"""
    parts = [f"## 当前步骤\n名称: {step.name}\n描述: {step.description}"]

    # 添加已完成步骤的结果
    prev_results = state.get("step_results", [])
    if prev_results:
        parts.append("\n## 前序步骤结果")
        for r in prev_results[-3:]:  # 最多引用最近 3 步
            parts.append(f"- [{r['name']}] {r['result'][:200]}")

    # 添加用户原始指令
    if state.get("task_text"):
        parts.append(f"\n## 用户原始指令\n{state['task_text']}")

    return "\n".join(parts)
