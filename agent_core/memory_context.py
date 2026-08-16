"""记忆上下文构建器：从各 Memory 中检索相关信息，注入 LLM 上下文。

P0 实现：
1. 情景记忆 → 历史相似任务参考
2. 用户画像 → 偏好注入
3. 语义记忆 → 知识库片段
"""
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def build_memory_context(task_text: str, step_name: str = "",
                         task_type: str = "", top_k: int = 2) -> str:
    """构建记忆增强的上下文片段。

    从历史任务、用户偏好、知识库中检索相关信息，
    供 parse() 和 execute_node() 注入 LLM prompt。

    Args:
        task_text: 用户任务文本
        step_name: 当前步骤名（可选，用于更精准检索）
        task_type: 任务类型
        top_k: 各来源返回的最大条数

    Returns:
        格式化的上下文字符串，无记忆时返回空串
    """
    parts: list[str] = []

    # ── 1. 情景记忆：历史相似任务 ──
    history_context = _recall_similar_tasks(task_text, top_k=top_k)
    if history_context:
        parts.append(history_context)

    # ── 2. 用户画像：相关偏好 ──
    pref_context = _recall_user_preferences(task_text, top_k=top_k)
    if pref_context:
        parts.append(pref_context)

    # ── 3. 语义记忆：知识库片段 ──
    kb_context = _recall_knowledge_snippets(task_text, top_k=top_k)
    if kb_context:
        parts.append(kb_context)

    return "\n\n".join(parts)


def _recall_similar_tasks(task_text: str, top_k: int = 2) -> str:
    """检索相似历史任务（情景记忆）。"""
    try:
        from memory_store.sqlite_db import get_conn

        conn = get_conn()
        # 按关键词匹配 + 时间倒序
        keyword = f"%{task_text[:10]}%"  # 用前 10 字做模糊匹配
        rows = conn.execute(
            """SELECT task_content, task_steps, work_score, life_score, cost_time, status
               FROM task_list
               WHERE (task_content LIKE ? OR tags LIKE ?)
                 AND status IN ('done', 'failed')
               ORDER BY create_time DESC LIMIT ?""",
            (keyword, keyword, top_k * 3),
        ).fetchall()
        conn.close()

        if not rows:
            return ""

        # 格式化输出
        lines = ["## 历史参考（类似任务的执行经验）"]
        used = 0
        for r in rows:
            if used >= top_k:
                break
            content = r["task_content"][:60] if r["task_content"] else "未知任务"
            scores = []
            if r["work_score"] and r["work_score"] > 0:
                scores.append(f"工作 {r['work_score']:.0f} 分")
            if r["life_score"] and r["life_score"] > 0:
                scores.append(f"生活 {r['life_score']:.0f} 分")
            score_str = f"（{'，'.join(scores)}）" if scores else ""

            # 提取步骤摘要
            steps_summary = ""
            if r["task_steps"]:
                try:
                    steps = json.loads(r["task_steps"])
                    if steps:
                        step_names = [s.get("name", "") for s in steps[:4] if s.get("name")]
                        if step_names:
                            steps_summary = f"，步骤：{' → '.join(step_names)}"
                except (json.JSONDecodeError, TypeError):
                    pass

            lines.append(f"- 「{content}」{score_str}{steps_summary}")
            used += 1

        return "\n".join(lines) if used > 0 else ""

    except Exception as e:
        logger.debug("情景记忆检索失败: %s", e)
        return ""


def _recall_user_preferences(task_text: str, top_k: int = 3) -> str:
    """检索相关用户偏好（用户画像）。"""
    try:
        from memory_store.sqlite_db import get_conn

        conn = get_conn()
        # 按 pref_key 匹配 + 置信度排序
        keyword = f"%{task_text[:8]}%"
        rows = conn.execute(
            """SELECT pref_key, pref_value, confidence, evidence_count
               FROM user_preference
               WHERE pref_key LIKE ? OR last_evidence LIKE ?
               ORDER BY confidence DESC, evidence_count DESC LIMIT ?""",
            (keyword, keyword, top_k),
        ).fetchall()
        conn.close()

        if not rows:
            return ""

        lines = ["## 您的偏好"]
        for r in rows:
            key = r["pref_key"]
            value = r["pref_value"]
            # 简化显示
            if len(value) > 50:
                value = value[:50] + "..."
            lines.append(f"- {key}: {value}")

        return "\n".join(lines)

    except Exception as e:
        logger.debug("用户偏好检索失败: %s", e)
        return ""


def _recall_knowledge_snippets(task_text: str, top_k: int = 2) -> str:
    """检索知识库相关片段（语义记忆，纯向量检索避免递归）。"""
    try:
        from memory_store.chroma_kb import search

        # 使用纯向量检索（hybrid=False），避免触发 BM25 索引构建导致递归
        results = search(task_text, top_k=top_k, hybrid=False)
        if not results:
            return ""

        lines = ["## 相关知识"]
        seen_texts: set[str] = set()
        for r in results:
            text = r.get("text", "")
            # 去重（文本前 50 字符）
            key = text[:50]
            if key in seen_texts:
                continue
            seen_texts.add(key)

            file_name = r.get("file_name", "")
            source = f"（{file_name}）" if file_name else ""
            # 截取关键片段
            snippet = text[:120].replace("\n", " ")
            lines.append(f"- {snippet}{source}")

        return "\n".join(lines) if len(lines) > 1 else ""

    except Exception as e:
        logger.debug("知识库检索失败: %s", e)
        return ""


def archive_task_output(task_text: str, output_text: str, category: str = "work_doc",
                        file_name: str = "") -> bool:
    """将任务产出归档到知识库（语义记忆扩展）。

    任务完成后调用，将生成的文书（周报、会议纪要等）存入知识库，
    使"上次怎么做的"可被检索。

    Args:
        task_text: 原始任务文本
        output_text: 任务产出的文本内容
        category: 知识库分类
        file_name: 文件名（可选）

    Returns:
        是否成功归档
    """
    if not output_text or len(output_text.strip()) < 20:
        return False

    try:
        from memory_store.chroma_kb import add_document

        if not file_name:
            # 从任务文本生成文件名
            file_name = f"task_output_{task_text[:20]}.md"

        result = add_document(
            file_path=f"task_output://{file_name}",
            text=output_text,
            category=category,
            file_name=file_name,
        )

        if result.get("status") == "ok":
            logger.info("任务产出已归档知识库: %s (%d 切片)", file_name, result.get("chunks", 0))
            return True
        return False

    except Exception as e:
        logger.debug("任务产出归档失败: %s", e)
        return False
