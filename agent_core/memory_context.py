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
    """构建记忆增强的上下文片段（按重要性排序）。

    从历史任务、用户偏好、知识库中检索相关信息，
    供 parse() 和 execute_node() 注入 LLM prompt。

    排序规则（重要性从高到低）：
    1. 用户偏好（直接指导输出风格）
    2. 历史参考（类似任务经验）
    3. 知识片段（相关领域知识）

    Args:
        task_text: 用户任务文本
        step_name: 当前步骤名（可选，用于更精准检索）
        task_type: 任务类型
        top_k: 各来源返回的最大条数

    Returns:
        格式化的上下文字符串，无记忆时返回空串
    """
    parts: list[tuple[str, int]] = []  # (内容, 重要性排序)

    # ── 1. 用户画像：相关偏好（重要性最高 = 1）──
    pref_context = _recall_user_preferences(task_text, top_k=top_k)
    if pref_context:
        parts.append((pref_context, 1))

    # ── 2. 情景记忆：语义检索 + 字符串检索（合并去重）──
    # 语义检索（向量相似度）
    semantic_history = _recall_similar_tasks_semantic(task_text, top_k=top_k)
    # 字符串检索（兜底）
    keyword_history = _recall_similar_tasks(task_text, top_k=top_k)

    # 合并去重：两者都有时合并，只取其一
    if semantic_history and keyword_history:
        # 合并：取语义结果 + 字符串结果中不重复的部分
        merged = _merge_history_results(semantic_history, keyword_history, top_k)
        if merged:
            parts.append((merged, 2))
    elif semantic_history:
        parts.append((semantic_history, 2))
    elif keyword_history:
        parts.append((keyword_history, 2))

    # ── 3. 语义记忆：知识库片段（重要性低 = 3）──
    kb_context = _recall_knowledge_snippets(task_text, top_k=top_k)
    if kb_context:
        parts.append((kb_context, 3))

    # 按重要性排序
    parts.sort(key=lambda x: x[1])

    return "\n\n".join(p[0] for p in parts)


def _merge_history_results(semantic: str, keyword: str, top_k: int) -> str:
    """合并语义检索和字符串检索结果（去重）。"""
    # 提取各自的任务摘要行
    semantic_lines = [l for l in semantic.split("\n") if l.startswith("- ")]
    keyword_lines = [l for l in keyword.split("\n") if l.startswith("- ")]

    # 去重：基于任务内容前缀
    seen = set()
    merged = ["## 历史参考"]
    for line in semantic_lines + keyword_lines:
        # 提取任务内容作为去重 key
        content_start = line.find("「")
        content_end = line.find("」")
        if content_start > 0 and content_end > content_start:
            key = line[content_start:content_end + 1]
        else:
            key = line[:40]
        if key not in seen and len(merged) <= top_k + 1:
            seen.add(key)
            merged.append(line)

    return "\n".join(merged) if len(merged) > 1 else ""


def _recall_similar_tasks_semantic(task_text: str, top_k: int = 2) -> str:
    """语义检索相似历史任务（向量相似度 + 评分时间加权）。

    与 _recall_similar_tasks() 互补：
    - 语义检索：捕捉语义相似但关键词不同的任务
    - 字符串检索：精确匹配关键词
    """
    try:
        from memory_store.episodic_index import search_similar_tasks

        results = search_similar_tasks(task_text, top_k=top_k, min_score=0.3)
        if not results:
            return ""

        lines = ["## 历史参考（语义匹配）"]
        for r in results:
            content = r["text"][:60] if r["text"] else "未知任务"
            sim = r.get("similarity", 0)
            score = r.get("score", 0)
            score_str = f"（相似度 {sim:.0%}"
            if score > 0:
                score_str += f"，{score:.0f} 分"
            score_str += "）"
            lines.append(f"- 「{content}」{score_str}")

        return "\n".join(lines)
    except Exception as e:
        logger.debug("情景记忆语义检索失败: %s", e)
        return ""


