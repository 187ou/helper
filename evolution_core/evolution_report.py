"""演化报告生成：自动生成日/周/里程碑级演化总结（含完整边缘处理）。

边缘情况处理：
1. 无数据 → 返回空报告 + 提示
2. DB 读取失败 → 返回部分数据
3. JSON 解析失败 → 使用默认值
4. 除零（无任务）→ 成功率返回 0
5. 报告持久化失败 → 仍返回报告内容
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any

from memory_store.sqlite_db import get_conn, now_str
from evolution_core.judge_score import analyze_score_trend, score_task
from evolution_core.weight_evolve import get_habit_profile, get_top_habits
from evolution_core.pattern_miner import get_top_patterns
from evolution_core.feedback_learner import analyze_feedback_trends, get_all_preferences
from evolution_core.safe_ops import safe_divide, safe_avg, safe_json_loads, clamp_value

logger = logging.getLogger(__name__)


def generate_daily_report() -> dict[str, Any]:
    """生成每日演化报告。"""
    today = datetime.now().strftime("%Y-%m-%d")
    return _generate_report("daily", today, today)


def generate_weekly_report() -> dict[str, Any]:
    """生成每周演化报告。"""
    today = datetime.now()
    start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    end = today.strftime("%Y-%m-%d")
    return _generate_report("weekly", start, end)


def generate_milestone_report() -> dict[str, Any]:
    """生成里程碑报告（全部历史）。"""
    return _generate_report("milestone", "", "")


def get_latest_report(report_type: str = "daily") -> dict[str, Any] | None:
    """获取最新报告。"""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM evolution_report WHERE report_type = ? ORDER BY id DESC LIMIT 1",
            (report_type,)
        ).fetchone()
    except Exception:
        return None
    finally:
        conn.close()

    if not row:
        return None

    d = dict(row)
    d["content"] = safe_json_loads(d.get("content"), default={})
    d["highlights"] = safe_json_loads(d.get("highlights"), default=[])
    d["suggestions"] = safe_json_loads(d.get("suggestions"), default=[])
    d["score_trend"] = safe_json_loads(d.get("score_trend"), default=[])
    return d


# ── 内部实现 ──

def _generate_report(report_type: str, period_start: str, period_end: str) -> dict[str, Any]:
    """生成报告核心逻辑。"""
    # 获取数据（每个步骤独立容错）
    task_stats = _safe_get_task_stats(period_start, period_end)
    score_trend = _safe_analyze_score_trend()
    patterns = _safe_get_patterns()
    preferences = _safe_get_preferences()
    habits = _safe_get_habits()
    habit_profile = _safe_get_habit_profile()
    feedback_trend = _safe_analyze_feedback()

    highlights = _generate_highlights(task_stats, score_trend, patterns, habits)
    suggestions = _generate_suggestions(task_stats, score_trend, feedback_trend, habits)

    report = {
        "type": report_type,
        "period": {"start": period_start, "end": period_end},
        "generated_at": now_str(),
        "task_stats": task_stats,
        "score_trend": score_trend,
        "patterns": patterns,
        "preferences": preferences[:5],
        "habits": habits[:10],
        "habit_profile": {k: len(v) for k, v in habit_profile.items()},
        "feedback_trend": feedback_trend,
    }

    # 持久化（失败不影响返回）
    try:
        _save_report(report_type, period_start, period_end, report, highlights, suggestions, score_trend)
    except Exception as e:
        logger.warning("报告持久化失败: %s", e)

    logger.info("生成报告: %s (%s ~ %s)", report_type, period_start, period_end)
    return report


def _safe_get_task_stats(period_start: str, period_end: str) -> dict[str, Any]:
    """安全获取任务统计。"""
    conn = get_conn()
    try:
        if period_start and period_end:
            date_filter = "AND create_time BETWEEN ? AND ?"
            date_params = (period_start, period_end + " 23:59:59")
        else:
            date_filter = ""
            date_params = ()

        total = conn.execute(
            f"SELECT COUNT(*) FROM task_list WHERE 1=1 {date_filter}", date_params
        ).fetchone()[0]

        success = conn.execute(
            f"SELECT COUNT(*) FROM task_list WHERE status = 'success' {date_filter}", date_params
        ).fetchone()[0]

        avg_score = conn.execute(
            f"SELECT AVG(work_score) FROM task_list WHERE work_score > 0 {date_filter}", date_params
        ).fetchone()[0]

        avg_duration = conn.execute(
            f"SELECT AVG(cost_time) FROM task_list WHERE cost_time > 0 {date_filter}", date_params
        ).fetchone()[0]

        type_stats = {}
        for row in conn.execute(
            f"""SELECT task_type, COUNT(*) as cnt FROM task_list
                WHERE 1=1 {date_filter} GROUP BY task_type""", date_params
        ):
            type_stats[row["task_type"]] = row["cnt"]

        return {
            "total": total,
            "success": success,
            "success_rate": round(safe_divide(success, total) * 100, 1),
            "average_score": round(avg_score, 1) if avg_score else 0,
            "average_duration": round(avg_duration, 1) if avg_duration else 0,
            "by_type": type_stats,
        }
    except Exception as e:
        logger.warning("任务统计获取失败: %s", e)
        return {"total": 0, "success": 0, "success_rate": 0, "average_score": 0, "average_duration": 0, "by_type": {}}
    finally:
        conn.close()


def _safe_analyze_score_trend() -> dict[str, Any]:
    """安全分析分数趋势。"""
    try:
        return analyze_score_trend(window=20)
    except Exception:
        return {"trend": "insufficient_data", "average": 0, "change": 0}


def _safe_get_patterns() -> list:
    """安全获取模式。"""
    try:
        return get_top_patterns(n=5, min_confidence=0.3)
    except Exception:
        return []


def _safe_get_preferences() -> list:
    """安全获取偏好。"""
    try:
        return get_all_preferences()
    except Exception:
        return []


def _safe_get_habits() -> list:
    """安全获取习惯。"""
    try:
        return get_top_habits(n=10)
    except Exception:
        return []


def _safe_get_habit_profile() -> dict:
    """安全获取习惯画像。"""
    try:
        return get_habit_profile()
    except Exception:
        return {"work": [], "life": [], "health": [], "other": []}


def _safe_analyze_feedback() -> dict:
    """安全分析反馈。"""
    try:
        return analyze_feedback_trends(days=30)
    except Exception:
        return {"total": 0, "satisfaction": 0, "by_type": {}}


def _generate_highlights(task_stats: dict, score_trend: dict, patterns: list, habits: list) -> list[str]:
    """生成亮点摘要。"""
    highlights = []

    success_rate = task_stats.get("success_rate", 0)
    if success_rate >= 80:
        highlights.append(f"任务成功率 {success_rate}%，表现优秀")
    elif success_rate >= 60:
        highlights.append(f"任务成功率 {success_rate}%，表现良好")

    if score_trend.get("trend") == "improving":
        highlights.append(f"分数呈上升趋势，平均 {score_trend.get('average_work', 0)} 分")
    elif score_trend.get("trend") == "stable":
        highlights.append(f"分数稳定，平均 {score_trend.get('average_work', 0)} 分")

    if patterns:
        best = patterns[0]
        highlights.append(f"发现高置信度模式「{best['pattern_key']}」(置信度 {best['confidence']})")

    if habits:
        top = habits[0]
        highlights.append(f"高频习惯「{top['habit_key']}」权重 {top['weight']}")

    if not highlights:
        highlights.append("继续积累数据，系统将生成更有价值的洞察")

    return highlights


def _generate_suggestions(task_stats: dict, score_trend: dict, feedback_trend: dict, habits: list) -> list[str]:
    """生成改进建议。"""
    suggestions = []

    success_rate = task_stats.get("success_rate", 0)
    if success_rate < 60:
        suggestions.append("任务成功率偏低，建议检查任务拆解粒度")

    if score_trend.get("trend") == "declining":
        suggestions.append("分数呈下降趋势，建议关注近期任务质量")

    if feedback_trend.get("satisfaction", 1) < 0.5:
        suggestions.append("用户满意度较低，建议收集更多反馈优化输出")

    if not habits:
        suggestions.append("习惯数据不足，建议多使用系统积累个性化数据")

    low_habits = [h for h in habits if h.get("weight", 5) < 3]
    if low_habits:
        suggestions.append(f"有 {len(low_habits)} 个习惯权重较低，建议增加相关任务频率")

    if not suggestions:
        suggestions.append("系统运行良好，继续保持当前使用习惯")

    return suggestions


def _save_report(report_type: str, period_start: str, period_end: str,
                 content: dict, highlights: list[str], suggestions: list[str],
                 score_trend: dict) -> None:
    """持久化报告。"""
    conn = get_conn()
    try:
        conn.execute(
            """INSERT INTO evolution_report
               (report_type, period_start, period_end, content, highlights, suggestions, score_trend)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                report_type, period_start, period_end,
                json.dumps(content, ensure_ascii=False, default=str),
                json.dumps(highlights, ensure_ascii=False),
                json.dumps(suggestions, ensure_ascii=False),
                json.dumps(score_trend, ensure_ascii=False),
            ),
        )
        conn.commit()
    finally:
        conn.close()
