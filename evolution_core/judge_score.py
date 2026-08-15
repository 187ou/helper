"""演化裁判：多维度打分系统 + 趋势分析（含完整边缘处理）。

边缘情况处理：
1. result 为 None/空 → 返回默认分数
2. 缺失字段 → 使用安全默认值
3. LLM 超时/失败 → 自动降级到规则打分
4. LLM 返回非法 JSON → 尝试修复 + 降级
5. 零除（空步骤列表）→ 返回 0
6. 分数溢出 → 限幅到 0-100
7. 历史数据为空 → 返回 insufficient_data
"""
import json
import logging
from datetime import datetime
from typing import Any

from evolution_core.safe_ops import (
    safe_llm_json, safe_divide, safe_avg, clamp_value,
    validate_task_result,
)

logger = logging.getLogger(__name__)

# 维度权重（按任务类型差异化）
_DIMENSION_WEIGHTS = {
    "work": {
        "completeness": 0.25, "efficiency": 0.20, "quality": 0.25,
        "consistency": 0.15, "satisfaction": 0.10, "novelty": 0.05,
    },
    "life": {
        "completeness": 0.20, "efficiency": 0.15, "quality": 0.20,
        "consistency": 0.15, "satisfaction": 0.20, "novelty": 0.10,
    },
    "mix": {
        "completeness": 0.25, "efficiency": 0.20, "quality": 0.20,
        "consistency": 0.15, "satisfaction": 0.15, "novelty": 0.05,
    },
}

_SCORE_SYSTEM_PROMPT = """你是一个任务质量评估专家。根据任务执行结果，从 6 个维度打分（每项 0-100）：

评分维度：
1. 完成度 (completeness): 所有步骤是否完整执行
2. 效率 (efficiency): 执行耗时是否合理
3. 质量 (quality): 输出内容是否具体、可操作
4. 一致性 (consistency): 与标准流程是否一致
5. 用户满意度 (satisfaction): 预估用户满意程度
6. 创新度 (novelty): 相比常规是否有改进

返回严格 JSON，不要 markdown：
{"completeness": 0-100, "efficiency": 0-100, "quality": 0-100, "consistency": 0-100, "satisfaction": 0-100, "novelty": 0-100, "overall": 0-100, "reason": "评价", "suggestion": "建议"}"""


def score_task(result: dict[str, Any], task_type: str = "work") -> dict[str, Any]:
    """多维度打分（LLM 优先，规则兜底）。"""
    # 边缘：验证并补全字段
    result = validate_task_result(result)

    # 尝试 LLM 打分
    try:
        llm_scores = _llm_score(result, task_type)
        if llm_scores:
            return llm_scores
    except Exception as e:
        logger.warning("LLM 打分异常: %s", e)

    # 规则兜底
    return _rule_score(result, task_type)


def score_work(result: dict[str, Any]) -> float:
    """工作维度打分（兼容旧接口）。"""
    scores = score_task(result, "work")
    return scores.get("overall", 0)


def score_life(result: dict[str, Any]) -> float:
    """生活维度打分（兼容旧接口）。"""
    scores = score_task(result, "life")
    return scores.get("overall", 0)


def combined_score(work: float, life: float, task_type: str) -> float:
    """综合打分（兼容旧接口）。"""
    if task_type == "work":
        return work
    if task_type == "life":
        return life
    return (work + life) / 2