def _recall_similar_tasks(task_text: str, top_k: int = 2) -> str:
    """检索相似历史任务（情景记忆）——评分+时间加权排序。

    改进：
    1. 多关键词匹配（不再只用前 10 字）
    2. 综合得分排序：评分权重 0.5 + 时间衰减权重 0.3 + 完成度权重 0.2
    3. 优先返回高分、近期、已完成的任务
    """
    try:
        from memory_store.sqlite_db import get_conn
        from datetime import datetime, timedelta

        # 提取多个关键词（避免前 10 字相同的问题）
        keywords = _extract_search_keywords(task_text)
        if not keywords:
            return ""

        # 构建动态 WHERE 条件（匹配任意关键词）
        conditions = " OR ".join(["(task_content LIKE ? OR tags LIKE ?)"] * len(keywords))
        params = []
        for kw in keywords:
            params.extend([f"%{kw}%", f"%{kw}%"])

        conn = get_conn()
        rows = conn.execute(
            f"""SELECT task_content, task_steps, work_score, life_score, cost_time, status, create_time
                FROM task_list
                WHERE {conditions}
                  AND status IN ('done', 'failed')
                LIMIT ?""",
            params + [top_k * 5],  # 多取一些用于排序筛选
        ).fetchall()
        conn.close()

        if not rows:
            return ""

        # 评分+时间加权排序
        now = datetime.now()
        scored_rows = []
        for r in rows:
            # 评分维度 (0-100)
            score_val = max(r["work_score"] or 0, r["life_score"] or 0)
            score_weight = score_val / 100.0  # 0-1

            # 时间衰减（越近越好）
            try:
                task_time = datetime.strptime(r["create_time"], "%Y-%m-%d %H:%M:%S")
                days_ago = (now - task_time).days
                time_weight = max(0, 1 - days_ago / 90)  # 90 天后衰减到 0
            except (ValueError, TypeError):
                time_weight = 0.5

            # 完成度（成功 > 失败）
            completeness = 1.0 if r["status"] == "done" else 0.5

            # 综合得分
            final_score = score_weight * 0.5 + time_weight * 0.3 + completeness * 0.2

            scored_rows.append((final_score, r))

        # 按综合得分排序
        scored_rows.sort(key=lambda x: x[0], reverse=True)

        # 格式化输出 top_k
        lines = ["## 历史参考"]
        for i, (score, r) in enumerate(scored_rows[:top_k]):
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

        return "\n".join(lines) if len(lines) > 1 else ""

    except Exception as e:
        logger.debug("情景记忆检索失败: %s", e)
        return ""


def check_proactive_reminder(task_text: str) -> str | None:
    """检查是否需要主动提醒用户回忆（基于时间衰减）。

    当用户长期未执行某类任务时，主动提醒回忆上次经验。

    Args:
        task_text: 当前任务文本

    Returns:
        提醒文本，不需要提醒时返回 None
    """
    try:
        from memory_store.sqlite_db import get_conn
        from datetime import datetime, timedelta
        from evolution_core.weight_evolve import _HABIT_PATTERNS

        # 识别任务对应的习惯类型
        habit_key = None
        for habit_type, patterns in _HABIT_PATTERNS.items():
            for key, keywords in patterns.items():
                for kw in keywords:
                    if kw in task_text:
                        habit_key = key
                        break
                if habit_key:
                    break
            if habit_key:
                break

        if not habit_key:
            return None

        # 查询该习惯最近一次执行时间
        keyword = f"%{habit_key}%"
        conn = get_conn()
        try:
            row = conn.execute(
                """SELECT MAX(create_time) as last_time FROM task_list
                   WHERE (task_content LIKE ? OR tags LIKE ?)
                     AND status IN ('done', 'success')""",
                (keyword, keyword),
            ).fetchone()
        finally:
            conn.close()

        if not row or not row["last_time"]:
            return None

        try:
            last_time = datetime.strptime(row["last_time"], "%Y-%m-%d %H:%M:%S")
            days_ago = (datetime.now() - last_time).days
        except (ValueError, TypeError):
            return None

        # 超过 14 天未执行，触发提醒
        if days_ago >= 14:
            return f"提示：您 {days_ago} 天未做{habit_key}了，上次经验可供参考"

        return None

    except Exception as e:
        logger.debug("主动回忆检查失败: %s", e)
        return None


def compress_memory_summary(max_tokens: int = 300) -> str:
    """压缩记忆摘要（用于上下文窗口紧张时）。

    将多层记忆压缩为简短摘要，保留最关键信息。

    Args:
        max_tokens: 最大 token 数

    Returns:
        压缩后的记忆摘要
    """
    try:
        from evolution_core.feedback_learner import generate_execution_guidance, get_all_preferences
        from evolution_core.weight_evolve import get_top_habits

        parts = []

        # 1. 偏好摘要（最高优先级）
        guidance = generate_execution_guidance()
        if guidance:
            # 只取前 2 条
            lines = guidance.split("\n")[:2]
            parts.append("; ".join(lines))

        # 2. 高权重习惯（只取 top 3）
        habits = get_top_habits(3)
        if habits:
            habit_names = [h.get("habit_key", "") for h in habits if h.get("habit_key")]
            if habit_names:
                parts.append(f"高频习惯: {', '.join(habit_names)}")

        summary = " | ".join(parts)
        if not summary:
            return ""

        # 截断到 max_tokens
        from agent_core.context_window import estimate_tokens, truncate_text
        if estimate_tokens(summary) > max_tokens:
            summary = truncate_text(summary, max_tokens)

        return f"[记忆摘要] {summary}"

    except Exception as e:
        logger.debug("记忆摘要压缩失败: %s", e)
        return ""


