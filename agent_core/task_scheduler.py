"""任务调度：串联 parser → builder → graph.execute，含演化打分。"""
import logging
import time
from typing import Any, Generator

from core.context import new_task_id, set_task_id
from agent_core.task_parser import parse, detect_task_type
from agent_core.graph_builder import build_graph
from evolution_core.judge_score import score_work, score_life, combined_score
from memory_store.sqlite_db import now_str
from config.app_const import TaskStatus

logger = logging.getLogger(__name__)


def run(task_text: str) -> dict[str, Any]:
    """执行完整任务链路，返回结果字典。"""
    # 注入 task_id，后续所有日志自动携带
    task_id = new_task_id()
    set_task_id(task_id)

    result: dict[str, Any] = {
        "task_id": task_id,
        "task_text": task_text,
        "steps": [],
        "status": TaskStatus.RUNNING.value,
        "logs": [],
        "cost_time": 0,
        "work_score": 0,
        "life_score": 0,
    }

    logger.info("任务开始: %s", task_text[:50])

    # 1. 拆解
    steps = parse(task_text)
    result["steps"] = [{"index": s.index, "name": s.name, "desc": s.description, "type": s.step_type} for s in steps]
    result["logs"].append(f"拆解为 {len(steps)} 个步骤")
    task_type = detect_task_type(task_text)

    # 2. 建图
    graph = build_graph(steps)
    if graph is None:
        result["status"] = TaskStatus.FAIL.value
        result["logs"].append("图构建失败（LangGraph 未就绪）")
        return result

    # 3. 执行（带超时保护）
    start = time.time()
    max_exec_time = 120  # 单次任务最长 120 秒
    try:
        init_state = {
            "task_text": task_text,
            "logs": [],
            "completed_steps": [],
            "step_results": [],
            "cost_time": 0,
            "current_step": -1,
        }
        # LangGraph 的 invoke 不支持直接 timeout，用 config 传入递归限制
        try:
            from langgraph.pregel import Pregel
            config = {"recursion_limit": len(steps) * 3 + 10} if steps else {"recursion_limit": 20}
        except ImportError:
            config = None
        final_state = graph.invoke(init_state, config=config) if config else graph.invoke(init_state)
        result["logs"].extend(final_state.get("logs", []))
        result["step_results"] = final_state.get("step_results", [])
        result["cost_time"] = time.time() - start
        result["status"] = TaskStatus.SUCCESS.value
        result["logs"].append(f"执行完成，总耗时 {result['cost_time']:.2f}s")
        logger.info("任务完成: 耗时 %.2fs", result["cost_time"])
    except Exception as e:
        result["status"] = TaskStatus.FAIL.value
        result["cost_time"] = time.time() - start
        result["logs"].append(f"执行异常: {e}")
        logger.exception("任务执行异常: %s", e)

    # 4. 演化打分
    result["work_score"] = score_work(result)
    result["life_score"] = score_life(result)
    result["logs"].append(f"工作评分: {result['work_score']:.1f} | 生活评分: {result['life_score']:.1f}")

    # 5. 自演化闭环
    _evolution_loop(task_text, result)

    # 6. 持久化到数据库
    _save_task(result, task_type)

    logger.info("任务结束: status=%s, work=%.1f, life=%.1f",
                result["status"], result["work_score"], result["life_score"])
    return result


def _evolution_loop(task_text: str, result: dict) -> None:
    """自演化闭环：打分 → 流程优化 → 权重迭代 → 模板固化 → 日志记录。"""
    try:
        score = combined_score(
            result["work_score"], result["life_score"],
            result.get("task_type", "work")
        )
        result["combined_score"] = score

        # 权重迭代
        from evolution_core.weight_evolve import evolve_from_task
        evolve_from_task(task_text, score)

        # 流程优化（步骤 > 2 时）
        if len(result.get("steps", [])) > 2:
            from evolution_core.flow_optimize import optimize
            from evolution_core.evo_log import log_flow_optimize
            old_steps = result["steps"]
            optimized = optimize(old_steps)
            if len(optimized) < len(old_steps):
                log_flow_optimize(old_steps, optimized)
                result["logs"].append(f"流程优化: {len(old_steps)}步 → {len(optimized)}步")

        # 模板固化（高频任务）
        from evolution_core.template_save import check_and_save_template, list_templates
        from evolution_core.evo_log import log_template_save
        tpl = check_and_save_template(task_text, result.get("steps", []))
        if tpl:
            log_template_save(tpl["name"], tpl["freq"])
            result["logs"].append(f"固化模板: {tpl['name']}")

    except Exception as e:
        logger.warning("演化闭环异常: %s", e)


