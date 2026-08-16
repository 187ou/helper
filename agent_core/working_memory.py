"""工作记忆：任务执行中的"当前状态"。

解决缺口：当前只有 step_results[-3:]，缺少任务整体目标和已完成部分的语义摘要。

核心能力：
1. 任务目标跟踪（一句话描述最终交付物）
2. 已完成摘要（每步执行后更新）
3. 关键决策记录（已做的选择）
4. 剩余步骤追踪
5. 任务完成后自动归档到情景记忆
"""
import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class WorkingMemory:
    """单任务的工作记忆（任务执行期间维护）。"""

    def __init__(self, task_id: int, task_text: str, steps: list[dict]):
        self.task_id = task_id
        self.task_text = task_text
        self.task_goal = ""  # 任务目标（拆解后生成）
        self.completed_summary = ""  # 已完成部分的语义摘要
        self.remaining_steps = [s.get("name", f"步骤{i}") for i, s in enumerate(steps)]
        self.completed_steps: list[str] = []
        self.key_decisions: list[dict[str, str]] = []  # [{"step": "name", "decision": "xxx"}]
        self.related_preferences: list[str] = []  # 本任务涉及的偏好
        self.created_at = datetime.now().isoformat()
        self.step_results: list[dict] = []

    def update_goal(self, goal: str) -> None:
        """更新任务目标（从拆解结果提取）。"""
        self.task_goal = goal[:200]

    def record_step_completion(self, step_name: str, result: str) -> None:
        """记录步骤完成，更新摘要。"""
        self.completed_steps.append(step_name)
        if step_name in self.remaining_steps:
            self.remaining_steps.remove(step_name)
        self.step_results.append({"name": step_name, "result": result[:500]})

        # 更新已完成摘要（保留最近 3 步的摘要）
        recent = self.step_results[-3:]
        summary_parts = [f"{r['name']}: {r['result'][:100]}" for r in recent]
        self.completed_summary = "; ".join(summary_parts)

    def record_decision(self, step_name: str, decision: str) -> None:
        """记录关键决策。"""
        self.key_decisions.append({
            "step": step_name,
            "decision": decision[:200],
            "time": datetime.now().isoformat(),
        })

    def add_preference(self, pref: str) -> None:
        """记录本任务涉及的偏好。"""
        if pref not in self.related_preferences:
            self.related_preferences.append(pref[:100])

    def get_context_summary(self) -> str:
        """获取工作记忆摘要（注入 prompt 用）。"""
        parts = []
        if self.task_goal:
            parts.append(f"任务目标: {self.task_goal}")
        if self.completed_summary:
            parts.append(f"已完成: {self.completed_summary}")
        if self.remaining_steps:
            parts.append(f"剩余步骤: {' → '.join(self.remaining_steps[:5])}")
        if self.key_decisions:
            recent_decisions = self.key_decisions[-2:]
            dec_str = "; ".join(d["decision"] for d in recent_decisions)
            parts.append(f"关键决策: {dec_str}")
        return "\n".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典（用于持久化）。"""
        return {
            "task_id": self.task_id,
            "task_text": self.task_text,
            "task_goal": self.task_goal,
            "completed_summary": self.completed_summary,
            "remaining_steps": self.remaining_steps,
            "completed_steps": self.completed_steps,
            "key_decisions": self.key_decisions,
            "related_preferences": self.related_preferences,
            "step_results": self.step_results,
        }


# ── 任务级工作记忆管理（内存中，任务结束后可归档）──

_working_memories: dict[int, WorkingMemory] = {}
_MAX_WORKING_MEMORIES = 50  # 最多保留 50 个任务的内存记忆（LRU 淘汰）


def get_working_memory(task_id: int, task_text: str = "",
                       steps: list[dict] | None = None) -> WorkingMemory:
    """获取或创建工作记忆（带 LRU 淘汰防内存泄漏）。"""
    if task_id in _working_memories:
        return _working_memories[task_id]

    # LRU 淘汰：超出限制时删除最早的
    if len(_working_memories) >= _MAX_WORKING_MEMORIES:
        oldest_key = next(iter(_working_memories))
        del _working_memories[oldest_key]
        logger.debug("工作记忆 LRU 淘汰: task #%d", oldest_key)

    wm = WorkingMemory(task_id, task_text or "", steps or [])
    _working_memories[task_id] = wm
    return wm


def clear_working_memory(task_id: int) -> None:
    """清除工作记忆（任务完成后）。"""
    if task_id in _working_memories:
        del _working_memories[task_id]


def cleanup_stale_working_memories(max_age_hours: int = 24) -> int:
    """清理过期的工作记忆（防止长时间运行后内存泄漏）。"""
    now = datetime.now()
    to_remove = []
    for task_id, wm in _working_memories.items():
        try:
            created = datetime.strptime(wm.created_at, "%Y-%m-%d %H:%M:%S")
            if (now - created).total_seconds() > max_age_hours * 3600:
                to_remove.append(task_id)
        except (ValueError, TypeError):
            to_remove.append(task_id)

    for task_id in to_remove:
        del _working_memories[task_id]

    if to_remove:
        logger.info("清理 %d 条过期工作记忆", len(to_remove))
    return len(to_remove)


def archive_working_memory_to_episodic(task_id: int) -> None:
    """任务完成后，将工作记忆归档到情景记忆（持久化到 SQLite）。"""
    wm = _working_memories.get(task_id)
    if not wm:
        return

    try:
        from memory_store.sqlite_db import get_conn
        conn = get_conn()
        try:
            conn.execute(
                """UPDATE task_list SET
                    task_goal = ?,
                    key_decisions = ?,
                    related_preferences = ?
                   WHERE id = ?""",
                (
                    wm.task_goal,
                    json.dumps(wm.key_decisions, ensure_ascii=False),
                    json.dumps(wm.related_preferences, ensure_ascii=False),
                    task_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        # 清理内存
        clear_working_memory(task_id)
        logger.info("工作记忆已归档: task #%d", task_id)
    except Exception as e:
        logger.debug("工作记忆归档失败: %s", e)


def restore_working_memory_from_task(task_id: int) -> WorkingMemory | None:
    """从持久化的任务记录恢复工作记忆（断点续跑时调用）。

    从 task_list 表的 task_goal/key_decisions/related_preferences 字段恢复。
    """
    try:
        from memory_store.sqlite_db import get_conn
        conn = get_conn()
        try:
            row = conn.execute(
                """SELECT task_content, task_goal, key_decisions, related_preferences, task_steps
                   FROM task_list WHERE id = ?""",
                (task_id,),
            ).fetchone()
        finally:
            conn.close()

        if not row:
            return None

        # 恢复步骤列表
        steps = []
        if row["task_steps"]:
            try:
                steps = json.loads(row["task_steps"])
            except (json.JSONDecodeError, TypeError):
                steps = []

        # 创建工作记忆
        wm = WorkingMemory(task_id, row["task_content"] or "", steps)

        # 恢复字段
        if row["task_goal"]:
            wm.task_goal = row["task_goal"]

        if row["key_decisions"]:
            try:
                wm.key_decisions = json.loads(row["key_decisions"])
            except (json.JSONDecodeError, TypeError):
                pass

        if row["related_preferences"]:
            try:
                wm.related_preferences = json.loads(row["related_preferences"])
            except (json.JSONDecodeError, TypeError):
                pass

        # 恢复已完成步骤（从 DAG 状态推断）
        # 注意：这里无法完全恢复 step_results，但至少恢复了元信息
        for step in steps:
            step_name = step.get("name", "")
            if step_name and step_name not in wm.remaining_steps:
                wm.completed_steps.append(step_name)

        # 存入内存缓存
        _working_memories[task_id] = wm
        logger.info("工作记忆已恢复: task #%d（已完成 %d 步）", task_id, len(wm.completed_steps))
        return wm
    except Exception as e:
        logger.debug("工作记忆恢复失败: %s", e)
        return None
