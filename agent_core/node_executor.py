"""各任务节点执行器（LLM 驱动）。"""
import json
import logging
import time

from agent_core.task_parser import TaskStep
from agent_core.llm_client import chat

logger = logging.getLogger(__name__)

_EXECUTE_SYSTEM_PROMPT = """你是一个任务执行助手。你会收到一个任务步骤的描述和上下文，需要执行该步骤并返回结果。

规则：
1. 根据步骤描述完成具体任务（生成文本、分析数据、整理信息等）
2. 如果步骤需要数据但上下文中没有，明确说明需要什么数据
3. 输出要具体、可操作，不要空泛
4. 保持简洁，重点突出"""


def execute_node(step: TaskStep, state: dict) -> dict:
    """执行单个节点，返回**本步骤的增量结果**（非累积列表）。

    LangGraph 的 operator.add reducer 会自动合并各节点返回的增量。
    """
    logger.info("[节点 %d] %s", step.index, step.name)

    # 本步骤新增的日志
    new_logs = [f"[{step.index}] {step.name}: {step.description}"]
    # 本步骤的 step_result
    step_result = None

    start = time.time()

    # 构建上下文
    context = _build_context(step, state)

    try:
        result = chat([
            {"role": "system", "content": _EXECUTE_SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ], temperature=0.5)

        step_result = {
            "index": step.index,
            "name": step.name,
            "result": result,
        }
        new_logs.append(f"  → {result[:100]}...")
    except Exception as e:
        logger.error("[节点 %d] 执行异常: %s", step.index, e)
        new_logs.append(f"  → [异常] {e}")

    elapsed = time.time() - start
    logger.info("[节点 %d] 完成，耗时 %.2fs", step.index, elapsed)

    # 返回增量（LangGraph reducer 负责合并）
    update: dict = {
        "logs": new_logs,
        "completed_steps": [step.index],
        "cost_time": elapsed,
        "current_step": step.index,
    }
    if step_result:
        update["step_results"] = [step_result]
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
