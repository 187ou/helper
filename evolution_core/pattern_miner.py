"""任务模式挖掘：从历史任务中发现可复用的工作流模式（含完整边缘处理）。

边缘情况处理：
1. 空任务文本/步骤 → 直接返回，不抛异常
2. 数据库连接失败 → 记录日志 + 安全返回
3. JSON 解析失败 → 使用默认值
4. 零除（空列表）→ 返回 0
5. 模式 key 冲突 → 更新而非报错
6. 超长文本 → 截断处理
"""
import json
import logging
import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from memory_store.sqlite_db import get_conn, now_str
from evolution_core.safe_ops import (
    safe_db_read, safe_db_write, safe_json_loads, safe_divide,
    safe_avg, sanitize_text, clamp_value,
)

logger = logging.getLogger(__name__)

# 最小支持度
_MIN_SUPPORT = 2
_MIN_CONFIDENCE = 0.5
# 最大步骤数（防止超长输入）
_MAX_STEPS = 50


@safe_db_read
def mine_patterns() -> list[dict[str, Any]]:
    """从历史任务中挖掘所有模式。"""
    patterns = []
    patterns.extend(_mine_sequence_patterns())
    patterns.extend(_mine_combo_patterns())
    return patterns


@safe_db_read
def recommend_steps(task_text: str, task_type: str = "") -> list[dict[str, Any]] | None:
    """为新任务推荐历史最优步骤模板（语义匹配 + 关键词匹配双通道）。"""
    if not task_text or not task_text.strip():
        return None

    # 1. 尝试语义匹配（更精准）
    try:
        from evolution_core.semantic_match import semantic_match_patterns
        conn = get_conn()
        all_patterns = conn.execute(
            "SELECT * FROM task_pattern WHERE usage_count >= 1 ORDER BY confidence DESC LIMIT 50"
        ).fetchall()
        conn.close()

        if all_patterns:
            matched = semantic_match_patterns(task_text, [dict(p) for p in all_patterns], threshold=0.4)
            if matched:
                best = matched[0]
                steps = safe_json_loads(best.get("step_template"), default=None)
                if steps and isinstance(steps, list):
                    logger.info("语义推荐: %s (相似度 %.2f)", best["pattern_key"], best.get("semantic_score", 0))
                    return steps
    except Exception as e:
        logger.debug("语义匹配失败，降级关键词: %s", e)

    # 2. 降级：关键词匹配
    matched = _find_matching_patterns(task_text, task_type)
    if not matched:
        return None

    matched.sort(key=lambda p: _pattern_score(p), reverse=True)
    best = matched[0]

    steps = safe_json_loads(best.get("step_template"), default=None)
    if steps and isinstance(steps, list):
        logger.info("关键词推荐: %s (置信度 %.2f)", best["pattern_key"], best["confidence"])
        return steps
    return None


