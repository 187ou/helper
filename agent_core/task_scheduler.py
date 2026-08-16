"""任务调度：串联 parser → builder → graph.execute，含演化打分。"""
import logging
import time
from typing import Any, Generator

from core.context import new_task_id, set_task_id
from agent_core.task_parser import parse, detect_task_type
from agent_core.graph_builder import build_graph, build_dag
from evolution_core.judge_score import score_work, score_life, combined_score
from memory_store.sqlite_db import now_str
from config.app_const import TaskStatus, ai_to_lifecycle_status
from service.task_service import create_task, save_dag, get_task, update_task
from evolution_core.async_evolution import submit_evolution, start_async_evolution, shutdown_async_evolution

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

    # 4. 演化打分（同步，快速返回）
    result["work_score"] = score_work(result)
    result["life_score"] = score_life(result)
    result["logs"].append(f"工作评分: {result['work_score']:.1f} | 生活评分: {result['life_score']:.1f}")

    # 5. 自演化闭环（异步，不阻塞主任务）
    _evolution_loop_async(task_text, result)

    # 6. 持久化到数据库
    _save_task(result, task_type)

    logger.info("任务结束: status=%s, work=%.1f, life=%.1f",
                result["status"], result["work_score"], result["life_score"])
    return result


def _evolution_loop_async(task_text: str, result: dict) -> None:
    """异步提交演化闭环（不阻塞主任务）。

    将演化任务提交到后台队列，由工作线程异步执行。
    如果异步系统不可用，降级到同步执行。
    """
    # 边缘：检查演化总开关
    try:
        from service.evolution_config_service import is_evolution_enabled
        if not is_evolution_enabled():
            return
    except Exception:
        pass

    # 边缘：补全 result 字段
    from evolution_core.safe_ops import validate_task_result
    result = validate_task_result(result)

    # 尝试异步提交
    try:
        submitted = submit_evolution(task_text, result)
        if submitted:
            logger.debug("演化任务已异步提交: %s", task_text[:30])
            return
    except Exception as e:
        logger.warning("异步提交失败，降级同步: %s", e)

    # 降级：同步执行（只执行核心步骤，跳过 LLM 打分）
    _evolution_loop_sync_fallback(task_text, result)


def _evolution_loop_sync_fallback(task_text: str, result: dict) -> None:
    """同步降级执行（只执行轻量操作，快速返回）。"""
    try:
        # 只用规则打分（不调 LLM）
        from evolution_core.judge_score import _rule_score
        scores = _rule_score(result, result.get("task_type", "work"))
        score = scores.get("overall", 60)

        task_type = result.get("task_type", "work")
        success = result.get("status") == TaskStatus.SUCCESS.value
        duration = result.get("cost_time", 0)

        # 权重迭代
        try:
            from evolution_core.weight_evolve import evolve_from_task
            evolve_from_task(task_text, score, task_type, success, duration)
        except Exception:
            pass

        # 模式学习
        try:
            from evolution_core.pattern_miner import learn_from_task
            learn_from_task(task_text, result.get("steps", []), score, duration, success)
        except Exception:
            pass

    except Exception as e:
        logger.warning("同步降级演化失败: %s", e)


