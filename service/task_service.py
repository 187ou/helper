"""任务管理服务：全生命周期 CRUD + 状态机 + 关联文档。"""
import json
import logging
from datetime import datetime
from typing import Any

from memory_store.sqlite_db import get_conn, now_str

logger = logging.getLogger(__name__)

# ── 状态机 ──
VALID_STATUSES = {"todo", "doing", "done", "failed", "archived", "shelved"}

# 允许的状态流转（空集合 = 终态，禁止任何流出）
TRANSITIONS: dict[str, set[str]] = {
    "todo": {"doing", "shelved", "done", "failed"},
    "doing": {"done", "failed", "shelved", "todo"},
    "done": {"doing", "archived", "shelved"},
    "failed": {"doing", "todo", "shelved"},  # 失败后可重试
    "archived": set(),  # 终态
    "shelved": {"todo", "doing"},  # 搁置后可恢复
}

VALID_PRIORITIES = {"high", "medium", "low"}
VALID_TYPES = {"work", "life", "health", "mix"}


def list_tasks(
    status: str = "",
    task_type: str = "",
    priority: str = "",
    keyword: str = "",
    limit: int = 100,
) -> list[dict[str, Any]]:
    """列出任务，支持多维过滤。"""
    sql = "SELECT * FROM task_list WHERE 1=1"
    params: list = []

    if status:
        sql += " AND status = ?"
        params.append(status)
    if task_type:
        sql += " AND task_type = ?"
        params.append(task_type)
    if priority:
        sql += " AND priority = ?"
        params.append(priority)
    if keyword:
        sql += " AND (task_content LIKE ? OR tags LIKE ?)"
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    sql += " ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, create_time DESC LIMIT ?"
    params.append(limit)

    conn = get_conn()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_row_to_task(r) for r in rows]


