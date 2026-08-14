"""流程冗余步骤精简（LLM 分析 + 规则兜底）。"""
import logging
from typing import Any

from agent_core.llm_client import chat_json

logger = logging.getLogger(__name__)


_OPTIMIZE_SYSTEM_PROMPT = """你是一个流程优化专家。分析给定的任务执行步骤，找出冗余环节并给出优化建议。

规则：
1. 检查是否有重复或可以合并的步骤
2. 检查是否有可以并行执行的串行步骤
3. 检查是否有不必要的中间步骤
4. 返回优化后的步骤列表

返回严格 JSON：
{
  "optimized": true/false,
  "reason": "优化原因",
  "steps": [{"name": "步骤名", "description": "描述", "step_type": "action|parallel"}]
}"""


def optimize(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """识别并精简冗余步骤。"""
    if len(steps) <= 2:
        return steps

    # 尝试 LLM 优化
    optimized = _optimize_with_llm(steps)
    if optimized and len(optimized) < len(steps):
        logger.info("流程优化: %d 步 → %d 步", len(steps), len(optimized))
        return optimized

    # 兜底：规则优化
    return _optimize_with_rules(steps)


def _optimize_with_llm(steps: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    """用 LLM 优化流程。"""
    try:
        steps_text = "\n".join(
            f"{i+1}. [{s.get('step_type', 'action')}] {s['name']}: {s.get('desc', '')}"
            for i, s in enumerate(steps)
        )
        resp = chat_json([
            {"role": "system", "content": _OPTIMIZE_SYSTEM_PROMPT},
            {"role": "user", "content": f"请优化以下 {len(steps)} 个步骤:\n{steps_text}"},
        ], max_tokens=1024)

        if resp.get("optimized") and resp.get("steps"):
            return resp["steps"]
        return None
    except Exception as e:
        logger.warning("LLM 流程优化失败: %s", e)
        return None


def _optimize_with_rules(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """规则式优化：合并同名步骤。"""
    seen = set()
    result = []
    for s in steps:
        key = s.get("name", "")
        if key not in seen:
            seen.add(key)
            result.append(s)
    return result if len(result) < len(steps) else steps


def detect_duplicate(steps: list[dict[str, Any]]) -> list[int]:
    """检测重复步骤的索引。"""
    seen = {}
    duplicates = []
    for i, s in enumerate(steps):
        key = s.get("name", "")
        if key in seen:
            duplicates.append(i)
        else:
            seen[key] = i
    return duplicates