def run_stream(task_text: str) -> Generator[dict, None, None]:
    """流式执行任务，yield 事件供 SSE 推送。

    事件类型:
    - steps: 拆解结果 {steps: [...]}
    - step_start: 步骤开始 {index, name}
    - token: LLM 输出逐字符 {index, text}
    - step_done: 步骤完成 {index, name}
    - done: 完成 {cost_time}
    """
    task_id = new_task_id()
    set_task_id(task_id)

    # 1. 拆解
    steps = parse(task_text)
    yield {
        "type": "steps",
        "data": {
            "task_id": task_id,
            "steps": [{"index": s.index, "name": s.name, "desc": s.description, "type": s.step_type} for s in steps],
        },
    }

    # 2. 逐个步骤执行 + 流式输出
    start = time.time()
    step_results = []

    try:
        for step in steps:
            yield {"type": "step_start", "data": {"index": step.index, "name": step.name}}

            state = {
                "task_text": task_text,
                "logs": [],
                "completed_steps": [],
                "step_results": step_results,
                "cost_time": 0,
                "current_step": step.index - 1,
            }

            # 执行节点并流式推送 token
            result = yield from _execute_node_streaming(step, state)
            step_results.extend(result.get("step_results", []))

            yield {"type": "step_done", "data": {"index": step.index, "name": step.name}}
    except Exception as e:
        logger.exception("流式任务异常: %s", e)
        yield {"type": "log", "data": {"message": f"执行异常: {e}"}}

    cost_time = time.time() - start
    yield {"type": "log", "data": {"message": f"执行完成，总耗时 {cost_time:.2f}s"}}
    yield {"type": "done", "data": {"cost_time": cost_time}}


def _execute_node_streaming(step, state) -> Generator[dict, None, dict]:
    """执行单个节点，yield 每个 token，最后返回结果。"""
    from agent_core.llm_client import chat_stream
    from agent_core.result_validator import validate_and_retry

    context = _build_node_context(step, state)
    result_parts = []

    for token in chat_stream([
        {"role": "system", "content": "你是一个任务执行助手。你会收到一个任务步骤的描述和上下文，需要执行该步骤并返回结果。"},
        {"role": "user", "content": context},
    ], temperature=0.5):
        result_parts.append(token)
        yield {"type": "token", "data": {"index": step.index, "text": token}}

    result = "".join(result_parts)
    validated, _ = validate_and_retry(result, {
        "step_desc": step.description,
        "task_text": state.get("task_text", ""),
    })

    return {
        "logs": [f"[{step.index}] {step.name}: {validated[:100]}..."],
        "completed_steps": [step.index],
        "step_results": [{"index": step.index, "name": step.name, "result": validated}],
        "cost_time": 0,
        "current_step": step.index,
    }


def _build_node_context(step, state) -> str:
    """构建节点执行上下文。"""
    parts = [f"## 当前步骤\n名称: {step.name}\n描述: {step.description}"]
    prev_results = state.get("step_results", [])
    if prev_results:
        parts.append("\n## 前序步骤结果")
        for r in prev_results[-3:]:
            parts.append(f"- [{r['name']}] {r['result'][:200]}")
    if state.get("task_text"):
        parts.append(f"\n## 用户原始指令\n{state['task_text']}")
    return "\n".join(parts)


def _save_task(result: dict, task_type) -> None:
    """保存任务记录到数据库。"""
    try:
        from memory_store.repositories import TaskRepository
        repo = TaskRepository()
        repo.save(
            task_type=task_type.value if hasattr(task_type, 'value') else str(task_type),
            content=result["task_text"],
            steps=result["steps"],
            status=result["status"],
            cost_time=result["cost_time"],
            work_score=result["work_score"],
            life_score=result["life_score"],
        )
        logger.info("任务记录已保存")
    except Exception as e:
        logger.warning("任务保存失败: %s", e)
