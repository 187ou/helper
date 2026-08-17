"""任务调度：串联 parser → builder → graph.execute，含演化打分。"""
import logging
import time
from datetime import datetime
from typing import Any, Generator

from core.context import new_task_id, set_task_id
from agent_core.task_parser import parse, parse_with_source, detect_task_type
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
    # trace_id 用于日志串联（hex 短码），db_id 是 task_list 表的整数主键。
    # 两者不可混用：用 hex 串去 UPDATE ... WHERE id = ? 会静默匹配 0 行。
    set_task_id(new_task_id())
    is_resume = resume_from is not None
    db_id = task_id

    # 1. 拆解（带来源信息）
    steps, source_info = parse_with_source(task_text)

    # 续跑复用已有记录；新任务先建表拿到真实主键，后续落库/前端回传都用它
    if db_id is None:
        created = create_task(
            content=task_text,
            task_type=detect_task_type(task_text).value,
            steps=[{"index": s.index, "name": s.name, "desc": s.description, "type": s.step_type} for s in steps],
            source="ai",
        )
        db_id = created["id"]

    yield {
        "type": "steps",
        "data": {
            "task_id": db_id,
            "is_resume": is_resume,
            "source": source_info.get("source", "llm"),
            "source_label": source_info.get("source_label", "AI 智能拆解"),
            "template_name": source_info.get("template_name", ""),
            "steps": [{"index": s.index, "name": s.name, "desc": s.description, "type": s.step_type} for s in steps],
        },
    }

    # ── 主动回忆提醒 + 情感检测 + 需求预测 ──
    try:
        from agent_core.memory_context import check_proactive_reminder
        reminder = check_proactive_reminder(task_text)
        if reminder:
            yield {"type": "reminder", "data": {"message": reminder}}
    except Exception:
        pass

    # 情感检测
    try:
        from agent_core.emotional_memory import record_emotion
        emotion = record_emotion(db_id, task_text, source="user_input")
        if emotion and emotion.get("emotion") != "neutral":
            yield {"type": "emotion", "data": {"emotion": emotion["emotion"], "label": emotion["emotion_label"]}}
    except Exception:
        pass

    # 需求预测
    try:
        from agent_core.proactive_reasoning import predict_next_needs
        predictions = predict_next_needs(task_text, detect_task_type(task_text).value)
        if predictions:
            yield {"type": "prediction", "data": {"predictions": predictions[:3]}}
    except Exception:
        pass

    # ── 恢复已有状态（断点续跑） ──
    step_results: list[dict] = []
    node_states: dict[str, str] = {}  # step_id → status

    if is_resume:
        try:
            from service.task_service import get_task, get_dag
            existing_task = get_task(db_id)
            existing_dag = get_dag(db_id) if existing_task else None
            if existing_dag:
                for node in existing_dag.get("nodes", []):
                    node_states[node["id"]] = node.get("status", "pending")

                # 恢复已完成步骤的结果到 step_results（关键修复）
                restored_count = _restore_completed_results(existing_task, existing_dag, step_results)
                logger.info("断点续跑: 任务 #%d，从步骤 %d 继续，恢复 %d 步结果",
                            db_id, resume_from, restored_count)
                yield {"type": "log", "data": {"message": f"断点续跑：从步骤 {resume_from + 1} 继续（已恢复 {restored_count} 步结果）"}}

            # 恢复工作记忆（断点续跑时恢复上下文）
            from agent_core.working_memory import restore_working_memory_from_task
            wm = restore_working_memory_from_task(db_id)
            if wm:
                logger.info("工作记忆已恢复: task #%d（目标: %s）", db_id, wm.task_goal[:50])
        except Exception as e:
            logger.warning("恢复状态失败，从头执行: %s", e)
            is_resume = False
            resume_from = None

    # 2. 初始化工作记忆
    from agent_core.working_memory import get_working_memory
    wm = get_working_memory(db_id, task_text, steps)
    # 从拆解结果推断任务目标
    if steps:
        wm.update_goal(f"{task_text}（{len(steps)} 步）")

    # 3. 逐个步骤执行 + 流式输出
    start = time.time()

    try:
        for step in steps:
            nid = f"step_{step.index}"

            # 断点续跑：跳过已成功的步骤
            if is_resume and resume_from is not None and step.index < resume_from:
                if node_states.get(nid) == "success":
                    logger.info("[节点 %d] 跳过（已完成）", step.index)
                    continue

            # 标记为执行中
            node_states[nid] = "running"
            yield {"type": "step_start", "data": {"index": step.index, "name": step.name}}

            # 构建 state（含工作记忆）
            state = {
                "task_text": task_text,
                "logs": [],
                "completed_steps": [],
                "step_results": step_results,
                "cost_time": 0,
                "current_step": step.index - 1,
                "working_memory": wm.get_context_summary(),  # 工作记忆注入
            }

            # 执行节点并流式推送 token（含执行重试）
            result = yield from _execute_node_streaming(step, state)

            # 更新节点状态和工作记忆
            node_states[nid] = result.get("status", "failed")
            if result.get("status") == "success":
                step_result_text = result.get("step_results", [{}])[0].get("result", "")
                step_results.extend(result.get("step_results", []))
                wm.record_step_completion(step.name, result.get("step_results", [{}])[0].get("result", ""))
                yield {"type": "step_done", "data": {"index": step.index, "name": step.name, "status": "success"}}
            else:
                yield {"type": "step_done", "data": {"index": step.index, "name": step.name, "status": "failed"}}
                yield {"type": "log", "data": {"message": f"步骤 {step.index} 执行失败: {result.get('error', '未知错误')}"}}
                # 失败不立即终止，继续执行后续步骤（部分成功策略）

    except Exception as e:
        logger.exception("流式任务异常: %s", e)
        # 结构化异常事件：前端可据此显示错误类型和建议
        yield {
            "type": "error",
            "data": {
                "message": str(e)[:300],
                "error_type": type(e).__name__,
                "step_index": step.index if 'step' in dir() else -1,
                "suggestion": _get_error_suggestion(e),
            },
        }

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

    # ── 持久化 DAG + 状态流转（任务记录已在开头创建） ──
    try:
        # 使用共享 build_dag 生成正确的并行边，注入节点状态与真实执行产出
        results_by_index = {r["index"]: r.get("result", "") for r in step_results if "index" in r}
        step_dicts = [
            {
                "index": s.index,
                "name": s.name,
                "description": s.description,
                "step_type": s.step_type,
                "status": node_states.get(f"step_{s.index}", "pending"),
                # 存真实产出而非步骤描述，续跑时后续节点才能拿到有效上下文
                "result": results_by_index.get(s.index, "")[:2000],
            }
            for s in steps
        ]
        dag = build_dag(step_dicts)
        save_dag(db_id, dag)

        # 更新任务状态
        update_task(db_id, status=final_status)
        logger.info("任务 #%d 已持久化，状态 → %s，DAG 节点 %d 个",
                    db_id, final_status, len(dag["nodes"]))

        # ── 任务完成后处理（归档 + 索引） ──
        if final_status == TaskStatus.DONE.value:
            avg_score = _calc_avg_step_score(step_results) if step_results else 0

            # 产出归档到知识库
            if step_results:
                _archive_task_results(task_text, step_results, score=avg_score, task_id=db_id)

            # 工作记忆归档
            from agent_core.working_memory import archive_working_memory_to_episodic
            archive_working_memory_to_episodic(db_id)

            # 添加到语义索引（情景记忆语义化）
            from memory_store.episodic_index import add_task_to_index
            add_task_to_index(
                task_id=db_id,
                task_text=task_text,
                task_type=detect_task_type(task_text).value,
                score=avg_score,
            )

            # 自动创建记忆关联
            from agent_core.memory_graph import auto_discover_links
            auto_discover_links(task_text, detect_task_type(task_text).value, db_id)

            # 事件触发检测（任务完成时检查是否有事件匹配）
            from agent_core.prospective_memory import _check_event_triggers
            event_due = _check_event_triggers(task_text, datetime.now())
            for e in event_due:
                yield {"type": "event_triggered", "data": {"message": f"事件触发: {e.get('user_intent', '')[:50]}", "reminder": e}}
    except Exception as e:
        logger.warning("持久化任务失败: %s", e)


