"""异步演化闭环：不阻塞主任务执行。

核心能力：
1. 线程池执行演化逻辑（主任务立即返回）
2. 任务队列 + 工作线程（顺序处理，避免并发写冲突）
3. 超时控制（演化逻辑有执行上限）
4. 错误隔离（演化失败不影响主任务）
5. 状态追踪（可查询演化执行状态）

设计：
- 使用 Queue + Thread 实现生产者-消费者模式
- 主任务生产"演化任务"到队列
- 工作线程消费并执行演化逻辑
- 单线程消费避免 SQLite 并发写冲突
"""
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future, TimeoutError
from dataclasses import dataclass, field
from datetime import datetime
from queue import Queue, Empty
from typing import Any, Callable, Optional

from config.app_const import TaskStatus

logger = logging.getLogger(__name__)

# ── 配置 ──
ASYNC_CONFIG = {
    "evolution_timeout": 30,        # 单次演化超时（秒）
    "max_queue_size": 100,          # 队列最大长度
    "worker_count": 1,              # 工作线程数（单线程避免写冲突）
    "retry_count": 2,               # 失败重试次数
    "retry_delay": 1.0,             # 重试间隔（秒）
}


@dataclass
class EvolutionTask:
    """演化任务。"""
    task_text: str
    result: dict[str, Any]
    created_at: float = field(default_factory=time.time)
    retry_count: int = 0
    status: str = "pending"  # pending / running / done / failed
    error: str = ""
    duration: float = 0.0