def run_stream(task_text: str, task_id: int | None = None,
               resume_from: int | None = None) -> Generator[dict, None, None]:
    """流式执行任务，yield 事件供 SSE 推送。

    支持断点续跑：传入 task_id 和 resume_from 可从指定步骤继续。

    事件类型:
    - steps: 拆解结果 {steps: [...]}
    - step_start: 步骤开始 {index, name}
    - token: LLM 输出逐字符 {index, text}
    - step_done: 步骤完成 {index, name, status}
    - log: 日志消息 {message}
    - done: 完成 {cost_time, status}

    Args:
        task_text: 任务文本
        task_id: 已有任务 ID（重试/续跑时传入），None 则新建
        resume_from: 从哪个步骤索引开始续跑（跳过之前成功的步骤）
    """
    # ── 任务初始化 ──
    if task_id is None:
        task_id = new_task_id()
    set_task_id(task_id)
    is_resume = resume_from is not None

    # 1. 拆解
    steps = parse(task_text)
    yield {
        "type": "steps",
        "data": {
            "task_id": task_id,
            "is_resume": is_resume,
            "steps": [{"index": s.index, "name": s.name, "desc": s.description, "type": s.step_type} for s in steps],
        },
    }

    # ── 恢复已有状态（断点续跑） ──
    step_results: list[dict] = []
    node_states: dict[str, str] = {}  # step_id → status

    if is_resume:
        try:
            from service.task_service import get_task, get_dag
            existing_task = get_task(task_id)
            existing_dag = get_dag(task_id) if existing_task else None
            if existing_dag:
                for node in existing_dag.get("nodes", []):
                    node_states[node["id"]] = node.get("status", "pending")
                # 恢复已完成的结果
                for node in existing_dag.get("nodes", []):
                    if node.get("status") == "success":
                        # 从持久化的 task_steps 恢复结果
                        pass
            logger.info("断点续跑: 任务 #%d，从步骤 %d 继续，已有 %d 步完成",
                        task_id, resume_from, sum(1 for v in node_states.values() if v == "success"))
            yield {"type": "log", "data": {"message": f"🔄 断点续跑：从步骤 {resume_from + 1} 继续"}}
        except Exception as e:
            logger.warning("恢复状态失败，从头执行: %s", e)
            is_resume = False
            resume_from = None

    # 2. 逐个步骤执行 + 流式输出
    start = time.time()

    try:
        for step in steps:
            nid = f"step_{step.index}"

            # 断点续跑：跳过已成功的步骤
            if is_resume and resume_from is not None and step.index < resume_from:
                if node_states.get(nid) == "success":
                    # 注入已完成的结果作为上下文
                    logger.info("[节点 %d] 跳过（已完成）", step.index)
                    continue

            # 标记为执行中
            node_states[nid] = "running"
            yield {"type": "step_start", "data": {"index": step.index, "name": step.name}}

            state = {
                "task_text": task_text,
                "logs": [],
                "completed_steps": [],
                "step_results": step_results,
                "cost_time": 0,
                "current_step": step.index - 1,
            }

            # 执行节点并流式推送 token（含执行重试）
            result = yield from _execute_node_streaming(step, state)

            # 更新节点状态
            node_states[nid] = result.get("status", "failed")
            if result.get("status") == "success":
                step_results.extend(result.get("step_results", []))
                yield {"type": "step_done", "data": {"index": step.index, "name": step.name, "status": "success"}}
            else:
                yield {"type": "step_done", "data": {"index": step.index, "name": step.name, "status": "failed"}}
                yield {"type": "log", "data": {"message": f"❌ 步骤 {step.index} 执行失败: {result.get('error', '未知错误')}"}}
                # 失败不立即终止，继续执行后续步骤（部分成功策略）

    except Exception as e:
        logger.exception("流式任务异常: %s", e)
        yield {"type": "log", "data": {"message": f"执行异常: {e}"}}

    cost_time = time.time() - start

    # ── 计算最终状态 ──
    total_steps = len(steps)
    success_steps = sum(1 for v in node_states.values() if v == "success")
    failed_steps = sum(1 for v in node_states.values() if v == "failed")

    if failed_steps == 0 and success_steps == total_steps:
        final_status = TaskStatus.DONE.value
    elif success_steps > 0:
        final_status = TaskStatus.FAILED.value  # 部分成功仍标记失败（可重试）
    else:
        final_status = TaskStatus.FAILED.value

    yield {"type": "log", "data": {"message": f"执行完成: {success_steps}/{total_steps} 步成功，耗时 {cost_time:.2f}s"}}
    yield {"type": "done", "data": {"cost_time": cost_time, "status": final_status,
                                    "success_steps": success_steps, "failed_steps": failed_steps}}

    # ── 持久化任务 + DAG + 状态流转 ──
    try:
        from service.task_service import create_task, save_dag, update_task, get_task
        task_type = detect_task_type(task_text)

        # 如果是续跑，获取已有任务；否则新建
        existing = get_task(task_id) if is_resume else None
        if existing:
            task = existing
        else:
            task = create_task(
                content=task_text,
                task_type=task_type.value,
                steps=[{"index": s.index, "name": s.name, "desc": s.description, "type": s.step_type} for s in steps],
                source="ai",
            )

        if task:
            # 使用共享 build_dag 生成正确的并行边，注入节点状态
            step_dicts = [
                {
                    "index": s.index,
                    "name": s.name,
                    "description": s.description,
                    "step_type": s.step_type,
                    "status": node_states.get(f"step_{s.index}", "pending"),
                }
                for s in steps
            ]
            dag = build_dag(step_dicts)
            save_dag(task_id, dag)

            # 更新任务状态
            update_task(task_id, status=final_status)
            logger.info("任务 #%d 已持久化，状态 → %s，DAG 节点 %d 个",
                        task_id, final_status, len(dag["nodes"]))

            # ── 任务产出自动归档到知识库（语义记忆扩展） ──
            if final_status == TaskStatus.DONE.value and step_results:
                _archive_task_results(task_text, step_results)
    except Exception as e:
        logger.warning("持久化任务失败: %s", e)


