"""反思与抽象：从具体事件中提炼高阶洞察。

解决缺口：当前系统会"记"但不会"想"，无法从事件中提炼抽象教训。

核心能力：
1. 周期反思：生成周/月反思报告
2. 模式检测：发现用户行为模式变化
3. 高阶洞察：从具体事件抽象通用教训
4. 改进建议：基于反思给出可操作建议
5. 趋势预测：预测未来可能的问题/机会
"""
import json
import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any

from agent_core.memory_consolidation import get_latest_insights

logger = logging.getLogger(__name__)


def generate_reflection_report(period: str = "weekly") -> dict[str, Any]:
    """生成反思报告（周/月）。

    Args:
        period: "weekly" 或 "monthly"

    Returns:
        反思报告，包含统计、模式、洞察、建议
    """
    days = 7 if period == "weekly" else 30
    since = datetime.now() - timedelta(days=days)

    logger.info("═══ 生成 %s 反思报告 ═══", period)

    report = {
        "period": period,
        "period_start": since.strftime("%Y-%m-%d"),
        "period_end": datetime.now().strftime("%Y-%m-%d"),
        "generated_at": datetime.now().isoformat(),
    }

    # 数据不足检查（新用户友好）
    stats = _collect_period_stats(since)
    if stats.get("total_tasks", 0) < 2:
        return {
            "period": period,
            "message": "数据不足，至少需要 2 个任务才能生成反思报告",
            "total_tasks": stats.get("total_tasks", 0),
        }

    report["statistics"] = stats

    # 2. 行为模式检测
    patterns = _detect_behavior_patterns(since)
    report["patterns"] = patterns

    # 3. 高阶洞察（LLM 辅助）
    insights = _generate_advanced_insights(since, stats, patterns)
    report["insights"] = insights

    # 4. 改进建议
    suggestions = _generate_improvement_suggestions(stats, patterns, insights)
    report["suggestions"] = suggestions

    # 5. 与上期对比（趋势）
    if period == "weekly":
        prev_since = since - timedelta(days=7)
        prev_stats = _collect_period_stats(prev_since)
        report["trend"] = _compare_periods(prev_stats, stats)

    # 存储报告
    _store_reflection_report(report)

    logger.info("═══ %s 反思报告生成完成 ═══", period)
    return report


# ── 1. 基础统计 ──

def _collect_period_stats(since: datetime) -> dict[str, Any]:
    """收集周期内的基础统计数据。"""
    from memory_store.sqlite_db import get_conn

    conn = get_conn()
    try:
        # 任务总量
        total_row = conn.execute(
            "SELECT COUNT(*) as cnt FROM task_list WHERE create_time >= ?",
            (since.strftime("%Y-%m-%d %H:%M:%S"),),
        ).fetchone()

        # 成功/失败
        success_row = conn.execute(
            """SELECT COUNT(*) as cnt FROM task_list
               WHERE create_time >= ? AND status IN ('done', 'success')""",
            (since.strftime("%Y-%m-%d %H:%M:%S"),),
        ).fetchone()

        # 平均分数
        score_row = conn.execute(
            """SELECT AVG(work_score) as avg_work, AVG(life_score) as avg_life
               FROM task_list
               WHERE create_time >= ? AND (work_score > 0 OR life_score > 0)""",
            (since.strftime("%Y-%m-%d %H:%M:%S"),),
        ).fetchone()

        # 平均耗时
        time_row = conn.execute(
            """SELECT AVG(cost_time) as avg_time FROM task_list
               WHERE create_time >= ? AND cost_time > 0""",
            (since.strftime("%Y-%m-%d %H:%M:%S"),),
        ).fetchone()

        # 反馈统计
        feedback_rows = conn.execute(
            """SELECT feedback_type, COUNT(*) as cnt FROM user_feedback
               WHERE create_time >= ? GROUP BY feedback_type""",
            (since.strftime("%Y-%m-%d %H:%M:%S"),),
        ).fetchall()

        # 类型分布
        type_rows = conn.execute(
            """SELECT task_type, COUNT(*) as cnt FROM task_list
               WHERE create_time >= ? GROUP BY task_type ORDER BY cnt DESC""",
            (since.strftime("%Y-%m-%d %H:%M:%S"),),
        ).fetchall()

        total = total_row["cnt"] if total_row else 0
        success = success_row["cnt"] if success_row else 0

        # 安全除零：所有除法用 max(..., 1)
        return {
            "total_tasks": total,
            "successful_tasks": success,
            "failed_tasks": total - success,
            "success_rate": round(success / max(total, 1) * 100, 1),
            "avg_work_score": round(score_row["avg_work"], 1) if score_row and score_row["avg_work"] else 0,
            "avg_life_score": round(score_row["avg_life"], 1) if score_row and score_row["avg_life"] else 0,
            "avg_cost_time": round(time_row["avg_time"], 1) if time_row and time_row["avg_time"] else 0,
            "feedback_distribution": {r["feedback_type"]: r["cnt"] for r in feedback_rows},
            "type_distribution": {r["task_type"]: r["cnt"] for r in type_rows},
        }
    except Exception as e:
        logger.debug("统计收集失败: %s", e)
        return {}
    finally:
        conn.close()


