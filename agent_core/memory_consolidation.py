"""记忆巩固：将碎片记忆"凝结"为结构化知识。

解决缺口：当前记忆是散落的碎片，没有"整理"机制。
10 次周报任务做完后，不会自动提炼"写周报的 3 个关键经验"。

核心能力：
1. 模式提炼：从情景记忆中重复出现的模式 → 程序性规则
2. 偏好强化：高频确认的偏好 → 提升置信度
3. 洞察生成：从具体事件中提炼抽象教训
4. 记忆清理：过期/冗余数据的归档
5. 反思摘要：生成"今天学到了什么"的总结
"""
import json
import logging
import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


def run_consolidation(days: int = 1) -> dict[str, Any]:
    """执行完整的记忆巩固周期（每日夜间调用）。

    Args:
        days: 回顾多少天的记忆

    Returns:
        巩固结果摘要
    """
    logger.info("═══ 开始记忆巩固周期（回顾 %d 天） ═══", days)
    start_time = datetime.now() - timedelta(days=days)
    results = {
        "period": f"{start_time.strftime('%Y-%m-%d')} ~ {datetime.now().strftime('%Y-%m-%d')}",
        "steps": [],
    }

    # 1. 模式提炼：情景记忆 → 程序性规则
    try:
        pattern_result = _extract_patterns_from_episodic(start_time)
        results["steps"].append({"step": "pattern_extract", **pattern_result})
        _log_consolidation("pattern_extract", pattern_result.get("source_count", 0),
                           pattern_result.get("summary", ""), pattern_result)
    except Exception as e:
        logger.warning("模式提炼失败: %s", e)
        results["steps"].append({"step": "pattern_extract", "summary": "模式提炼异常", "error": str(e)[:100]})

    # 2. 偏好强化：高频确认 → 提升置信度
    try:
        pref_result = _strengthen_frequent_preferences(start_time)
        results["steps"].append({"step": "preference_strengthen", **pref_result})
        _log_consolidation("preference_strengthen", pref_result.get("source_count", 0),
                           pref_result.get("summary", ""), pref_result)
    except Exception as e:
        logger.warning("偏好强化失败: %s", e)

    # 3. 洞察生成：具体事件 → 抽象教训
    try:
        insight_result = _generate_insights(start_time)
        results["steps"].append({"step": "insight_generate", **insight_result})
        _log_consolidation("insight_generate", insight_result.get("source_count", 0),
                           insight_result.get("summary", ""), insight_result)
    except Exception as e:
        logger.warning("洞察生成失败: %s", e)

    # 4. 记忆清理：冗余/过期数据
    try:
        cleanup_result = _cleanup_redundant_memories(start_time)
        results["steps"].append({"step": "cleanup", **cleanup_result})
        _log_consolidation("cleanup", cleanup_result.get("source_count", 0),
                           cleanup_result.get("summary", ""), cleanup_result)
    except Exception as e:
        logger.warning("记忆清理失败: %s", e)

    # 5. 元记忆同步 + 清理
    try:
        from agent_core.metamemory import sync_metamemory, cleanup_expired_metamemory
        sync_result = sync_metamemory()
        cleaned = cleanup_expired_metamemory(max_age_days=90)
        results["steps"].append({"step": "metamemory_sync",
                                  "summary": f"同步 {sync_result.get('synced', 0)} 条，清理 {cleaned} 条过期"})
    except Exception as e:
        logger.debug("元记忆同步失败: %s", e)

    # 6. 反思摘要
    try:
        reflection = _generate_reflection_summary(results["steps"])
        results["reflection"] = reflection
    except Exception as e:
        logger.debug("反思摘要生成失败: %s", e)

    # 7. 反思报告生成（每周一巩固后生成周报）
    try:
        if datetime.now().weekday() == 0:  # 周一
            from agent_core.reflection import generate_reflection_report
            reflection = generate_reflection_report(period="weekly")
            results["reflection"] = reflection.get("reflection", "")
            logger.info("周反思报告已生成")
    except Exception as e:
        logger.debug("反思报告生成失败: %s", e)

    logger.info("═══ 记忆巩固周期完成 ═══")
    return results


# ── 1. 模式提炼：情景记忆 → 程序性规则 ──

