"""流程冗余步骤精简（LLM 分析 + 规则兜底，真实可用）。"""
import logging
from typing import Any

from agent_core.llm_client import chat_json

logger = logging.getLogger(__name__)


_OPTIMIZE_SYSTEM_PROMPT = """你是一个流程优化专家。分析给定的任务执行步骤，找出冗余环节并给出优化建议。

规则：
1. 检查是否有重复或可以合并的步骤（语义相同或高度重叠的步骤应合并）
2. 检查是否有可以并行执行的串行步骤（无数据依赖的步骤可改为 parallel）
3. 检查是否有不必要的中间步骤（如重复确认、冗余检查）
4. 返回优化后的步骤列表

返回严格 JSON：
{
  "optimized": true/false,
  "reason": "优化原因",
  "steps": [{"name": "步骤名", "description": "描述", "step_type": "action|parallel"}]
}"""


def optimize(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """识别并精简冗余步骤（LLM 优先，规则兜底）。"""
    if len(steps) <= 2:
        return steps

    # 尝试 LLM 优化
    optimized = _optimize_with_llm(steps)
    if optimized and len(optimized) < len(steps):
        logger.info("LLM 流程优化: %d 步 → %d 步", len(steps), len(optimized))
        return optimized

    # 兜底：规则优化（语义合并 + 并行检测）
    rule_result = _optimize_with_rules(steps)
    if len(rule_result) < len(steps):
        logger.info("规则流程优化: %d 步 → %d 步", len(steps), len(rule_result))
        return rule_result

    return steps


def _optimize_with_llm(steps: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    """用 LLM 优化流程。"""
    try:
        steps_text = "\n".join(
            f"{i+1}. [{s.get('step_type', 'action')}] {s['name']}: {s.get('description', s.get('desc', ''))}"
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


# ── 同义词/近义词映射表（用于语义合并） ──
_SYNONYM_MAP = {
    "理解": ["了解", "分析", "解析", "梳理", "明确"],
    "收集": ["采集", "获取", "整理", "汇总", "归纳"],
    "生成": ["创建", "编写", "输出", "撰写", "制作"],
    "检查": ["校验", "验证", "确认", "核对", "审查"],
    "汇总": ["总结", "整合", "归纳", "合并"],
    "保存": ["存储", "记录", "写入", "归档"],
    "发送": ["推送", "通知", "传递"],
}

# 构建反向映射：同义词 → 规范词
_SYNONYM_REVERSE: dict[str, str] = {}
for _canonical, _synonyms in _SYNONYM_MAP.items():
    for _s in _synonyms:
        _SYNONYM_REVERSE[_s] = _canonical
    _SYNONYM_REVERSE[_canonical] = _canonical


def _extract_action_verb(name: str) -> str:
    """从步骤名中提取核心动作动词（规范化后）。

    例如：
    - "收集数据" → "收集"
    - "采集信息" → "收集"（采集是收集的同义词）
    - "生成报告" → "生成"
    """
    for key, canon in _SYNONYM_REVERSE.items():
        if key in name:
            return canon
    return name[:2] if len(name) >= 2 else name


def _canonicalize(name: str) -> str:
    """将步骤名归一化为规范形式（用于语义去重）。

    只比较核心动作动词，忽略宾语差异。
    例如"收集数据"和"采集信息"都归一化为"收集"。
    """
    return _extract_action_verb(name)


def _optimize_with_rules(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """规则式优化：语义去重 + 并行检测 + 冗余移除。"""
    # 1. 语义去重：合并同义步骤
    result = _merge_synonym_steps(steps)

    # 2. 并行检测：无依赖的相邻独立步骤标记为 parallel
    result = _detect_parallelizable(result)

    # 3. 移除冗余的中间步骤（如"等待确认"、"检查进度"等无实际产出的步骤）
    result = _remove_redundant_steps(result)

    return result


def _merge_synonym_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """合并语义相同的步骤。"""
    seen: dict[str, int] = {}  # canonical_name → index in result
    result = []

    for step in steps:
        name = step.get("name", "")
        canonical = _canonicalize(name)

        if canonical in seen:
            # 合并：保留第一个，把描述拼接到已有步骤
            existing_idx = seen[canonical]
            existing = result[existing_idx]
            old_desc = existing.get("description", existing.get("desc", ""))
            new_desc = step.get("description", step.get("desc", ""))
            if new_desc and new_desc != old_desc:
                merged = old_desc + "；" + new_desc[:100]
                if "description" in existing:
                    existing["description"] = merged
                elif "desc" in existing:
                    existing["desc"] = merged
        else:
            seen[canonical] = len(result)
            result.append(dict(step))

    return result


def _detect_parallelizable(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """检测可并行的步骤（无数据依赖的独立步骤）。"""
    if len(steps) < 3:
        return steps

    # 常见可并行标记：涉及不同对象/数据源/模块的步骤
    PARALLEL_KEYWORDS = ["统计数据", "整理资料", "收集信息", "读取文件", "分析数据"]

    for i, step in enumerate(steps):
        name = step.get("name", "")
        desc = step.get("description", step.get("desc", ""))
        combined = name + desc

        # 第一个步骤通常是"理解需求"，最后一个是"汇总输出"，不并行
        if i == 0 or i == len(steps) - 1:
            continue

        # 如果步骤名/描述中含有可并行关键词，且不是决策节点
        if any(kw in combined for kw in PARALLEL_KEYWORDS):
            if step.get("step_type", "action") == "action":
                step["step_type"] = "parallel"

    return steps


def _remove_redundant_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """移除冗余的中间步骤。"""
    # 冗余模式：无实际产出的确认/等待步骤
    REDUNDANT_PATTERNS = [
        "等待确认", "检查进度", "等待反馈", "再次确认",
        "等待审批", "等待回复", "暂停等待",
    ]
    result = []
    for step in steps:
        name = step.get("name", "")
        if any(pat in name for pat in REDUNDANT_PATTERNS):
            continue
        result.append(step)
    return result


def detect_duplicate(steps: list[dict[str, Any]]) -> list[int]:
    """检测重复步骤的索引（语义级）。"""
    seen: dict[str, int] = {}
    duplicates = []
    for i, s in enumerate(steps):
        canonical = _canonicalize(s.get("name", ""))
        if canonical in seen:
            duplicates.append(i)
        else:
            seen[canonical] = i
    return duplicates