def analyze_score_trend(task_type: str = "", window: int = 10) -> dict[str, Any]:
    """分析分数趋势。"""
    window = clamp_value(window, 1, 1000)

    from memory_store.sqlite_db import get_conn
    conn = get_conn()
    try:
        if task_type:
            rows = conn.execute(
                """SELECT work_score, life_score, create_time FROM task_list
                   WHERE task_type = ? AND status = 'success'
                   ORDER BY create_time DESC LIMIT ?""",
                (task_type, int(window)),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT work_score, life_score, create_time FROM task_list
                   WHERE status = 'success'
                   ORDER BY create_time DESC LIMIT ?""",
                (int(window),),
            ).fetchall()
    except Exception:
        return {"trend": "insufficient_data", "average": 0, "change": 0}
    finally:
        conn.close()

    if not rows:
        return {"trend": "insufficient_data", "average": 0, "change": 0}

    work_scores = [r["work_score"] for r in rows if r["work_score"] > 0]
    life_scores = [r["life_score"] for r in rows if r["life_score"] > 0]

    avg_work = safe_avg(work_scores)
    avg_life = safe_avg(life_scores)

    # 环比变化
    mid = len(rows) // 2
    if mid > 0:
        first_half = [r["work_score"] for r in rows[:mid] if r["work_score"] > 0]
        second_half = [r["work_score"] for r in rows[mid:] if r["work_score"] > 0]
        first_avg = safe_avg(first_half)
        second_avg = safe_avg(second_half)
        change = second_avg - first_avg
    else:
        change = 0

    if change > 5:
        trend = "improving"
    elif change < -5:
        trend = "declining"
    else:
        trend = "stable"

    return {
        "trend": trend,
        "average_work": round(avg_work, 1),
        "average_life": round(avg_life, 1),
        "change": round(change, 1),
        "sample_count": len(rows),
    }


def get_dimension_analysis(result: dict[str, Any]) -> dict[str, str]:
    """获取各维度分析文本。"""
    result = validate_task_result(result)
    scores = score_task(result, result.get("task_type", "work"))

    analysis = {}
    dimension_labels = {
        "completeness": "完成度", "efficiency": "效率", "quality": "质量",
        "consistency": "一致性", "satisfaction": "满意度", "novelty": "创新度",
    }

    for dim, label in dimension_labels.items():
        score = scores.get(dim, 0)
        if score >= 80:
            level = "优秀"
        elif score >= 60:
            level = "良好"
        elif score >= 40:
            level = "一般"
        else:
            level = "待改进"
        analysis[dim] = f"{label}: {score}分 ({level})"

    return analysis


# ── 内部实现 ──

def _llm_score(result: dict[str, Any], task_type: str) -> dict[str, Any] | None:
    """LLM 多维度打分。"""
    try:
        task_text = result.get("task_text", "")
        step_results = result.get("step_results", [])
        cost_time = result.get("cost_time", 0)
        logs = result.get("logs", [])
        steps = result.get("steps", [])

        summary = f"任务: {task_text}\n类型: {task_type}\n耗时: {cost_time:.1f}秒\n"
        summary += f"计划: {len(steps)} 步, 完成: {len(step_results)} 步\n"

        if step_results:
            for r in step_results:
                summary += f"  - [{r.get('name', '?')}] {str(r.get('result', ''))[:100]}\n"
        if logs:
            summary += f"日志: {'; '.join(str(l) for l in logs[-3:])}"

        resp = safe_llm_json([
            {"role": "system", "content": _SCORE_SYSTEM_PROMPT},
            {"role": "user", "content": summary},
        ], max_tokens=512, default=None)

        if not resp:
            return None

        if "overall" in resp:
            for dim in ["completeness", "efficiency", "quality", "consistency", "satisfaction", "novelty"]:
                if dim not in resp:
                    resp[dim] = 60

            weights = _DIMENSION_WEIGHTS.get(task_type, _DIMENSION_WEIGHTS["work"])
            weighted_total = sum(clamp_value(resp.get(dim, 60), 0, 100) * w for dim, w in weights.items())
            resp["overall"] = round(weighted_total, 1)
            resp["dimensions"] = {dim: clamp_value(resp.get(dim, 60), 0, 100) for dim in weights}

            logger.info("LLM 打分: overall=%.1f", resp["overall"])
            return resp
        return None
    except Exception as e:
        logger.warning("LLM 打分失败: %s", e)
        return None


def _rule_score(result: dict[str, Any], task_type: str) -> dict[str, Any]:
    """规则多维度打分（兜底）。"""
    steps = result.get("steps", [])
    step_results = result.get("step_results", [])
    cost_time = result.get("cost_time", 0)
    status = result.get("status", "")

    # 1. 完成度
    total_steps = max(len(steps), 1)
    completed = len(step_results)
    completeness = clamp_value(int(safe_divide(completed, total_steps) * 100), 0, 100)

    # 2. 效率
    if 5 <= cost_time <= 30:
        efficiency = 90
    elif 30 < cost_time <= 60:
        efficiency = 75
    elif 60 < cost_time <= 120:
        efficiency = 60
    elif cost_time < 5:
        efficiency = 70
    elif cost_time > 120:
        efficiency = 40
    else:
        efficiency = 60

    # 3. 质量
    if step_results:
        try:
            avg_len = safe_avg([len(str(r.get("result", ""))) for r in step_results])
            quality = clamp_value(int(avg_len / 2), 0, 100)
        except Exception:
            quality = 50
    else:
        quality = 30

    # 4. 一致性
    consistency = completeness

    # 5. 满意度
    satisfaction = 80 if status == "success" and completeness >= 80 else 60

    # 6. 创新度
    novelty = 50

    scores = {
        "completeness": completeness,
        "efficiency": efficiency,
        "quality": quality,
        "consistency": consistency,
        "satisfaction": satisfaction,
        "novelty": novelty,
    }

    weights = _DIMENSION_WEIGHTS.get(task_type, _DIMENSION_WEIGHTS["work"])
    overall = sum(scores[dim] * w for dim, w in weights.items())

    scores["overall"] = round(overall, 1)
    scores["dimensions"] = scores.copy()
    scores["reason"] = "规则打分（LLM 不可用）"
    scores["suggestion"] = _generate_suggestion(scores)

    return scores


def _generate_suggestion(scores: dict[str, Any]) -> str:
    """基于得分生成改进建议。"""
    suggestions = []
    if scores.get("completeness", 100) < 60:
        suggestions.append("提高步骤完成率")
    if scores.get("efficiency", 100) < 60:
        suggestions.append("优化执行效率")
    if scores.get("quality", 100) < 60:
        suggestions.append("提升输出质量")
    if scores.get("satisfaction", 100) < 60:
        suggestions.append("关注用户反馈")
    return "；".join(suggestions) if suggestions else "继续保持"