def _restore_completed_results(existing_task: dict | None, existing_dag: dict | None,
                                step_results: list[dict]) -> int:
    """从持久化的任务和 DAG 中恢复已完成步骤的结果。

    Args:
        existing_task: 数据库中的任务记录
        existing_dag: DAG 数据（含节点状态）
        step_results: 当前步骤结果列表（会被修改）

    Returns:
        恢复的步骤数量
    """
    if not existing_task or not existing_dag:
        return 0

    restored = 0
    try:
        # 从 task_steps 获取步骤定义
        task_steps_raw = existing_task.get("task_steps", "[]")
        if isinstance(task_steps_raw, str):
            import json
            task_steps = json.loads(task_steps_raw) if task_steps_raw else []
        else:
            task_steps = task_steps_raw or []

        # 从 DAG 获取成功节点（含持久化的执行产出）
        completed_nodes = {
            n["id"]: n for n in existing_dag.get("nodes", [])
            if n.get("status") == "success"
        }

        # 恢复已完成步骤的结果
        for step_def in task_steps:
            step_index = step_def.get("index", -1)
            node = completed_nodes.get(f"step_{step_index}")
            if not node:
                continue
            # 优先用持久化的真实产出；旧数据无 result 字段时降级到步骤描述
            result_text = node.get("result") or step_def.get("description", step_def.get("desc", ""))
            if result_text:
                step_results.append({
                    "index": step_index,
                    "name": step_def.get("name", f"步骤{step_index}"),
                    "result": result_text[:2000],
                })
                restored += 1
    except Exception as e:
        logger.debug("恢复已完成结果失败: %s", e)

    return restored


