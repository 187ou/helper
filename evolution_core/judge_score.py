"""演化裁判：工作/生活双维度打分（LLM 驱动 + 规则兜底）。"""
import logging
from typing import Any

from agent_core.llm_client import chat_json
from config.app_const import WORK_SCORE_WEIGHTS, LIFE_SCORE_WEIGHTS

logger = logging.getLogger(__name__)


_SCORE_SYSTEM_PROMPT = """你是一个任务质量评估助手。根据任务执行结果，从工作/生活两个维度打分。

评分维度：
- 工作侧：数据准确率(0-25)、文书完整度(0-25)、材料规范度(0-25)、执行耗时(0-25)
- 生活侧：开销统计精准度(0-25)、日程贴合度(0-25)、资料归档完整度(0-25)、偏好匹配度(0-25)

返回严格 JSON：
{"work_score": 0-100, "life_score": 0-100, "reason": "简短评价", "suggestion": "改进建议"}"""


def score_work(result: dict[str, Any]) -> float:
    """工作维度打分 0-100（LLM 优先，失败则规则）。"""
    llm_score = get_llm_scores(result)
    return llm_score.get("work_score", _rule_score_work(result))


def score_life(result: dict[str, Any]) -> float:
    """生活维度打分 0-100（LLM 优先，失败则规则）。"""
    llm_score = get_llm_scores(result)
    return llm_score.get("life_score", _rule_score_life(result))


def get_llm_scores(result: dict[str, Any]) -> dict:
    """获取 LLM 打分结果（带缓存，整个任务只调用一次 LLM）。"""
    if "_cached_llm_scores" in result:
        return result["_cached_llm_scores"]
    scores = _llm_score(result)
    result["_cached_llm_scores"] = scores if scores else {}
    return result["_cached_llm_scores"]


def combined_score(work: float, life: float, task_type: str) -> float:
    """综合打分。"""
    if task_type == "work":
        return work
    if task_type == "life":
        return life
    return (work + life) / 2


def _llm_score(result: dict[str, Any]) -> dict | None:
    """用 LLM 打分。"""
    try:
        task_text = result.get("task_text", "")
        step_results = result.get("step_results", [])
        cost_time = result.get("cost_time", 0)
        logs = result.get("logs", [])

        summary = f"任务: {task_text}\n耗时: {cost_time:.1f}f\n"
        summary += f"执行步骤数: {len(step_results)}\n"
        if step_results:
            summary += "各步骤结果:\n"
            for r in step_results:
                summary += f"  - [{r['name']}] {r['result'][:150]}\n"
        if logs:
            summary += f"日志: {'; '.join(logs[-3:])}"

        resp = chat_json([
            {"role": "system", "content": _SCORE_SYSTEM_PROMPT},
            {"role": "user", "content": summary},
        ], max_tokens=512)

        if resp and "work_score" in resp and "life_score" in resp:
            logger.info("LLM 打分: work=%s life=%s", resp["work_score"], resp["life_score"])
            return resp
        return None
    except Exception as e:
        logger.warning("LLM 打分失败: %s", e)
        return None


def _rule_score_work(result: dict[str, Any]) -> float:
    """规则兜底：工作打分。"""
    base = 65.0
    cost = result.get("cost_time", 0)
    steps = len(result.get("steps", []))
    results_count = len(result.get("step_results", []))

    if steps > 0 and results_count >= steps - 1:
        base += 10
    if 5 < cost < 120:
        base += 5
    if result.get("status") == "success":
        base += 10
    return min(100.0, base)


def _rule_score_life(result: dict[str, Any]) -> float:
    """规则兜底：生活打分。"""
    base = 65.0
    if result.get("status") == "success":
        base += 10
    results_count = len(result.get("step_results", []))
    if results_count >= 3:
        base += 10
    return min(100.0, base)