# ── 2. 行为模式检测 ──

def _detect_behavior_patterns(since: datetime) -> list[dict[str, Any]]:
    """检测用户行为模式变化。"""
    patterns = []

    try:
        # 模式 1：任务频率变化
        freq_pattern = _detect_frequency_pattern(since)
        if freq_pattern:
            patterns.append(freq_pattern)

        # 模式 2：时间偏好（何时执行任务）
        time_pattern = _detect_time_preference(since)
        if time_pattern:
            patterns.append(time_pattern)

        # 模式 3：质量变化趋势
        quality_pattern = _detect_quality_trend(since)
        if quality_pattern:
            patterns.append(quality_pattern)

        # 模式 4：类型集中度
        type_pattern = _detect_type_concentration(since)
        if type_pattern:
            patterns.append(type_pattern)

        # 模式 5：反馈倾向
        feedback_pattern = _detect_feedback_tendency(since)
        if feedback_pattern:
            patterns.append(feedback_pattern)

    except Exception as e:
        logger.debug("模式检测失败: %s", e)

    return patterns


def _detect_frequency_pattern(since: datetime) -> dict | None:
    """检测任务频率模式。"""
    from memory_store.sqlite_db import get_conn

    conn = get_conn()
    try:
        # 按天统计任务数
        rows = conn.execute(
            """SELECT DATE(create_time) as day, COUNT(*) as cnt
               FROM task_list WHERE create_time >= ?
               GROUP BY DATE(create_time) ORDER BY day""",
            (since.strftime("%Y-%m-%d %H:%M:%S"),),
        ).fetchall()

        if len(rows) < 3:
            return None

        counts = [r["cnt"] for r in rows]
        avg_count = sum(counts) / len(counts)
        max_day = max(rows, key=lambda x: x["cnt"])

        return {
            "type": "frequency",
            "description": f"日均 {avg_count:.1f} 个任务，最高 {max_day['cnt']} 个（{max_day['day']}）",
            "daily_avg": round(avg_count, 1),
            "peak_day": max_day["day"],
            "peak_count": max_day["cnt"],
        }
    except Exception:
        return None
    finally:
        conn.close()