def get_task(task_id: int) -> dict[str, Any] | None:
    """获取单个任务。"""
    conn = get_conn()
    row = conn.execute("SELECT * FROM task_list WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return _row_to_task(row) if row else None


def create_task(
    content: str,
    task_type: str = "work",
    priority: str = "medium",
    tags: str = "",
    deadline: str = "",
    related_doc: str = "",
    steps: list | None = None,
    source: str = "manual",
) -> dict[str, Any]:
    """创建任务。"""
    if not content.strip():
        raise ValueError("任务内容不能为空")
    if task_type not in VALID_TYPES:
        task_type = "work"
    if priority not in VALID_PRIORITIES:
        priority = "medium"

    conn = get_conn()
    cursor = conn.execute(
        """INSERT INTO task_list
           (task_type, task_content, task_steps, status, tags, priority, deadline, related_doc, source)
           VALUES (?, ?, ?, 'todo', ?, ?, ?, ?, ?)""",
        (
            task_type, content.strip(),
            json.dumps(steps or [], ensure_ascii=False),
            tags.strip(), priority, deadline.strip(), related_doc.strip(), source,
        ),
    )
    conn.commit()
    tid = cursor.lastrowid
    conn.close()
    logger.info("创建任务 #%d: %s", tid, content[:50])
    return get_task(tid)


def update_task(task_id: int, **kwargs) -> dict[str, Any] | None:
    """更新任务字段。"""
    allowed = {"task_content", "tags", "priority", "deadline", "related_doc",
               "task_type", "task_steps", "dag_json", "status"}
    fields = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not fields:
        return get_task(task_id)

    if "task_steps" in fields and isinstance(fields["task_steps"], list):
        fields["task_steps"] = json.dumps(fields["task_steps"], ensure_ascii=False)
    if "priority" in fields and fields["priority"] not in VALID_PRIORITIES:
        fields["priority"] = "medium"
    if "task_type" in fields and fields["task_type"] not in VALID_TYPES:
        fields["task_type"] = "work"
    if "status" in fields and fields["status"] not in VALID_STATUSES:
        logger.warning("忽略无效状态: %s", fields.pop("status", None))
        fields.pop("status", None)
        if not fields:
            return get_task(task_id)

    fields["update_time"] = now_str()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [task_id]

    conn = get_conn()
    conn.execute(f"UPDATE task_list SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()
    logger.info("更新任务 #%d: %s", task_id, list(fields.keys()))
    return get_task(task_id)


def change_status(task_id: int, new_status: str) -> dict[str, Any] | None:
    """状态流转（带校验）。"""
    if new_status not in VALID_STATUSES:
        raise ValueError(f"无效状态: {new_status}")

    task = get_task(task_id)
    if not task:
        return None

    current = task["status"]
    if current == new_status:
        return task

    # 校验流转合法性（空集合 = 终态，禁止任何流出）
    allowed_targets = TRANSITIONS.get(current)
    if allowed_targets is None:
        raise ValueError(f"未知当前状态: {current}")
    if new_status not in allowed_targets:
        raise ValueError(f"不允许的状态流转: {current} → {new_status}")

    conn = get_conn()
    conn.execute(
        "UPDATE task_list SET status = ?, update_time = ? WHERE id = ?",
        (new_status, now_str(), task_id),
    )
    conn.commit()
    conn.close()
    logger.info("任务 #%d 状态: %s → %s", task_id, current, new_status)
    return get_task(task_id)


def delete_task(task_id: int) -> bool:
    """删除任务。"""
    conn = get_conn()
    conn.execute("DELETE FROM task_list WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    logger.info("删除任务 #%d", task_id)
    return True


def get_statistics() -> dict[str, Any]:
    """看板统计数据。"""
    conn = get_conn()
    today = datetime.now().strftime("%Y-%m-%d")

    total = conn.execute("SELECT COUNT(*) FROM task_list WHERE status <> 'archived'").fetchone()[0]
    todo = conn.execute("SELECT COUNT(*) FROM task_list WHERE status = 'todo'").fetchone()[0]
    doing = conn.execute("SELECT COUNT(*) FROM task_list WHERE status = 'doing'").fetchone()[0]
    done = conn.execute("SELECT COUNT(*) FROM task_list WHERE status = 'done'").fetchone()[0]
    archived = conn.execute("SELECT COUNT(*) FROM task_list WHERE status = 'archived'").fetchone()[0]

    # 今日到期
    due_today = conn.execute(
        "SELECT COUNT(*) FROM task_list WHERE deadline LIKE ? AND status NOT IN ('done', 'archived')",
        (f"{today}%",),
    ).fetchone()[0]

    # 分类统计
    by_type = {}
    for row in conn.execute(
        "SELECT task_type, COUNT(*) as cnt FROM task_list WHERE status <> 'archived' GROUP BY task_type"
    ):
        by_type[row["task_type"]] = row["cnt"]

    conn.close()

    completion_rate = (done / (done + todo + doing) * 100) if (done + todo + doing) > 0 else 0

    return {
        "total": total,
        "todo": todo,
        "doing": doing,
        "done": done,
        "archived": archived,
        "due_today": due_today,
        "completion_rate": round(completion_rate, 1),
        "by_type": by_type,
    }


def get_dag(task_id: int) -> dict[str, Any] | None:
    """获取任务的 DAG 数据。"""
    task = get_task(task_id)
    if not task:
        return None
    dag_json = task.get("dag_json", "")
    if dag_json:
        try:
            return json.loads(dag_json)
        except json.JSONDecodeError:
            pass
    # 无持久化 DAG 时，从 task_steps 构建
    steps = json.loads(task.get("task_steps", "[]")) if task.get("task_steps") else []
    if not steps:
        return None
    return _build_dag_from_steps(steps)


def save_dag(task_id: int, dag_data: dict) -> None:
    """保存 DAG 数据。"""
    conn = get_conn()
    conn.execute(
        "UPDATE task_list SET dag_json = ?, update_time = ? WHERE id = ?",
        (json.dumps(dag_data, ensure_ascii=False), now_str(), task_id),
    )
    conn.commit()
    conn.close()


def _build_dag_from_steps(steps: list[dict]) -> dict[str, Any]:
    """从步骤列表构建 DAG 结构（节点+边），正确处理并行节点。"""
    from agent_core.graph_builder import build_dag
    return build_dag(steps)


def _row_to_task(row) -> dict[str, Any]:
    """数据库行转任务字典。"""
    d = dict(row)
    # 解析 JSON 字段
    for key in ("task_steps",):
        if d.get(key):
            try:
                d[key] = json.loads(d[key])
            except (json.JSONDecodeError, TypeError):
                d[key] = []
        else:
            d[key] = []
    return d