class AsyncEvolutionLoop:
    """异步演化闭环执行器。

    使用方式：
        async_loop = AsyncEvolutionLoop()
        async_loop.start()
        async_loop.submit(task_text, result)  # 非阻塞
        async_loop.shutdown()  # 关闭时调用
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        # 单例模式（全局唯一工作线程）
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._queue: Queue[EvolutionTask] = Queue(maxsize=ASYNC_CONFIG["max_queue_size"])
        self._executor: Optional[ThreadPoolExecutor] = None
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False
        self._stats = {
            "total_submitted": 0,
            "total_executed": 0,
            "total_failed": 0,
            "total_timeout": 0,
        }
        self._stats_lock = threading.Lock()

    def start(self) -> None:
        """启动工作线程。"""
        if self._running:
            return
        self._running = True
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="EvolutionWorker",
            daemon=True,
        )
        self._worker_thread.start()
        logger.info("异步演化工作线程启动")

    def shutdown(self, wait: bool = True, timeout: float = 30) -> None:
        """关闭工作线程。"""
        self._running = False
        if wait and self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout)
        logger.info("异步演化工作线程关闭")

    def submit(self, task_text: str, result: dict[str, Any]) -> bool:
        """提交演化任务（非阻塞）。

        Returns:
            是否成功入队
        """
        if not self._running:
            logger.warning("演化工作线程未运行，跳过")
            return False

        evo_task = EvolutionTask(
            task_text=task_text,
            result=result,
        )

        try:
            self._queue.put_nowait(evo_task)
            with self._stats_lock:
                self._stats["total_submitted"] += 1
            logger.debug("演化任务入队: %s", task_text[:30])
            return True
        except Exception:
            logger.warning("演化队列已满，跳过: %s", task_text[:30])
            return False

    def get_stats(self) -> dict[str, Any]:
        """获取执行统计。"""
        with self._stats_lock:
            return dict(self._stats)

    @property
    def queue_size(self) -> int:
        """当前队列长度。"""
        return self._queue.qsize()

    # ── 内部实现 ──

    def _worker_loop(self) -> None:
        """工作线程主循环。"""
        while self._running:
            try:
                evo_task = self._queue.get(timeout=1.0)
            except Empty:
                continue

            self._execute_with_retry(evo_task)

    def _execute_with_retry(self, evo_task: EvolutionTask) -> None:
        """带重试的执行。"""
        max_retries = ASYNC_CONFIG["retry_count"]

        for attempt in range(max_retries + 1):
            evo_task.status = "running"
            start_time = time.time()

            try:
                # 在线程池中执行（带超时）
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(self._execute_evolution, evo_task)
                    future.result(timeout=ASYNC_CONFIG["evolution_timeout"])

                evo_task.status = "done"
                evo_task.duration = time.time() - start_time
                with self._stats_lock:
                    self._stats["total_executed"] += 1
                logger.debug("演化完成: %s (%.2fs)", evo_task.task_text[:30], evo_task.duration)
                return

            except TimeoutError:
                evo_task.status = "failed"
                evo_task.error = "timeout"
                with self._stats_lock:
                    self._stats["total_timeout"] += 1
                logger.warning("演化超时: %s", evo_task.task_text[:30])
                return  # 超时不重试

            except Exception as e:
                evo_task.retry_count += 1
                if evo_task.retry_count <= max_retries:
                    logger.warning("演化失败，重试 %d/%d: %s",
                                   evo_task.retry_count, max_retries, e)
                    time.sleep(ASYNC_CONFIG["retry_delay"])
                else:
                    evo_task.status = "failed"
                    evo_task.error = str(e)[:200]
                    with self._stats_lock:
                        self._stats["total_failed"] += 1
                    logger.error("演化最终失败: %s", e)
                    return

    def _execute_evolution(self, evo_task: EvolutionTask) -> None:
        """执行演化闭环（在线程中）。"""
        task_text = evo_task.task_text
        result = evo_task.result

        # 补全字段
        from evolution_core.safe_ops import validate_task_result
        result = validate_task_result(result)

        # 1. 打分
        from evolution_core.judge_score import score_task
        detailed_scores = score_task(result, result.get("task_type", "work"))
        score = detailed_scores.get("overall", 60)

        task_type = result.get("task_type", "work")
        success = result.get("status") == TaskStatus.SUCCESS.value
        duration = result.get("cost_time", 0)

        # 2. 权重迭代
        try:
            from evolution_core.weight_evolve import evolve_from_task
            evolve_from_task(task_text, score, task_type, success, duration)
        except Exception as e:
            logger.warning("权重迭代异常: %s", e)

        # 3. 模式学习
        try:
            from evolution_core.pattern_miner import learn_from_task
            learn_from_task(task_text, result.get("steps", []), score, duration, success)
        except Exception as e:
            logger.warning("模式学习异常: %s", e)

        # 3.5 模式使用反馈：如果本次任务使用了演化推荐，强化对应模式
        try:
            from evolution_core.pattern_miner import get_top_patterns
            used_steps = result.get("steps", [])
            if used_steps and len(used_steps) >= 2:
                # 查找与本次步骤序列最匹配的模式并记录使用
                _reinforce_used_pattern(task_text, task_type, used_steps, score, duration, success)
        except Exception as e:
            logger.debug("模式强化跳过: %s", e)

        # 4. 流程优化 → 反馈到模式库
        try:
            from service.evolution_config_service import get_config
            if get_config("enable_auto_optimize") and len(result.get("steps", [])) > 2:
                from evolution_core.flow_optimize import optimize
                from evolution_core.evo_log import log_flow_optimize
                old_steps = result["steps"]
                optimized = optimize(old_steps)
                if len(optimized) < len(old_steps):
                    log_flow_optimize(old_steps, optimized)
                    # 关键反馈：将优化后的流程保存为可复用模式
                    _save_optimized_as_pattern(task_text, task_type, old_steps, optimized, score)
        except Exception as e:
            logger.warning("流程优化异常: %s", e)

        # 5. 模板固化
        try:
            from service.evolution_config_service import get_config
            if get_config("enable_template_save"):
                from evolution_core.template_save import check_and_save_template
                from evolution_core.evo_log import log_template_save
                tpl = check_and_save_template(task_text, result.get("steps", []))
                if tpl:
                    log_template_save(tpl["name"], tpl["freq"])
        except Exception as e:
            logger.warning("模板固化异常: %s", e)


def _save_optimized_as_pattern(task_text: str, task_type: str, old_steps: list[dict],
                                optimized_steps: list[dict], score: float) -> None:
    """将优化后的流程保存为模式（优化→复用反馈）。

    当流程被精简优化后，将优化结果存入 pattern 库，
    下次同类任务可直接使用优化后的流程，而非原始冗余流程。
    """
    try:
        from evolution_core.pattern_miner import learn_from_task
        # 用优化后的步骤作为新模板学习（标记为优化来源）
        learn_from_task(
            task_text=f"[optimized] {task_text}",
            steps=optimized_steps,
            score=min(score + 5, 100),  # 优化流程略有加分
            duration=0,
            success=True,
        )
        logger.info("优化流程已存入模式库: %d 步 → %d 步", len(old_steps), len(optimized_steps))
    except Exception as e:
        logger.debug("优化流程存模式失败: %s", e)


def _reinforce_used_pattern(task_text: str, task_type: str, used_steps: list[dict],
                            score: float, duration: float, success: bool) -> None:
    """强化与本次任务匹配的模式（使用反馈闭环）。

    当任务实际使用了某个演化推荐的模式时，记录使用以强化该模式的置信度，
    使下次同类任务更容易命中该模式。
    """
    from evolution_core.pattern_miner import get_top_patterns, record_pattern_usage
    from evolution_core.safe_ops import safe_json_loads

    step_names = [s.get("name", "") for s in used_steps if s.get("name")]
    if len(step_names) < 2:
        return

    # 查找最匹配的模式
    patterns = get_top_patterns(n=20, min_confidence=0.3)
    best_key = None
    best_overlap = 0

    for p in patterns:
        p_steps = safe_json_loads(p.get("step_template"), default=[])
        if not p_steps:
            continue
        # 计算步骤名重叠度
        overlap = len(set(step_names) & set(p_steps))
        if overlap > best_overlap:
            best_overlap = overlap
            best_key = p.get("pattern_key")

    if best_key and best_overlap >= 2:
        record_pattern_usage(best_key, score, duration, success)
        logger.debug("模式强化: %s (重叠 %d 步)", best_key, best_overlap)


# ── 全局实例 ──

_global_loop: Optional[AsyncEvolutionLoop] = None


def get_async_loop() -> AsyncEvolutionLoop:
    """获取全局异步演化实例。"""
    global _global_loop
    if _global_loop is None:
        _global_loop = AsyncEvolutionLoop()
    return _global_loop


def start_async_evolution() -> None:
    """启动异步演化。"""
    loop = get_async_loop()
    loop.start()


def submit_evolution(task_text: str, result: dict[str, Any]) -> bool:
    """提交演化任务（便捷函数）。"""
    loop = get_async_loop()
    return loop.submit(task_text, result)


def shutdown_async_evolution() -> None:
    """关闭异步演化。"""
    global _global_loop
    if _global_loop:
        _global_loop.shutdown()
        _global_loop = None