def _execute_node_streaming(step, state) -> Generator[dict, dict, dict]:
    """执行单个节点，yield 每个 token，最后返回结果。

    使用 execute_node 的执行重试 + 校验重试能力。
    """
    from agent_core.node_executor import execute_node

    token_buffer: list[str] = []

    def token_cb(token: str) -> None:
        """流式回调：缓存 token 并推送给前端。"""
        token_buffer.append(token)
        return {"type": "token", "data": {"index": step.index, "text": token}}

    # 使用 execute_node 的完整重试逻辑
    # 但我们需要拦截 token 推送，所以手动实现流式 + 重试
    from agent_core.llm_client import chat_stream
    from agent_core.result_validator import validate_and_retry
    from agent_core.node_executor import MAX_EXEC_RETRIES, RETRY_BACKOFF_BASE

    context = _build_node_context(step, state)
    last_error = ""
    step_result = None
    attempts = 0

    for attempt in range(MAX_EXEC_RETRIES + 1):
        try:
            if attempt > 0:
                wait = RETRY_BACKOFF_BASE ** attempt
                yield {"type": "log", "data": {"message": f"🔄 步骤 {step.index} 第 {attempt} 次重试（{wait:.1f}s 后）..."}}
                import time as _time
                _time.sleep(wait)
                token_buffer.clear()

            # 流式执行
            result_parts: list[str] = []
            for token in chat_stream([
                {"role": "system", "content": "你是一个任务执行助手。你会收到一个任务步骤的描述和上下文，需要执行该步骤并返回结果。"},
                {"role": "user", "content": context},
            ], temperature=0.5):
                result_parts.append(token)
                yield {"type": "token", "data": {"index": step.index, "text": token}}

            result = "".join(result_parts)
            validated, passed = validate_and_retry(result, {
                "step_desc": step.description,
                "task_text": state.get("task_text", ""),
            })

            step_result = {"index": step.index, "name": step.name, "result": validated}
            attempts = attempt + 1
            break  # 成功

        except Exception as e:
            last_error = str(e)
            logger.error("[节点 %d] 执行异常（第 %d 次）: %s", step.index, attempt + 1, e)
            attempts = attempt + 1

    success = step_result is not None
    return {
        "logs": [f"[{step.index}] {step.name}: {step_result['result'][:100] if step_result else last_error}..."],
        "completed_steps": [step.index] if success else [],
        "step_results": [step_result] if success else [],
        "cost_time": 0,
        "current_step": step.index,
        "status": "success" if success else "failed",
        "attempts": attempts,
        "error": "" if success else last_error,
    }


def _build_node_context(step, state) -> str:
    """构建节点执行上下文（记忆增强）。"""
    parts = [f"## 当前步骤\n名称: {step.name}\n描述: {step.description}"]
    prev_results = state.get("step_results", [])
    if prev_results:
        parts.append("\n## 前序步骤结果")
        for r in prev_results[-3:]:
            parts.append(f"- [{r['name']}] {r['result'][:200]}")

    task_text = state.get("task_text", "")
    if task_text:
        parts.append(f"\n## 用户原始指令\n{task_text}")

    # 添加记忆增强上下文
    try:
        from agent_core.memory_context import build_memory_context
        memory = build_memory_context(f"{step.name} {task_text}", step_name=step.name, top_k=1)
        if memory:
            parts.append(f"\n{memory}")
    except Exception:
        pass

    return "\n".join(parts)


def _archive_task_results(task_text: str, step_results: list[dict]) -> None:
    """将任务产出归档到知识库（异步，不阻塞）。"""
    try:
        from agent_core.memory_context import archive_task_output

        # 拼接所有步骤结果
        output_parts = []
        for r in step_results:
            name = r.get("name", "")
            result = r.get("result", "")
            if result:
                output_parts.append(f"### {name}\n{result}")

        if not output_parts:
            return

        output_text = f"# 任务产出：{task_text}\n\n" + "\n\n".join(output_parts)

        # 确定分类
        task_type = detect_task_type(task_text).value
        category_map = {"work": "work_doc", "life": "personal", "health": "personal", "mix": "work_doc"}
        category = category_map.get(task_type, "work_doc")

        archive_task_output(
            task_text=task_text,
            output_text=output_text,
            category=category,
            file_name=f"产出_{task_text[:15]}",
        )
    except Exception as e:
        logger.debug("任务产出归档失败: %s", e)


def _save_task(result: dict, task_type) -> None:
    """保存任务记录到数据库（AI 执行状态 → 生命周期状态）。"""
    try:
        from memory_store.repositories import TaskRepository
        repo = TaskRepository()
        # 关键：将 AI 执行状态映射为生命周期状态后再持久化
        lifecycle_status = ai_to_lifecycle_status(result.get("status", ""))
        repo.save(
            task_type=task_type.value if hasattr(task_type, 'value') else str(task_type),
            content=result["task_text"],
            steps=result["steps"],
            status=lifecycle_status,
            cost_time=result["cost_time"],
            work_score=result["work_score"],
            life_score=result["life_score"],
        )
        logger.info("任务记录已保存: status=%s (AI原始=%s)", lifecycle_status, result.get("status"))
    except Exception as e:
        logger.warning("任务保存失败: %s", e)
