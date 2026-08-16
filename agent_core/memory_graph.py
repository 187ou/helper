"""关联记忆：记忆之间的互相引用。

解决缺口：当前记忆是独立的碎片，无法做到"这张照片让我想起那次旅行"。

核心能力：
1. 记忆节点：每条记忆是一个节点（情景/知识/偏好/程序性）
2. 关联边：记忆之间的关系（引用/因果/相似/时序）
3. 关联检索：找到一条记忆时，自动关联相关记忆
4. 关联发现：自动发现记忆之间的隐含关系
"""
import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


# ── 关联类型 ──
RELATION_TYPES = {
    "references": "引用",       # 记忆 A 引用了记忆 B
    "causes": "导致",           # 记忆 A 导致了记忆 B
    "similar_to": "相似于",     # 记忆 A 与记忆 B 相似
    "follows": "时序跟随",      # 记忆 A 在记忆 B 之前/之后发生
    "belongs_to": "属于",       # 记忆 A 属于某个项目/主题
    "derived_from": "派生自",   # 记忆 A 从记忆 B 派生
    "conflicts_with": "冲突于", # 记忆 A 与记忆 B 冲突
}


def create_link(source_type: str, source_key: str,
                target_type: str, target_key: str,
                relation: str, strength: float = 0.5,
                note: str = "") -> bool:
    """创建记忆之间的关联。

    Args:
        source_type: 源记忆类型
        source_key: 源记忆标识
        target_type: 目标记忆类型
        target_key: 目标记忆标识
        relation: 关联类型
        strength: 关联强度 0-1
        note: 关联说明

    Returns:
        是否成功
    """
    try:
        from memory_store.sqlite_db import get_conn

        conn = get_conn()
        try:
            conn.execute(
                """INSERT INTO memory_link
                   (source_type, source_key, target_type, target_key,
                    relation, strength, note, create_time)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (source_type, source_key, target_type, target_key,
                 relation, strength, note[:200],
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            conn.commit()
            return True
        finally:
            conn.close()
    except Exception as e:
        logger.debug("关联创建失败: %s", e)
        return False


def get_related_memories(memory_type: str, memory_key: str,
                         max_depth: int = 2, min_strength: float = 0.3) -> list[dict]:
    """获取与指定记忆关联的所有记忆（支持多跳）。

    Args:
        memory_type: 记忆类型
        memory_key: 记忆标识
        max_depth: 最大检索深度（1=直接关联，2=间接关联）
        min_strength: 最低关联强度

    Returns:
        关联记忆列表，按关联强度排序
    """
    try:
        from memory_store.sqlite_db import get_conn

        conn = get_conn()
        try:
            # 1. 直接关联（source 或 target 匹配）
            rows = conn.execute(
                """SELECT * FROM memory_link
                   WHERE (source_type = ? AND source_key = ?)
                      OR (target_type = ? AND target_key = ?)
                   AND strength >= ?
                   ORDER BY strength DESC LIMIT 20""",
                (memory_type, memory_key, memory_type, memory_key, min_strength),
            ).fetchall()

            related = []
            visited = {(memory_type, memory_key)}

            for row in rows:
                # 确定关联的另一端
                if row["source_type"] == memory_type and row["source_key"] == memory_key:
                    other_type, other_key = row["target_type"], row["target_key"]
                else:
                    other_type, other_key = row["source_type"], row["source_key"]

                if (other_type, other_key) in visited:
                    continue
                visited.add((other_type, other_key))

                related.append({
                    "memory_type": other_type,
                    "memory_key": other_key,
                    "relation": row["relation"],
                    "relation_label": RELATION_TYPES.get(row["relation"], row["relation"]),
                    "strength": row["strength"],
                    "note": row["note"],
                    "depth": 1,
                })

                # 2. 间接关联（第二跳）
                if max_depth >= 2:
                    indirect_rows = conn.execute(
                        """SELECT * FROM memory_link
                           WHERE (source_type = ? AND source_key = ?)
                              OR (target_type = ? AND target_key = ?)
                           AND strength >= ?
                           LIMIT 10""",
                        (other_type, other_key, other_type, other_key, min_strength),
                    ).fetchall()

                    for irow in indirect_rows:
                        if irow["source_type"] == other_type and irow["source_key"] == other_key:
                            i_type, i_key = irow["target_type"], irow["target_key"]
                        else:
                            i_type, i_key = irow["source_type"], irow["source_key"]

                        if (i_type, i_key) in visited:
                            continue
                        visited.add((i_type, i_key))

                        related.append({
                            "memory_type": i_type,
                            "memory_key": i_key,
                            "relation": irow["relation"],
                            "relation_label": RELATION_TYPES.get(irow["relation"], irow["relation"]),
                            "strength": round(irow["strength"] * 0.7, 2),  # 间接关联衰减
                            "note": irow["note"],
                            "depth": 2,
                        })

            # 按强度排序
            related.sort(key=lambda x: x["strength"], reverse=True)
            return related
        finally:
            conn.close()
    except Exception as e:
        logger.debug("关联检索失败: %s", e)
        return []


def delete_links_for_memory(memory_type: str, memory_key: str) -> int:
    """删除指定记忆的所有关联（记忆删除时调用）。

    Args:
        memory_type: 记忆类型
        memory_key: 记忆标识

    Returns:
        删除的关联数量
    """
    try:
        from memory_store.sqlite_db import get_conn

        conn = get_conn()
        try:
            result = conn.execute(
                """DELETE FROM memory_link
                   WHERE (source_type = ? AND source_key = ?)
                      OR (target_type = ? AND target_key = ?)""",
                (memory_type, memory_key, memory_type, memory_key),
            )
            conn.commit()
            deleted = result.rowcount
            if deleted > 0:
                logger.debug("删除 %d 条关联: %s:%s", deleted, memory_type, memory_key)
            return deleted
        finally:
            conn.close()
    except Exception as e:
        logger.debug("关联删除失败: %s", e)
        return 0


def delete_links_for_task(task_id: int) -> int:
    """删除任务的所有关联（任务删除时调用）。"""
    return delete_links_for_memory("episodic", f"task_{task_id}")


def auto_discover_links(task_text: str, task_type: str, task_id: int) -> int:
    """自动发现并创建记忆关联（任务完成后调用）。

    Args:
        task_text: 任务文本
        task_type: 任务类型
        task_id: 任务 ID

    Returns:
        创建的关联数量
    """
    created = 0
    try:
        from memory_store.sqlite_db import get_conn

        conn = get_conn()
        try:
            # 1. 与知识库关联（任务文本匹配知识库文档）
            kb_rows = conn.execute(
                """SELECT file_name, file_path FROM kb_file_index
                   WHERE file_name != '' LIMIT 50"""
            ).fetchall()

            for kb in kb_rows:
                if kb["file_name"] and kb["file_name"] in task_text:
                    if create_link("episodic", f"task_{task_id}",
                                   "semantic", kb["file_path"],
                                   "references", 0.7, f"任务引用了知识库文档 {kb['file_name']}"):
                        created += 1

            # 2. 与偏好关联（任务类型匹配偏好）
            pref_rows = conn.execute(
                "SELECT pref_key FROM user_preference WHERE pref_key LIKE ?",
                (f"type:{task_type}:%",),
            ).fetchall()

            for pref in pref_rows:
                if create_link("episodic", f"task_{task_id}",
                               "preference", pref["pref_key"],
                               "derived_from", 0.5):
                    created += 1

            # 3. 时序关联（与最近的同类型任务关联）
            recent_rows = conn.execute(
                """SELECT id FROM task_list
                   WHERE task_type = ? AND id != ?
                   ORDER BY create_time DESC LIMIT 3""",
                (task_type, task_id),
            ).fetchall()

            for recent in recent_rows:
                if create_link("episodic", f"task_{task_id}",
                               "episodic", f"task_{recent['id']}",
                               "follows", 0.4):
                    created += 1

        finally:
            conn.close()

        if created > 0:
            logger.debug("自动创建 %d 条记忆关联: task #%d", created, task_id)
    except Exception as e:
        logger.debug("自动关联发现失败: %s", e)

    return created


def get_memory_context_expanded(memory_type: str, memory_key: str,
                                include_related: bool = True) -> str:
    """获取记忆及其关联记忆的上下文（用于 prompt 注入）。

    Args:
        memory_type: 记忆类型
        memory_key: 记忆标识
        include_related: 是否包含关联记忆

    Returns:
        格式化的上下文字符串
    """
    parts = []

    if not include_related:
        return ""

    related = get_related_memories(memory_type, memory_key, max_depth=2)
    if not related:
        return ""

    # 按关联类型分组
    by_relation = {}
    for r in related:
        rel = r["relation_label"]
        if rel not in by_relation:
            by_relation[rel] = []
        by_relation[rel].append(r)

    for rel_label, items in by_relation.items():
        parts.append(f"## 关联记忆（{rel_label}）")
        for item in items[:3]:
            key_display = item["memory_key"][:50]
            parts.append(f"- [{item['memory_type']}] {key_display}（强度 {item['strength']:.0%}）")

    return "\n".join(parts) if parts else ""