def _detect_time_preference(since: datetime) -> dict | None:
    """检测时间偏好（何时执行任务）。"""
    from memory_store.sqlite_db import get_conn

    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT strftime('%H', create_time) as hour, COUNT(*) as cnt
               FROM task_list WHERE create_time >= ?
               GROUP BY hour ORDER BY cnt DESC LIMIT 3""",
            (since.strftime("%Y-%m-%d %H:%M:%S"),),
        ).fetchall()

        if not rows:
            return None

        peak_hours = [f"{r['hour']}时({r['cnt']}次)" for r in rows[:3]]
        return {
            "type": "time_preference",
            "description": f"任务高峰时段：{', '.join(peak_hours)}",
            "peak_hours": [r["hour"] for r in rows[:3]],
        }
    except Exception:
        return None
    finally:
        conn.close()


def _detect_quality_trend(since: datetime) -> dict | None:
    """检测质量变化趋势。"""
    from memory_store.sqlite_db import get_conn

    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT DATE(create_time) as day,
                      AVG(COALESCE(work_score, 0)) as avg_score
               FROM task_list
               WHERE create_time >= ? AND work_score > 0
               GROUP BY DATE(create_time) ORDER BY day""",
            (since.strftime("%Y-%m-%d %H:%M:%S"),),
        ).fetchall()

        if len(rows) < 3:
            return None

        first_half = [r["avg_score"] for r in rows[:len(rows)//2]]
        second_half = [r["avg_score"] for r in rows[len(rows)//2:]]

        if not first_half or not second_half:
            return None

        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)

        if second_avg > first_avg + 5:
            return {"type": "quality_trend", "direction": "improving",
                    "description": f"任务质量上升趋势（{first_avg:.0f} → {second_avg:.0f} 分）"}
        elif second_avg < first_avg - 5:
            return {"type": "quality_trend", "direction": "declining",
                    "description": f"任务质量下降趋势（{first_avg:.0f} → {second_avg:.0f} 分）"}
        return {"type": "quality_trend", "direction": "stable",
                "description": f"任务质量稳定（{first_avg:.0f} 分左右）"}
    except Exception:
        return None
    finally:
        conn.close()


def _detect_type_concentration(since: datetime) -> dict | None:
    """检测任务类型集中度。"""
    from memory_store.sqlite_db import get_conn

    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT task_type, COUNT(*) as cnt FROM task_list
               WHERE create_time >= ? AND task_type != ''
               GROUP BY task_type ORDER BY cnt DESC LIMIT 5""",
            (since.strftime("%Y-%m-%d %H:%M:%S"),),
        ).fetchall()

        if not rows:
            return None

        total = sum(r["cnt"] for r in rows)
        top = rows[0]

        concentration = top["cnt"] / max(total, 1) * 100

        return {
            "type": "type_concentration",
            "description": f"「{top['task_type']}」类任务占 {concentration:.0f}%（{top['cnt']}/{total}）",
            "top_type": top["task_type"],
            "concentration": round(concentration, 1),
            "distribution": {r["task_type"]: r["cnt"] for r in rows},
        }
    except Exception:
        return None
    finally:
        conn.close()


def _detect_feedback_tendency(since: datetime) -> dict | None:
    """检测反馈倾向（用户是否满意）。"""
    from memory_store.sqlite_db import get_conn

    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT feedback_type, COUNT(*) as cnt FROM user_feedback
               WHERE create_time >= ? GROUP BY feedback_type""",
            (since.strftime("%Y-%m-%d %H:%M:%S"),),
        ).fetchall()

        if not rows:
            return None

        total = sum(r["cnt"] for r in rows)
        praise = sum(r["cnt"] for r in rows if r["feedback_type"] == "praise")
        modify = sum(r["cnt"] for r in rows if r["feedback_type"] == "modify")
        reject = sum(r["cnt"] for r in rows if r["feedback_type"] == "reject")

        satisfaction = praise / max(praise + modify + reject, 1) * 100

        if satisfaction >= 70:
            desc = f"用户满意（点赞率 {satisfaction:.0f}%）"
        elif satisfaction >= 40:
            desc = f"用户有改进建议（修改率 {modify/max(total,1)*100:.0f}%）"
        else:
            desc = f"用户反馈偏负面（驳回率 {reject/max(total,1)*100:.0f}%）"

        return {
            "type": "feedback_tendency",
            "description": desc,
            "satisfaction_rate": round(satisfaction, 1),
            "praise_count": praise,
            "modify_count": modify,
            "reject_count": reject,
        }
    except Exception:
        return None
    finally:
        conn.close()


# ── 3. 高阶洞察 ──

def _generate_advanced_insights(since: datetime, stats: dict, patterns: list) -> list[str]:
    """生成高阶洞察（结合规则 + 数据）。"""
    insights = []

    # 从巩固洞察中获取
    consolidation_insights = get_latest_insights()
    insights.extend(consolidation_insights)

    # 基于统计的洞察
    if stats.get("success_rate", 100) < 60:
        insights.append("任务成功率偏低，建议检查失败步骤并优化流程")

    if stats.get("avg_cost_time", 0) > 120:
        insights.append(f"平均任务耗时 {stats['avg_cost_time']:.0f} 秒，建议拆分复杂任务或优化步骤")

    # 基于模式的洞察
    for p in patterns:
        if p.get("type") == "quality_trend" and p.get("direction") == "declining":
            insights.append("近期任务质量有下降趋势，建议回顾上次成功的执行方式")
        if p.get("type") == "type_concentration" and p.get("concentration", 0) > 80:
            insights.append(f"任务类型过于集中在「{p.get('top_type')}」，建议关注其他类型任务")

    # 去重
    return list(set(insights))[:5]


# ── 4. 改进建议 ──

def _generate_improvement_suggestions(stats: dict, patterns: list, insights: list) -> list[dict]:
    """生成可操作的改进建议。"""
    suggestions = []

    # 基于成功率的建议
    if stats.get("success_rate", 100) < 70:
        suggestions.append({
            "area": "执行成功率",
            "suggestion": "建议将复杂任务拆分为更小的步骤，每步完成后检查",
            "priority": "high",
        })

    # 基于耗时的建议
    if stats.get("avg_cost_time", 0) > 60:
        suggestions.append({
            "area": "执行效率",
            "suggestion": "考虑将可并行的步骤同时执行，减少总耗时",
            "priority": "medium",
        })

    # 基于反馈的建议
    feedback_dist = stats.get("feedback_distribution", {})
    if feedback_dist.get("modify", 0) > feedback_dist.get("praise", 0):
        suggestions.append({
            "area": "输出质量",
            "suggestion": "用户修改次数多于点赞，建议检查输出是否符合偏好",
            "priority": "high",
        })

    # 基于类型的建议
    type_dist = stats.get("type_distribution", {})
    if len(type_dist) == 1:
        suggestions.append({
            "area": "任务多样性",
            "suggestion": "近期只有一种任务类型，建议尝试其他功能",
            "priority": "low",
        })

    return suggestions


# ── 5. 趋势对比 ──

def _compare_periods(prev_stats: dict, curr_stats: dict) -> dict[str, Any]:
    """对比两个周期的变化趋势（安全处理上期无数据）。"""
    trend = {}

    # 任务量变化
    prev_total = prev_stats.get("total_tasks", 0)
    curr_total = curr_stats.get("total_tasks", 0)
    if prev_total > 0:
        change = (curr_total - prev_total) / prev_total * 100
        trend["task_volume"] = f"{'↑' if change > 0 else '↓'} {abs(change):.0f}%"
    elif curr_total > 0:
        trend["task_volume"] = "新增（上期无数据）"

    # 成功率变化
    prev_sr = prev_stats.get("success_rate", 0)
    curr_sr = curr_stats.get("success_rate", 0)
    if prev_sr > 0:
        diff = curr_sr - prev_sr
        trend["success_rate"] = f"{'↑' if diff > 0 else '↓'} {abs(diff):.1f}%"
    elif curr_sr > 0:
        trend["success_rate"] = "新增（上期无数据）"

    # 分数变化
    prev_score = max(prev_stats.get("avg_work_score", 0), prev_stats.get("avg_life_score", 0))
    curr_score = max(curr_stats.get("avg_work_score", 0), curr_stats.get("avg_life_score", 0))
    if prev_score > 0:
        diff = curr_score - prev_score
        trend["quality"] = f"{'↑' if diff > 0 else '↓'} {abs(diff):.1f} 分"
    elif curr_score > 0:
        trend["quality"] = "新增（上期无数据）"

    # 如果所有维度都无数据
    if not trend:
        trend["status"] = "首次生成，无对比数据"

    return trend


# ── 6. 存储与检索 ──

def _store_reflection_report(report: dict) -> None:
    """存储反思报告（按日期保留历史 + latest 快捷入口）。"""
    try:
        from memory_store.sqlite_db import get_conn
        conn = get_conn()
        try:
            period = report.get("period", "weekly")
            today = datetime.now().strftime("%Y-%m-%d")
            report_json = json.dumps(report, ensure_ascii=False, default=str)

            # 1. 存储到巩固日志（永久历史）
            conn.execute(
                """INSERT INTO consolidation_log
                   (consolidation_type, source_count, result_summary, result_detail, period_start, period_end)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ("reflection_report", report.get("statistics", {}).get("total_tasks", 0),
                 report.get("reflection", "")[:200], report_json[:2000],
                 report.get("period_start", ""), report.get("period_end", "")),
            )

            # 2. 更新 latest 快捷入口
            latest_key = f"reflection:{period}:latest"
            existing = conn.execute(
                "SELECT pref_key FROM user_preference WHERE pref_key = ?", (latest_key,)
            ).fetchone()
            if existing:
                conn.execute(
                    """UPDATE user_preference SET
                        pref_value = ?, update_time = ? WHERE pref_key = ?""",
                    (report_json, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), latest_key),
                )
            else:
                conn.execute(
                    """INSERT INTO user_preference
                       (pref_key, pref_value, confidence, evidence_count, last_evidence)
                       VALUES (?, ?, 0.8, 1, ?)""",
                    (latest_key, report_json, f"反思报告 {today}"),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.debug("反思报告存储失败: %s", e)


def get_latest_reflection(period: str = "weekly") -> dict[str, Any]:
    """获取最新反思报告。"""
    try:
        from memory_store.sqlite_db import get_conn
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT pref_value FROM user_preference WHERE pref_key = ?",
                (f"reflection:{period}:latest",),
            ).fetchone()

            if row:
                return json.loads(row["pref_value"])
            return {}
        finally:
            conn.close()
    except Exception:
        return {}


def get_reflection_history(period: str = "weekly", limit: int = 10) -> list[dict]:
    """获取反思历史（从巩固日志中提取）。"""
    try:
        from memory_store.sqlite_db import get_conn
        conn = get_conn()
        try:
            rows = conn.execute(
                """SELECT * FROM consolidation_log
                   WHERE consolidation_type = 'insight_generate'
                   ORDER BY create_time DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    except Exception:
        return []