def _get_error_suggestion(error: Exception) -> str:
    """根据异常类型返回用户友好的建议。"""
    error_msg = str(error).lower()
    error_type = type(error).__name__

    if "timeout" in error_msg or "timed out" in error_msg:
        return "请求超时，请检查网络连接或稍后重试"
    if "connection" in error_msg or "connect" in error_msg:
        return "网络连接失败，请检查网络设置"
    if "api" in error_msg and ("key" in error_msg or "auth" in error_msg or "unauthorized" in error_msg):
        return "API 密钥无效或已过期，请检查设置"
    if "rate" in error_msg and "limit" in error_msg:
        return "请求频率过高，请稍后重试"
    if "json" in error_msg or "decode" in error_msg:
        return "AI 返回格式异常，已自动重试"
    if error_type == "JSONDecodeError":
        return "AI 返回格式异常，已自动重试"
    if "recursion" in error_msg or "maximum recursion" in error_msg:
        return "任务复杂度超出限制，请简化任务"
    return "执行出错，请重试或联系支持"


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
                # 结构化重试事件：前端可显示"第 N 次重试中..."进度
                yield {
                    "type": "retry",
                    "data": {
                        "index": step.index,
                        "name": step.name,
                        "attempt": attempt,
                        "max_attempts": MAX_EXEC_RETRIES,
                        "wait_seconds": round(wait, 1),
                        "message": f"步骤 {step.name} 第 {attempt} 次重试（{wait:.1f}s 后）",
                    },
                }
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


def _archive_task_results(task_text: str, step_results: list[dict],
                          score: float = 0, task_id: int = 0) -> None:
    """将任务产出归档到知识库（含评分和反馈元数据）。"""
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
            score=score,
            task_id=task_id,
        )
    except Exception as e:
        logger.debug("任务产出归档失败: %s", e)


def _calc_avg_step_score(step_results: list[dict]) -> float:
    """计算步骤结果的平均质量分（基于输出长度和信息密度）。"""
    if not step_results:
        return 0
    scores = []
    for r in step_results:
        text = str(r.get("result", ""))
        if not text:
            continue
        # 简单质量评估：长度适中（50-500字）得分高
        length = len(text.strip())
        if 50 <= length <= 500:
            scores.append(85)
        elif 20 <= length < 50:
            scores.append(60)
        elif length < 20:
            scores.append(30)
        else:
            scores.append(70)
    return sum(scores) / len(scores) if scores else 0


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
