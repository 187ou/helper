"""深度反思：从统计到洞察。

解决缺口：当前反思只做统计报告（"本周 15 个任务，成功率 80%"），
缺少"为什么"和"怎么办"的深度分析。

核心能力：
1. 根因分析：为什么质量下降？为什么某个步骤反复出错？
2. 模式识别：用户的行为模式有什么深层含义？
3. 预测分析：按照当前趋势，下周会怎样？
4. 建议生成：基于分析给出可操作的改进建议
5. 对比学习：与历史最佳表现对比
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


def generate_deep_reflection(period: str = "weekly") -> dict[str, Any]:
    """生成深度反思报告（超越统计，给出洞察和建议）。

    Args:
        period: "weekly" 或 "monthly"

    Returns:
        深度反思报告
    """
    days = 7 if period == "weekly" else 30
    since = datetime.now() - timedelta(days=days)

    reflection = {
        "period": period,
        "generated_at": datetime.now().isoformat(),
    }

    # 1. 根因分析
    root_causes = _analyze_root_causes(since)
    reflection["root_causes"] = root_causes

    # 2. 深层模式识别
    deep_patterns = _identify_deep_patterns(since)
    reflection["deep_patterns"] = deep_patterns

    # 3. 趋势预测
    predictions = _generate_predictions(since)
    reflection["predictions"] = predictions

    # 4. 可操作建议
    actionable_suggestions = _generate_actionable_suggestions(root_causes, deep_patterns, predictions)
    reflection["actionable_suggestions"] = actionable_suggestions

    # 5. 与历史最佳对比
    best_comparison = _compare_to_best(since)
    reflection["best_comparison"] = best_comparison

    # 存储
    _store_deep_reflection(reflection)

    return reflection


# ── 1. 根因分析 ──

def _analyze_root_causes(since: datetime) -> list[dict]:
    """分析问题的根本原因（为什么出错）。"""
    causes = []
    try:
        from memory_store.sqlite_db import get_conn

        conn = get_conn()
        try:
            # 找出失败任务
            failed_rows = conn.execute(
                """SELECT task_content, task_steps, cost_time
                   FROM task_list
                   WHERE create_time >= ? AND status = 'failed'
                   ORDER BY create_time DESC LIMIT 20""",
                (since.strftime("%Y-%m-%d %H:%M:%S"),),
            ).fetchall()

            if not failed_rows:
                return []

            # 分析失败任务的共同特征
            # 特征 1：耗时过长
            long_time_tasks = [r for r in failed_rows if r["cost_time"] and r["cost_time"] > 120]
            if len(long_time_tasks) > len(failed_rows) * 0.5:
                causes.append({
                    "category": "耗时过长",
                    "description": f"{len(long_time_tasks)}/{len(failed_rows)} 个失败任务耗时超过 2 分钟",
                    "suggestion": "考虑将复杂任务拆分为更小的步骤，或增加超时时间",
                    "severity": "high" if len(long_time_tasks) > len(failed_rows) * 0.7 else "medium",
                })

            # 特征 2：步骤失败
            step_failures = Counter()
            for r in failed_rows:
                if r["task_steps"]:
                    try:
                        steps = json.loads(r["task_steps"])
                        for s in steps:
                            if s.get("status") == "failed":
                                step_failures[s.get("name", "未知")] += 1
                    except (json.JSONDecodeError, TypeError):
                        continue

            if step_failures:
                most_common = step_failures.most_common(3)
                for step_name, count in most_common:
                    if count >= 2:
                        causes.append({
                            "category": "步骤反复出错",
                            "description": f"步骤「{step_name}」失败 {count} 次",
                            "suggestion": f"建议重点优化「{step_name}」步骤的执行方式",
                            "severity": "high" if count >= 3 else "medium",
                        })

            # 特征 3：反馈分析
            feedback_rows = conn.execute(
                """SELECT original_content, modified_content, diff_summary
                   FROM user_feedback
                   WHERE create_time >= ? AND feedback_type = 'modify'
                   LIMIT 20""",
                (since.strftime("%Y-%m-%d %H:%M:%S"),),
            ).fetchall()

            if feedback_rows:
                # 分析用户修改的共同模式
                modification_types = Counter()
                for fb in feedback_rows:
                    if fb["diff_summary"]:
                        modification_types[fb["diff_summary"]] += 1

                if modification_types:
                    top_mod = modification_types.most_common(1)[0]
                    causes.append({
                        "category": "用户频繁修改",
                        "description": f"最常见的修改类型：「{top_mod[0]}」（{top_mod[1]} 次）",
                        "suggestion": "建议调整输出风格以减少用户修改",
                        "severity": "medium",
                    })

        finally:
            conn.close()
    except Exception as e:
        logger.debug("根因分析失败: %s", e)

    return causes


# ── 2. 深层模式识别 ──

def _identify_deep_patterns(since: datetime) -> list[dict]:
    """识别用户行为模式背后的深层含义。"""
    patterns = []
    try:
        from memory_store.sqlite_db import get_conn

        conn = get_conn()
        try:
            rows = conn.execute(
                """SELECT task_content, task_type, work_score, life_score, cost_time, status
                   FROM task_list WHERE create_time >= ?
                   ORDER BY create_time""",
                (since.strftime("%Y-%m-%d %H:%M:%S"),),
            ).fetchall()

            if len(rows) < 5:
                return []

            # 模式 1：质量与时间的关系
            high_score = [r for r in rows if max(r["work_score"] or 0, r["life_score"] or 0) > 80]
            low_score = [r for r in rows if 0 < max(r["work_score"] or 0, r["life_score"] or 0) < 50]

            if high_score and low_score:
                high_avg_time = sum(r["cost_time"] or 0 for r in high_score) / len(high_score)
                low_avg_time = sum(r["cost_time"] or 0 for r in low_score) / len(low_score)

                if high_avg_time > low_avg_time * 1.5:
                    patterns.append({
                        "type": "quality_time_correlation",
                        "description": f"高质量任务平均耗时 {high_avg_time:.0f}s，低质量任务 {low_avg_time:.0f}s",
                        "insight": "投入更多时间通常产出更高质量，建议为重要任务预留充足时间",
                    })

            # 模式 2：任务类型与质量的关系
            type_scores = {}
            for r in rows:
                t = r["task_type"] or "other"
                score = max(r["work_score"] or 0, r["life_score"] or 0)
                if score > 0:
                    if t not in type_scores:
                        type_scores[t] = []
                    type_scores[t].append(score)

            if type_scores:
                type_avgs = {t: sum(s)/len(s) for t, s in type_scores.items() if s}
                if type_avgs:
                    best_type = max(type_avgs, key=type_avgs.get)
                    worst_type = min(type_avgs, key=type_avgs.get)
                    if type_avgs[best_type] - type_avgs[worst_type] > 20:
                        patterns.append({
                            "type": "type_quality_gap",
                            "description": f"「{best_type}」类任务平均 {type_avgs[best_type]:.0f} 分，「{worst_type}」类仅 {type_avgs[worst_type]:.0f} 分",
                            "insight": f"建议参考「{best_type}」类任务的成功经验来改进「{worst_type}」类任务",
                        })

            # 模式 3：学习曲线
            if len(rows) >= 10:
                mid = len(rows) // 2
                first_half_scores = [max(r["work_score"] or 0, r["life_score"] or 0) for r in rows[:mid]]
                second_half_scores = [max(r["work_score"] or 0, r["life_score"] or 0) for r in rows[mid:]]

                first_avg = sum(first_half_scores) / max(len(first_half_scores), 1)
                second_avg = sum(second_half_scores) / max(len(second_half_scores), 1)

                if second_avg > first_avg + 10:
                    patterns.append({
                        "type": "learning_curve",
                        "description": f"前半期平均 {first_avg:.0f} 分 → 后半期 {second_avg:.0f} 分",
                        "insight": "你在进步！继续保持当前的学习节奏",
                    })
                elif second_avg < first_avg - 10:
                    patterns.append({
                        "type": "learning_curve",
                        "description": f"前半期平均 {first_avg:.0f} 分 → 后半期 {second_avg:.0f} 分",
                        "insight": "近期表现有所下滑，建议回顾上次成功的方法",
                    })

        finally:
            conn.close()
    except Exception as e:
        logger.debug("深层模式识别失败: %s", e)

    return patterns


# ── 3. 趋势预测 ──

def _generate_predictions(since: datetime) -> list[dict]:
    """基于当前趋势预测未来。"""
    predictions = []
    try:
        from memory_store.sqlite_db import get_conn

        conn = get_conn()
        try:
            # 获取最近 4 周的数据
            four_weeks_ago = since - timedelta(days=21)
            rows = conn.execute(
                """SELECT DATE(create_time) as day,
                          COUNT(*) as cnt,
                          AVG(COALESCE(work_score, 0)) as avg_score
                   FROM task_list
                   WHERE create_time >= ?
                   GROUP BY DATE(create_time)
                   ORDER BY day""",
                (four_weeks_ago.strftime("%Y-%m-%d %H:%M:%S"),),
            ).fetchall()

            if len(rows) >= 7:
                # 预测 1：任务量趋势
                recent = rows[-7:]
                earlier = rows[-14:-7] if len(rows) >= 14 else rows[:7]

                recent_avg = sum(r["cnt"] for r in recent) / len(recent)
                earlier_avg = sum(r["cnt"] for r in earlier) / len(earlier)

                if recent_avg > earlier_avg * 1.3:
                    predictions.append({
                        "type": "workload_increase",
                        "description": f"日均任务量从 {earlier_avg:.1f} 增加到 {recent_avg:.1f}",
                        "prediction": "下周可能继续保持高工作量，建议提前规划",
                    })
                elif recent_avg < earlier_avg * 0.7:
                    predictions.append({
                        "type": "workload_decrease",
                        "description": f"日均任务量从 {earlier_avg:.1f} 减少到 {recent_avg:.1f}",
                        "prediction": "下周工作量可能较低，适合处理积压任务",
                    })

                # 预测 2：质量趋势
                recent_scores = [r["avg_score"] for r in recent if r["avg_score"] > 0]
                if len(recent_scores) >= 3:
                    if all(recent_scores[i] <= recent_scores[i+1] for i in range(len(recent_scores)-1)):
                        predictions.append({
                            "type": "quality_improving",
                            "description": "任务质量连续提升",
                            "prediction": "按当前趋势，下周质量可能继续提升",
                        })
                    elif all(recent_scores[i] >= recent_scores[i+1] for i in range(len(recent_scores)-1)):
                        predictions.append({
                            "type": "quality_declining",
                            "description": "任务质量连续下降",
                            "prediction": "按当前趋势，下周需要关注质量问题",
                        })

        finally:
            conn.close()
    except Exception as e:
        logger.debug("趋势预测失败: %s", e)

    return predictions


# ── 4. 可操作建议 ──

def _generate_actionable_suggestions(root_causes: list, patterns: list, predictions: list) -> list[dict]:
    """基于分析生成可操作的改进建议（规则 + LLM 增强）。"""
    suggestions = []

    # 从根因生成建议
    for cause in root_causes:
        if cause["severity"] == "high":
            suggestions.append({
                "priority": "high",
                "area": cause["category"],
                "action": cause["suggestion"],
                "expected_impact": "解决主要失败原因",
            })

    # 从模式生成建议
    for pattern in patterns:
        if pattern.get("type") == "type_quality_gap":
            suggestions.append({
                "priority": "medium",
                "area": "任务质量",
                "action": pattern.get("insight", ""),
                "expected_impact": "缩小不同类型任务的质量差距",
            })
        elif pattern.get("type") == "quality_time_correlation":
            suggestions.append({
                "priority": "medium",
                "area": "时间管理",
                "action": pattern.get("insight", ""),
                "expected_impact": "提高重要任务的质量",
            })

    # 从预测生成建议
    for pred in predictions:
        if pred.get("type") == "workload_increase":
            suggestions.append({
                "priority": "medium",
                "area": "工作规划",
                "action": pred.get("prediction", ""),
                "expected_impact": "避免工作积压",
            })

    # ── LLM 增强：生成深度洞察 ──
    try:
        llm_suggestion = _generate_llm_insight(root_causes, patterns, predictions)
        if llm_suggestion:
            suggestions.append({
                "priority": "high",
                "area": "深度洞察",
                "action": llm_suggestion,
                "expected_impact": "LLM 生成的个性化改进建议",
                "source": "llm",
            })
    except Exception:
        pass

    # 去重并按优先级排序
    seen = set()
    unique = []
    for s in suggestions:
        key = s.get("action", "")[:50]
        if key not in seen:
            seen.add(key)
            unique.append(s)

    priority_order = {"high": 0, "medium": 1, "low": 2}
    unique.sort(key=lambda x: priority_order.get(x.get("priority", "low"), 3))

    return unique[:5]  # 最多 5 条建议


def _generate_llm_insight(root_causes: list, patterns: list, predictions: list) -> str | None:
    """使用 LLM 生成深度洞察（为什么 + 怎么办）。

    将统计数据发送给 LLM，生成自然语言的深度分析。
    """
    try:
        from agent_core.llm_client import chat

        # 构造 prompt
        prompt_parts = ["基于以下用户行为数据，生成一条深度洞察（为什么 + 怎么办）："]

        if root_causes:
            prompt_parts.append("\n【问题根因】")
            for c in root_causes[:3]:
                prompt_parts.append(f"- {c['description']}（建议：{c['suggestion']}）")

        if patterns:
            prompt_parts.append("\n【行为模式】")
            for p in patterns[:3]:
                prompt_parts.append(f"- {p.get('description', '')}")

        if predictions:
            prompt_parts.append("\n【趋势预测】")
            for pr in predictions[:2]:
                prompt_parts.append(f"- {pr.get('description', '')}")

        prompt_parts.append("\n请用 1-2 句话给出深度洞察，格式：「为什么」→「怎么办」。不要 markdown。")

        prompt = "\n".join(prompt_parts)

        result = chat([
            {"role": "system", "content": "你是用户行为分析专家，擅长从数据中发现问题根因并给出可操作建议。"},
            {"role": "user", "content": prompt},
        ], temperature=0.5, max_tokens=200)

        if result and result.strip() and "失败" not in result and "错误" not in result:
            return result.strip()

        return None
    except Exception as e:
        logger.debug("LLM 洞察生成失败: %s", e)
        return None


# ── 5. 与历史最佳对比 ──

def _compare_to_best(since: datetime) -> dict:
    """与历史最佳表现对比。"""
    try:
        from memory_store.sqlite_db import get_conn

        conn = get_conn()
        try:
            # 历史最佳周
            best_row = conn.execute(
                """SELECT DATE(create_time) as day,
                          AVG(COALESCE(work_score, 0)) as avg_score,
                          COUNT(*) as cnt
                   FROM task_list
                   WHERE work_score > 0
                   GROUP BY DATE(create_time)
                   HAVING cnt >= 2
                   ORDER BY avg_score DESC LIMIT 1"""
            ).fetchone()

            # 当前周
            current_row = conn.execute(
                """SELECT AVG(COALESCE(work_score, 0)) as avg_score,
                          COUNT(*) as cnt
                   FROM task_list
                   WHERE create_time >= ? AND work_score > 0""",
                (since.strftime("%Y-%m-%d %H:%M:%S"),),
            ).fetchone()

            best_score = best_row["avg_score"] if best_row else 0
            current_score = current_row["avg_score"] if current_row and current_row["avg_score"] else 0

            if best_score > 0 and current_score > 0:
                diff = current_score - best_score
                if diff >= 0:
                    return {
                        "best_score": round(best_score, 1),
                        "current_score": round(current_score, 1),
                        "diff": round(diff, 1),
                        "message": f"当前表现与历史最佳持平或更优（+{diff:.1f} 分）",
                        "is_record": diff > 5,
                    }
                else:
                    return {
                        "best_score": round(best_score, 1),
                        "current_score": round(current_score, 1),
                        "diff": round(diff, 1),
                        "message": f"距历史最佳还差 {abs(diff):.1f} 分，继续加油",
                        "is_record": False,
                    }

            return {"message": "数据不足，无法对比"}
        finally:
            conn.close()
    except Exception:
        return {"message": "对比失败"}


# ── 存储 ──

def _store_deep_reflection(reflection: dict) -> None:
    """存储深度反思报告。"""
    try:
        from memory_store.sqlite_db import get_conn
        conn = get_conn()
        try:
            period = reflection.get("period", "weekly")
            today = datetime.now().strftime("%Y-%m-%d")

            # 存储到巩固日志
            conn.execute(
                """INSERT INTO consolidation_log
                   (consolidation_type, source_count, result_summary, result_detail, period_start, period_end)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ("deep_reflection", len(reflection.get("root_causes", [])),
                 reflection.get("actionable_suggestions", [{}])[0].get("action", "")[:200]
                 if reflection.get("actionable_suggestions") else "",
                 json.dumps(reflection, ensure_ascii=False, default=str)[:2000],
                 (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
                 today),
            )

            # 更新 latest
            latest_key = f"deep_reflection:{period}:latest"
            existing = conn.execute(
                "SELECT pref_key FROM user_preference WHERE pref_key = ?", (latest_key,)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE user_preference SET pref_value = ?, update_time = ? WHERE pref_key = ?",
                    (json.dumps(reflection, ensure_ascii=False, default=str),
                     datetime.now().strftime("%Y-%m-%d %H:%M:%S"), latest_key),
                )
            else:
                conn.execute(
                    """INSERT INTO user_preference
                       (pref_key, pref_value, confidence, evidence_count, last_evidence)
                       VALUES (?, ?, 0.8, 1, ?)""",
                    (latest_key, json.dumps(reflection, ensure_ascii=False, default=str),
                     f"深度反思 {today}"),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.debug("深度反思存储失败: %s", e)


def get_latest_deep_reflection(period: str = "weekly") -> dict:
    """获取最新深度反思。"""
    try:
        from memory_store.sqlite_db import get_conn
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT pref_value FROM user_preference WHERE pref_key = ?",
                (f"deep_reflection:{period}:latest",),
            ).fetchone()
            return json.loads(row["pref_value"]) if row else {}
        finally:
            conn.close()
    except Exception:
        return {}