def _extract_patterns_from_episodic(since: datetime) -> dict[str, Any]:
    """从情景记忆中提取重复模式，提炼为程序性规则。"""
    from memory_store.sqlite_db import get_conn

    conn = get_conn()
    try:
        # 获取近期成功任务
        rows = conn.execute(
            """SELECT task_content, task_steps, work_score, life_score
               FROM task_list
               WHERE create_time >= ? AND status IN ('done', 'success')
               ORDER BY work_score DESC LIMIT 50""",
            (since.strftime("%Y-%m-%d %H:%M:%S"),),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return {"source_count": 0, "summary": "无近期任务", "patterns": []}

    # 按任务类型分组统计
    type_patterns = Counter()
    step_patterns = Counter()

    for row in rows:
        content = row["task_content"] or ""
        # 简单分类
        task_type = _classify_task_type(content)
        type_patterns[task_type] += 1

        # 提取步骤模式（保留全部步骤，不做 4 步截断）
        if row["task_steps"]:
            try:
                steps = json.loads(row["task_steps"])
                names = [s.get("name", "") for s in steps if s.get("name")]
                if len(names) >= 2:
                    seq = " → ".join(names)  # 保留全部步骤
                    step_patterns[(task_type, seq)] += 1
            except (json.JSONDecodeError, TypeError):
                continue

    # 提炼高频模式（动态阈值：总任务 < 10 时降为 1）
    threshold = 1 if len(rows) < 10 else 2
    frequent_patterns = [(key, count) for key, count in step_patterns.items() if count >= threshold]
    frequent_patterns.sort(key=lambda x: x[1], reverse=True)

    # 更新或创建程序性规则
    new_rules = []
    for (task_type, seq), count in frequent_patterns[:3]:
        rule = {
            "task_type": task_type,
            "step_sequence": seq,
            "frequency": count,
            "source": "consolidation",
        }
        new_rules.append(rule)
        # 存储到 user_preference
        _store_consolidated_rule(task_type, seq, count)

    summary = f"从 {len(rows)} 条任务中提炼出 {len(new_rules)} 个程序性规则"
    return {"source_count": len(rows), "summary": summary, "patterns": new_rules}


def _classify_task_type(content: str) -> str:
    """简单任务分类。"""
    work_kw = ["周报", "月报", "日报", "报销", "会议", "Excel", "PDF", "合同", "文书", "归档", "项目", "台账"]
    life_kw = ["记账", "开销", "购物", "家务", "出行", "健身", "睡眠", "饮食", "快递", "笔记"]
    health_kw = ["运动", "喝水", "久坐", "睡眠", "作息"]

    for kw in health_kw:
        if kw in content:
            return "health"
    for kw in life_kw:
        if kw in content:
            return "life"
    for kw in work_kw:
        if kw in content:
            return "work"
    return "other"


def _store_consolidated_rule(task_type: str, step_sequence: str, frequency: int) -> None:
    """存储巩固后的规则到偏好表。"""
    from memory_store.sqlite_db import get_conn
    from evolution_core.feedback_learner import _store_preference

    pref_key = f"procedure:{task_type}:common_flow"
    pref_value = step_sequence

    # 使用高置信度（因为是多任务验证的）
    confidence = min(0.5 + frequency * 0.1, 0.95)

    try:
        conn = get_conn()
        try:
            existing = conn.execute(
                "SELECT * FROM user_preference WHERE pref_key = ?", (pref_key,)
            ).fetchone()

            if existing:
                # 更新（取更高置信度）
                conn.execute(
                    """UPDATE user_preference SET
                        pref_value = ?, confidence = ?, evidence_count = evidence_count + 1,
                        last_evidence = ?, update_time = ?
                       WHERE pref_key = ?""",
                    (pref_value, confidence, f"巩固周期验证 {frequency} 次",
                     datetime.now().strftime("%Y-%m-%d %H:%M:%S"), pref_key),
                )
            else:
                conn.execute(
                    """INSERT INTO user_preference
                       (pref_key, pref_value, confidence, evidence_count, last_evidence)
                       VALUES (?, ?, ?, ?, ?)""",
                    (pref_key, pref_value, confidence, frequency,
                     f"巩固周期自动提炼 {frequency} 次"),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.debug("规则存储失败: %s", e)


# ── 2. 偏好强化：高频确认 → 提升置信度 ──

def _strengthen_frequent_preferences(since: datetime) -> dict[str, Any]:
    """强化近期被频繁确认的偏好。"""
    from memory_store.sqlite_db import get_conn

    conn = get_conn()
    try:
        # 获取近期反馈
        rows = conn.execute(
            """SELECT feedback_type, COUNT(*) as cnt
               FROM user_feedback
               WHERE create_time >= ?
               GROUP BY feedback_type""",
            (since.strftime("%Y-%m-%d %H:%M:%S"),),
        ).fetchall()

        # 获取所有偏好
        pref_rows = conn.execute(
            "SELECT * FROM user_preference WHERE confidence < 0.9"
        ).fetchall()
    finally:
        conn.close()

    if not pref_rows:
        return {"source_count": 0, "summary": "无待强化偏好", "strengthened": []}

    strengthened = []
    for pref in pref_rows:
        # 根据证据数提升置信度
        evidence = pref["evidence_count"]
        if evidence >= 3:
            # 证据充足，提升置信度
            new_confidence = min(pref["confidence"] + 0.05 * evidence, 0.95)
            try:
                conn = get_conn()
                try:
                    conn.execute(
                        "UPDATE user_preference SET confidence = ?, update_time = ? WHERE pref_key = ?",
                        (round(new_confidence, 3), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), pref["pref_key"]),
                    )
                    conn.commit()
                finally:
                    conn.close()
                strengthened.append({
                    "key": pref["pref_key"],
                    "old_confidence": pref["confidence"],
                    "new_confidence": round(new_confidence, 3),
                })
            except Exception:
                pass

    summary = f"强化了 {len(strengthened)} 个偏好（共 {len(pref_rows)} 个待强化）"
    return {"source_count": len(pref_rows), "summary": summary, "strengthened": strengthened}


# ── 3. 洞察生成：具体事件 → 抽象教训 ──

def _generate_insights(since: datetime) -> dict[str, Any]:
    """从近期任务中生成抽象洞察。"""
    from memory_store.sqlite_db import get_conn

    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT task_content, work_score, life_score, cost_time, status
               FROM task_list
               WHERE create_time >= ?
               ORDER BY create_time DESC LIMIT 30""",
            (since.strftime("%Y-%m-%d %H:%M:%S"),),
        ).fetchall()
    finally:
        conn.close()

    if len(rows) < 3:
        return {"source_count": len(rows), "summary": "任务数据不足，跳过洞察", "insights": []}

    insights = []

    # 洞察 1：分数趋势
    scores = [max(r["work_score"] or 0, r["life_score"] or 0) for r in rows if max(r["work_score"] or 0, r["life_score"] or 0) > 0]
    if len(scores) >= 3:
        first_half = sum(scores[:len(scores)//2]) / max(len(scores)//2, 1)
        second_half = sum(scores[len(scores)//2:]) / max(len(scores) - len(scores)//2, 1)
        if second_half > first_half + 5:
            insights.append(f"任务质量呈上升趋势（{first_half:.0f} → {second_half:.0f} 分）")
        elif second_half < first_half - 5:
            insights.append(f"任务质量有下降趋势（{first_half:.0f} → {second_half:.0f} 分），建议关注")

    # 洞察 2：耗时分析
    times = [r["cost_time"] for r in rows if r["cost_time"] > 0]
    if times:
        avg_time = sum(times) / len(times)
        if avg_time > 60:
            insights.append(f"平均任务耗时 {avg_time:.0f} 秒，建议优化流程")

    # 洞察 3：成功率
    success_count = sum(1 for r in rows if r["status"] in ("done", "success"))
    success_rate = success_count / len(rows) * 100
    if success_rate < 70:
        insights.append(f"任务成功率 {success_rate:.0f}%，建议检查失败原因")

    # 洞察 4：任务类型分布
    type_counts = Counter(_classify_task_type(r["task_content"] or "") for r in rows)
    if type_counts:
        most_common = type_counts.most_common(1)[0]
        insights.append(f"近期主要任务类型：{most_common[0]}（{most_common[1]} 次）")

    # 存储洞察
    if insights:
        try:
            conn = get_conn()
            try:
                conn.execute(
                    """INSERT INTO user_preference
                       (pref_key, pref_value, confidence, evidence_count, last_evidence)
                       VALUES (?, ?, ?, ?, ?)""",
                    ("insight:recent", json.dumps(insights, ensure_ascii=False),
                     0.7, len(rows), f"巩固周期生成 {datetime.now().strftime('%Y-%m-%d')}"),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            pass

    return {"source_count": len(rows), "summary": f"生成 {len(insights)} 条洞察", "insights": insights}


# ── 4. 记忆清理：冗余/过期数据 ──

def _cleanup_redundant_memories(since: datetime) -> dict[str, Any]:
    """清理冗余和低质量记忆 + 合并相似记忆。"""
    from memory_store.sqlite_db import get_conn

    conn = get_conn()
    cleaned = 0
    merged = 0
    try:
        old_time = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d %H:%M:%S")

        # 1. 清理低置信度（< 0.1）且长期未更新的偏好
        result = conn.execute(
            """DELETE FROM user_preference
               WHERE confidence < 0.1 AND update_time < ?""",
            (old_time,),
        )
        cleaned += result.rowcount

        # 2. 清理已处理且过期的反馈
        result = conn.execute(
            """DELETE FROM user_feedback
               WHERE processed = 1 AND create_time < ?""",
            (old_time,),
        )
        cleaned += result.rowcount

        # 3. 合并相似记忆（相同 pref_key 前缀的偏好）
        merged = _merge_similar_preferences(conn)

        conn.commit()
    finally:
        conn.close()

    return {"source_count": cleaned + merged,
            "summary": f"清理 {cleaned} 条，合并 {merged} 条相似记忆"}


def _merge_similar_preferences(conn: sqlite3.Connection) -> int:
    """合并相似的偏好（相同类型、相似值的偏好）。

    合并规则：
    - 同一 pref_key 前缀的偏好（如 style:prefer 和 style:prefer:detail）
    - 值相同或相似的偏好（如 "简洁" 和 "简单"）
    - 保留置信度最高的，合并证据数

    Returns:
        合并的记录数量
    """
    merged = 0
    try:
        # 查找相似偏好（基于 key 前缀匹配）
        rows = conn.execute(
            """SELECT pref_key, pref_value, confidence, evidence_count
               FROM user_preference
               WHERE confidence < 0.8
               ORDER BY pref_key"""
        ).fetchall()

        # 按前缀分组
        groups: dict[str, list[dict]] = {}
        for row in rows:
            # 提取前缀（如 procedure:work:common_flow → procedure:work）
            parts = row["pref_key"].rsplit(":", 1)
            prefix = parts[0] if len(parts) > 1 else row["pref_key"]
            if prefix not in groups:
                groups[prefix] = []
            groups[prefix].append({
                "key": row["pref_key"],
                "value": row["pref_value"],
                "confidence": row["confidence"],
                "evidence_count": row["evidence_count"],
            })

        # 合并每组中值相似的记录
        for prefix, items in groups.items():
            if len(items) <= 1:
                continue

            # 按值分组
            value_groups: dict[str, list[dict]] = {}
            for item in items:
                val_key = item["value"][:20]  # 取前 20 字符作为分组 key
                if val_key not in value_groups:
                    value_groups[val_key] = []
                value_groups[val_key].append(item)

            # 合并值相同的组
            for val_key, group in value_groups.items():
                if len(group) <= 1:
                    continue

                # 保留置信度最高的作为主记录
                group.sort(key=lambda x: x["confidence"], reverse=True)
                primary = group[0]
                total_evidence = sum(g["evidence_count"] for g in group)
                max_confidence = max(g["confidence"] for g in group)

                # 更新主记录
                conn.execute(
                    """UPDATE user_preference SET
                        evidence_count = ?, confidence = ?, update_time = ?
                       WHERE pref_key = ?""",
                    (total_evidence, min(max_confidence + 0.05, 0.95),
                     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                     primary["key"]),
                )

                # 删除其他重复记录
                for g in group[1:]:
                    if g["key"] != primary["key"]:
                        conn.execute(
                            "DELETE FROM user_preference WHERE pref_key = ?",
                            (g["key"],),
                        )
                        merged += 1

    except Exception as e:
        logger.debug("偏好合并失败: %s", e)

    return merged


# ── 5. 反思摘要 ──

def _generate_reflection_summary(steps: list[dict]) -> str:
    """生成反思摘要。"""
    parts = []
    for step in steps:
        step_name = step.get("step", "")
        summary = step.get("summary", "")
        if summary and summary != "无近期任务":
            parts.append(f"{step_name}: {summary}")

    if not parts:
        return "本次巩固周期无显著发现"

    return "；".join(parts)


# ── 辅助：日志记录 ──

def _log_consolidation(cons_type: str, source_count: int, summary: str, detail: dict) -> None:
    """记录巩固日志到数据库。"""
    try:
        from memory_store.sqlite_db import get_conn
        conn = get_conn()
        try:
            conn.execute(
                """INSERT INTO consolidation_log
                   (consolidation_type, source_count, result_summary, result_detail, period_start, period_end)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (cons_type, source_count, summary,
                 json.dumps(detail, ensure_ascii=False, default=str)[:1000],
                 (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
                 datetime.now().strftime("%Y-%m-%d")),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


# ── 便捷函数 ──

def get_consolidation_history(limit: int = 10) -> list[dict[str, Any]]:
    """获取巩固历史。"""
    from memory_store.sqlite_db import get_conn
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM consolidation_log ORDER BY create_time DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()


def get_latest_insights() -> list[str]:
    """获取最新洞察。"""
    from memory_store.sqlite_db import get_conn
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT pref_value FROM user_preference WHERE pref_key = 'insight:recent' ORDER BY update_time DESC LIMIT 1"
        ).fetchone()
        if row:
            return json.loads(row["pref_value"]) if row["pref_value"] else []
        return []
    except Exception:
        return []
    finally:
        conn.close()