def resolve_memory_conflicts(preferences: list[dict]) -> list[dict]:
    """解决记忆冲突（同一偏好有多个不同值时，保留置信度最高的）。

    在读取偏好时调用，确保注入上下文的一致性。

    Args:
        preferences: 偏好列表

    Returns:
        解决冲突后的偏好列表
    """
    try:
        from evolution_core.feedback_learner import detect_preference_conflicts, resolve_conflicts
        conflicts = detect_preference_conflicts(preferences)
        if conflicts:
            logger.info("检测到 %d 个偏好冲突，自动解决", len(conflicts))
            return resolve_conflicts(preferences)
        return preferences
    except Exception as e:
        logger.debug("冲突解决失败: %s", e)
        return preferences


def _extract_search_keywords(task_text: str) -> list[str]:
    """从任务文本提取多个关键词（用于情景记忆检索）。

    不再只用前 10 字，而是提取有意义的关键词片段。
    """
    import re

    keywords = []

    # 1. 提取 2-4 字的中文词组
    for length in range(4, 1, -1):
        for i in range(len(task_text) - length + 1):
            word = task_text[i:i + length]
            if '一' <= word[0] <= '鿿':  # 以中文开头
                # 过滤纯数字/标点的
                if any('一' <= c <= '鿿' for c in word):
                    keywords.append(word)

    # 2. 去重并保持顺序
    seen = set()
    unique = []
    for kw in keywords:
        if kw not in seen and len(kw) >= 2:
            seen.add(kw)
            unique.append(kw)

    # 3. 返回最多 5 个关键词（避免查询过于复杂）
    return unique[:5]


def _recall_user_preferences(task_text: str, top_k: int = 3) -> str:
    """检索相关用户偏好（用户画像）——使用 guidance 摘要。

    修复：之前用 pref_key LIKE %keyword% 匹配不上（偏好键是 style:prefer 格式）。
    改用 generate_execution_guidance() 直接获取高置信度偏好摘要。
    """
    try:
        from evolution_core.feedback_learner import generate_execution_guidance, get_all_preferences

        # 先解决偏好冲突（同一 key 多个不同值 → 保留高置信度）
        all_prefs = get_all_preferences()
        resolved_prefs = resolve_memory_conflicts(all_prefs)

        # 从任务文本推断类型
        task_type = _detect_task_type_simple(task_text)
        # 使用解决冲突后的偏好生成 guidance
        from evolution_core.feedback_learner import generate_execution_guidance
        guidance = generate_execution_guidance(task_type)

        if not guidance:
            return ""

        return f"## 您的偏好\n{guidance}"

    except Exception as e:
        logger.debug("用户偏好检索失败: %s", e)
        return ""


def _detect_task_type_simple(task_text: str) -> str:
    """简单推断任务类型（用于偏好检索）。"""
    work_keywords = ["周报", "月报", "日报", "报销", "会议", "Excel", "PDF", "合同", "文书", "归档", "项目"]
    life_keywords = ["记账", "开销", "购物", "家务", "出行", "健身", "睡眠", "饮食"]

    for kw in work_keywords:
        if kw in task_text:
            return "work"
    for kw in life_keywords:
        if kw in task_text:
            return "life"
    return "work"  # 默认工作类型


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
                        file_name: str = "", score: float = 0, feedback_summary: str = "",
                        task_id: int = 0) -> bool:
    """将任务产出归档到知识库（语义记忆扩展，含评分和反馈元数据）。

    任务完成后调用，将生成的文书（周报、会议纪要等）存入知识库，
    使"上次怎么做的"可被检索。

    Args:
        task_text: 原始任务文本
        output_text: 任务产出的文本内容
        category: 知识库分类
        file_name: 文件名（可选）
        score: 任务评分（高分产出更有参考价值）
        feedback_summary: 用户反馈摘要（如"用户精简了内容"）
        task_id: 关联任务 ID

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

        # 在产出头部添加元数据（评分、反馈）
        metadata_header = ""
        if score > 0:
            metadata_header += f"<!-- 评分: {score:.0f} 分 -->\n"
        if feedback_summary:
            metadata_header += f"<!-- 用户反馈: {feedback_summary} -->\n"
        if task_id > 0:
            metadata_header += f"<!-- 任务 ID: {task_id} -->\n"

        full_text = metadata_header + output_text if metadata_header else output_text

        result = add_document(
            file_path=f"task_output://{file_name}",
            text=full_text,
            category=category,
            file_name=file_name,
        )

        if result.get("status") == "ok":
            logger.info("任务产出已归档知识库: %s (评分 %.0f, %d 切片)", file_name, score, result.get("chunks", 0))
            return True
        return False

    except Exception as e:
        logger.debug("任务产出归档失败: %s", e)
        return False