@safe_db_write(default_return=False)
def record_pattern_usage(pattern_key: str, score: float, duration: float, success: bool) -> bool:
    """记录模式被使用，更新统计。"""
    if not pattern_key:
        return False

    pattern_key = sanitize_text(pattern_key, max_length=200)
    score = clamp_value(score, 0, 100)
    duration = max(0, duration)

    conn = get_conn()
    try:
        existing = conn.execute(
            "SELECT * FROM task_pattern WHERE pattern_key = ?", (pattern_key,)
        ).fetchone()

        if existing:
            new_count = existing["usage_count"] + 1
            new_total_dur = existing["total_duration"] + duration
            new_success = existing["success_count"] + (1 if success else 0)
            new_avg_score = safe_divide(
                existing["avg_score"] * existing["usage_count"] + score,
                new_count
            )

            conn.execute(
                """UPDATE task_pattern SET
                    usage_count = ?, avg_score = ?, success_count = ?,
                    total_duration = ?, avg_duration = ?, confidence = ?,
                    last_use_time = ?
                   WHERE pattern_key = ?""",
                (
                    new_count, round(new_avg_score, 2), new_success,
                    round(new_total_dur, 2), round(safe_divide(new_total_dur, new_count), 2),
                    round(safe_divide(new_success, new_count), 3),
                    now_str(), pattern_key,
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return True


def learn_from_task(task_text: str, steps: list[dict], score: float, duration: float, success: bool) -> None:
    """从完成的任务中学习新模式或强化已有模式。"""
    # 边缘：空步骤或单一步骤无法形成模式
    if not steps or len(steps) < 2:
        return
    if len(steps) > _MAX_STEPS:
        steps = steps[:_MAX_STEPS]

    task_text = sanitize_text(task_text, max_length=200)
    step_names = [s.get("name", "") for s in steps if s.get("name")]

    if len(step_names) < 2:
        return

    keywords = _extract_keywords(task_text)
    # 提取步骤类型序列，用于生成稳定的 pattern_key
    step_types = [s.get("step_type", s.get("type", "action")) for s in steps]
    pattern_key = _generate_detailed_pattern_key(step_names, keywords, step_types)

    # 安全写入
    if not _safe_learn(pattern_key, keywords, step_names, score, duration, success):
        logger.debug("模式学习跳过: %s", pattern_key)


@safe_db_write(default_return=False)
def _safe_learn(pattern_key, keywords, step_names, score, duration, success) -> bool:
    """安全执行模式学习（DB 操作）。"""
    conn = get_conn()
    try:
        existing = conn.execute(
            "SELECT * FROM task_pattern WHERE pattern_key = ?", (pattern_key,)
        ).fetchone()

        if existing:
            new_count = existing["usage_count"] + 1
            new_success = existing["success_count"] + (1 if success else 0)
            new_total_dur = existing["total_duration"] + duration
            new_avg_score = safe_divide(
                existing["avg_score"] * existing["usage_count"] + score,
                new_count
            )

            conn.execute(
                """UPDATE task_pattern SET
                    usage_count = ?, avg_score = ?, success_count = ?,
                    total_duration = ?, avg_duration = ?, confidence = ?,
                    last_use_time = ?
                   WHERE pattern_key = ?""",
                (
                    new_count, round(new_avg_score, 2), new_success,
                    round(new_total_dur, 2), round(safe_divide(new_total_dur, new_count), 2),
                    round(safe_divide(new_success, new_count), 3),
                    now_str(), pattern_key,
                ),
            )
            logger.info("强化模式: %s (第 %d 次)", pattern_key, new_count)
        else:
            confidence = 1.0 if success else 0.0
            conn.execute(
                """INSERT INTO task_pattern
                   (pattern_key, pattern_type, task_keywords, step_template,
                    avg_score, success_count, total_duration, avg_duration, confidence, last_use_time)
                   VALUES (?, 'workflow', ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    pattern_key,
                    json.dumps(keywords, ensure_ascii=False),
                    json.dumps(step_names, ensure_ascii=False),
                    round(score, 2), 1 if success else 0,
                    round(duration, 2), round(duration, 2),
                    confidence, now_str(),
                ),
            )
            logger.info("发现新模式: %s", pattern_key)
        conn.commit()
    finally:
        conn.close()
    return True


@safe_db_read
def get_top_patterns(n: int = 10, min_confidence: float = 0) -> list[dict[str, Any]]:
    """获取高置信度的模式列表。"""
    n = clamp_value(n, 1, 100)

    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT * FROM task_pattern
               WHERE confidence >= ?
               ORDER BY confidence DESC, usage_count DESC, avg_score DESC
               LIMIT ?""",
            (min_confidence, int(n)),
        ).fetchall()
    finally:
        conn.close()

    result = []
    for r in rows:
        d = dict(r)
        d["task_keywords"] = safe_json_loads(d.get("task_keywords"), default=[])
        d["step_template"] = safe_json_loads(d.get("step_template"), default=[])
        d["source_task_ids"] = safe_json_loads(d.get("source_task_ids"), default=[])
        result.append(d)
    return result


# ── 内部实现 ──

def _mine_sequence_patterns() -> list[dict[str, Any]]:
    """挖掘高频步骤序列模式。"""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT task_steps FROM task_list WHERE task_steps IS NOT NULL AND task_steps != '[]'"
        ).fetchall()
    except Exception:
        return []
    finally:
        conn.close()

    sequences = []
    for row in rows:
        try:
            steps = safe_json_loads(row["task_steps"], default=[])
            if not steps:
                continue
            names = [s.get("name", "") for s in steps if s.get("name")]
            if len(names) >= 2:
                sequences.append(names)
        except Exception:
            continue

    if not sequences:
        return []

    bigram_counts = Counter()
    for seq in sequences:
        for i in range(len(seq) - 1):
            bigram = f"{seq[i]}→{seq[i+1]}"
            bigram_counts[bigram] += 1

    patterns = []
    total = len(sequences)
    for bigram, count in bigram_counts.most_common(20):
        if count >= _MIN_SUPPORT:
            parts = bigram.split("→")
            patterns.append({
                "pattern_key": bigram,
                "pattern_type": "sequence",
                "step_template": parts,
                "usage_count": count,
                "confidence": round(safe_divide(count, total), 3),
            })
    return patterns


def _mine_combo_patterns() -> list[dict[str, Any]]:
    """挖掘经常同时出现的任务组合。"""
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT DATE(create_time) as d, GROUP_CONCAT(task_type, ',') as types
               FROM task_list
               GROUP BY DATE(create_time)
               HAVING COUNT(*) >= 2"""
        ).fetchall()
    except Exception:
        return []
    finally:
        conn.close()

    combo_counts = Counter()
    for row in rows:
        types = sorted(set(row["types"].split(",")))
        if len(types) >= 2:
            for i in range(len(types)):
                for j in range(i + 1, len(types)):
                    combo = f"{types[i]}+{types[j]}"
                    combo_counts[combo] += 1

    patterns = []
    total = len(rows)
    for combo, count in combo_counts.most_common(10):
        if count >= _MIN_SUPPORT:
            patterns.append({
                "pattern_key": combo,
                "pattern_type": "combo",
                "task_keywords": combo.split("+"),
                "usage_count": count,
                "confidence": round(safe_divide(count, total), 3),
            })
    return patterns


def _find_matching_patterns(task_text: str, task_type: str = "") -> list[dict[str, Any]]:
    """查找与当前任务匹配的历史模式。"""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM task_pattern WHERE usage_count >= ? ORDER BY confidence DESC",
            (_MIN_SUPPORT,),
        ).fetchall()
    except Exception:
        return []
    finally:
        conn.close()

    keywords = set(_extract_keywords(task_text))
    if not keywords:
        return []

    matched = []
    for row in rows:
        pattern_keywords = safe_json_loads(row["task_keywords"], default=[])
        pattern_keywords = set(pattern_keywords)

        if keywords and pattern_keywords:
            overlap = safe_divide(len(keywords & pattern_keywords), max(len(keywords), 1))
            if overlap >= 0.3:
                matched.append(dict(row))
    return matched


def _extract_keywords(text: str) -> list[str]:
    """从文本中提取关键词。"""
    if not text:
        return []

    stopwords = {"的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好", "自己", "这"}

    words = []
    for length in range(2, 5):
        for i in range(len(text) - length + 1):
            word = text[i:i + length]
            if word not in stopwords and not re.match(r'^[\s\d\W]+$', word):
                words.append(word)

    counter = Counter(words)
    return [w for w, c in counter.most_common(10) if c >= 1]


def _generate_pattern_key(step_names: list[str], keywords: list[str]) -> str:
    """生成模式唯一标识（基于步骤类型序列 + 关键词，避免名称碎片化）。

    之前用步骤名拼接（如 "周报:收集_梳理_汇总"），LLM 每次生成步骤名稍有不同就变成新模式。
    现在用步骤类型序列（如 "action:action+parallel+action"）+ 关键词前缀，同类工作流归并。
    """
    keyword_prefix = keywords[0] if keywords else "default"
    return f"{keyword_prefix}:{len(step_names)}steps"


def _generate_detailed_pattern_key(step_names: list[str], keywords: list[str],
                                    step_types: list[str] | None = None) -> str:
    """生成带步骤类型的详细模式 key（用于区分同一关键词下的不同流程模式）。"""
    keyword_prefix = keywords[0] if keywords else "default"
    if step_types and len(step_types) == len(step_names):
        # 用类型序列区分：如 "action+parallel+action"
        type_seq = "+".join(t if t in ("action", "parallel") else "action" for t in step_types)
        return f"{keyword_prefix}:{type_seq}"
    # 降级：用步骤数
    return f"{keyword_prefix}:{len(step_names)}steps"


def _pattern_score(pattern: dict) -> float:
    """计算模式综合得分。"""
    confidence = clamp_value(pattern.get("confidence", 0), 0, 1)
    usage_count = pattern.get("usage_count", 0)
    avg_score = clamp_value(pattern.get("avg_score", 0), 0, 100)

    usage_factor = clamp_value(usage_count / 10, 0, 1)
    score_factor = clamp_value(avg_score / 100, 0, 1)

    return confidence * 0.4 + usage_factor * 0.3 + score_factor * 0.3
