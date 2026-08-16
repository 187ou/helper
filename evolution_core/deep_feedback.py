"""反馈学习深化：用 LLM 分析修改意图，检测语义级变化。

核心能力：
1. LLM 驱动的意图分析（理解用户为什么修改）
2. 语义级差异检测（不只是长度/格式）
3. 结构化偏好提炼（从自然语言修改中提取规则）
4. 偏好冲突检测与解决

边缘处理：
- LLM 不可用 → 降级到规则分析
- 分析结果格式错误 → 容错解析
- 偏好冲突 → 基于置信度解决
"""
import json
import logging
from typing import Any

from evolution_core.safe_ops import safe_llm_json, safe_json_loads, sanitize_text

logger = logging.getLogger(__name__)

# LLM 分析提示词（从配置文件加载）
def _get_feedback_prompt() -> str:
    """获取反馈分析 prompt（优先配置文件，降级默认）。"""
    try:
        from config.prompt_manager import get_prompt
        prompt = get_prompt("feedback_analyze_prompt")
        if prompt:
            return prompt
    except Exception:
        pass
    return """你是一个用户行为分析专家。用户修改了 AI 的输出，请分析修改意图。
返回严格 JSON：{"modify_type": "style|structure|content|tone|format|other", "intent": "意图", "preference_rule": {"key": "键", "value": "值", "evidence": "证据"}, "confidence": 0-1}"""


_FEEDBACK_PROMPT_CACHE = None


def _get_feedback_prompt_cached() -> str:
    """获取反馈分析 prompt（缓存）。"""
    global _FEEDBACK_PROMPT_CACHE
    if _FEEDBACK_PROMPT_CACHE is None:
        _FEEDBACK_PROMPT_CACHE = _get_feedback_prompt()
    return _FEEDBACK_PROMPT_CACHE


def analyze_modification_deep(
    original: str,
    modified: str,
    task_type: str = "",
) -> dict[str, Any] | None:
    """深度分析用户修改（LLM 驱动）。

    相比规则分析的提升：
    - 能理解语义变化（"客户"→"用户"是术语统一）
    - 能识别结构重组（段落顺序调整）
    - 能提炼通用规则（不是只检测表面变化）

    Returns:
        分析结果字典，包含修改类型、意图、偏好规则
    """
    if not original or not modified or original == modified:
        return None

    # 尝试 LLM 分析
    llm_result = _analyze_with_llm(original, modified, task_type)
    if llm_result:
        return llm_result

    # 降级：规则分析
    return _analyze_with_rules(original, modified)


def _analyze_with_llm(original: str, modified: str, task_type: str) -> dict[str, Any] | None:
    """使用 LLM 分析修改意图。"""
    # 截断防止过长
    max_len = 1500
    original_short = sanitize_text(original, max_len)
    modified_short = sanitize_text(modified, max_len)

    context = f"任务类型: {task_type}\n\n" if task_type else ""
    context += f"## 原文\n{original_short}\n\n## 修改后\n{modified_short}"

    resp = safe_llm_json([
        {"role": "system", "content": _get_feedback_prompt_cached()},
        {"role": "user", "content": context},
    ], max_tokens=512, default=None)

    if not resp:
        return None

    # 验证结果格式
    if "modify_type" not in resp:
        return None

    # 标准化
    result = {
        "modify_type": resp.get("modify_type", "other"),
        "intent": resp.get("intent", ""),
        "confidence": min(max(resp.get("confidence", 0.5), 0), 1),
        "preference_rule": resp.get("preference_rule", {}),
        "details": resp.get("details", ""),
        "source": "llm",
    }

    logger.info("LLM 分析修改: type=%s, intent=%s", result["modify_type"], result["intent"][:50])
    return result


def _analyze_with_rules(original: str, modified: str) -> dict[str, Any] | None:
    """规则降级分析（不调 LLM）。"""
    if original == modified:
        return None

    # 长度变化
    len_diff = len(modified) - len(original)
    if abs(len_diff) > len(original) * 0.3:
        if len_diff < 0:
            return {
                "modify_type": "style",
                "intent": "用户偏好更简洁的表达",
                "confidence": 0.6,
                "preference_rule": {"key": "length:prefer", "value": "简洁", "evidence": f"从{len(original)}字精简到{len(modified)}字"},
                "source": "rule",
            }
        else:
            return {
                "modify_type": "content",
                "intent": "用户希望内容更详细",
                "confidence": 0.6,
                "preference_rule": {"key": "length:prefer", "value": "详细", "evidence": f"从{len(original)}字扩充到{len(modified)}字"},
                "source": "rule",
            }

    # 格式变化
    if "\n" in modified and "\n" not in original:
        return {
            "modify_type": "format",
            "intent": "用户偏好分段结构",
            "confidence": 0.5,
            "preference_rule": {"key": "format:prefer", "value": "分段结构", "evidence": "改为分段格式"},
            "source": "rule",
        }

    # 语气变化
    formal_words = ["因此", "综上所述", "特此"]
    casual_words = ["所以", "总的来说", "给你"]
    if sum(1 for w in formal_words if w in modified) > sum(1 for w in formal_words if w in original):
        return {
            "modify_type": "tone",
            "intent": "用户偏好正式语气",
            "confidence": 0.5,
            "preference_rule": {"key": "tone:prefer", "value": "正式", "evidence": "增加正式用语"},
            "source": "rule",
        }

    # 无法确定具体类型
    return {
        "modify_type": "other",
        "intent": "用户做了修改但意图不明显",
        "confidence": 0.3,
        "preference_rule": {},
        "source": "rule",
    }


def detect_preference_conflicts(preferences: list[dict]) -> list[dict]:
    """检测偏好冲突。

    冲突类型：
    - 同一 key 有多个不同值（如 style:prefer=正式 和 style:prefer=口语化）
    - 互斥偏好（如 length:prefer=简洁 和 length:prefer=详细）

    Returns:
        冲突列表，每个冲突包含冲突的偏好和解决建议
    """
    if not preferences:
        return []

    # 按 key 分组
    key_groups: dict[str, list[dict]] = {}
    for pref in preferences:
        key = pref.get("key", "")
        if key not in key_groups:
            key_groups[key] = []
        key_groups[key].append(pref)

    conflicts = []
    for key, group in key_groups.items():
        if len(group) <= 1:
            continue

        # 检查值是否不同
        values = set()
        for pref in group:
            val = pref.get("value")
            if isinstance(val, (list, dict)):
                val = json.dumps(val, ensure_ascii=False, sort_keys=True)
            values.add(str(val))

        if len(values) > 1:
            # 有冲突
            group.sort(key=lambda x: x.get("confidence", 0), reverse=True)
            winner = group[0]
            conflicts.append({
                "key": key,
                "conflicting_values": list(values),
                "resolution": "highest_confidence",
                "winner": winner,
                "losers": group[1:],
                "suggestion": f"保留置信度最高的偏好（{winner.get('value')}），移除其他",
            })

    return conflicts


def resolve_conflicts(preferences: list[dict]) -> list[dict]:
    """解决偏好冲突（基于置信度）。

    策略：同一 key 只保留置信度最高的值。
    """
    conflicts = detect_preference_conflicts(preferences)
    if not conflicts:
        return preferences

    # 收集需要移除的 key+value 组合
    to_remove = set()
    for conflict in conflicts:
        for loser in conflict.get("losers", []):
            to_remove.add((conflict["key"], str(loser.get("value"))))

    # 过滤
    resolved = []
    for pref in preferences:
        key = pref.get("key", "")
        val = str(pref.get("value"))
        if (key, val) not in to_remove:
            resolved.append(pref)

    logger.info("偏好冲突解决: %d 个冲突已解决", len(conflicts))
    return resolved


def generate_preference_summary(preferences: list[dict]) -> str:
    """生成偏好摘要（供 prompt 使用）。

    将结构化的偏好列表转化为自然语言描述，可直接拼接到 prompt 中。
    """
    if not preferences:
        return ""

    # 按类型分组
    style_prefs = []
    format_prefs = []
    tone_prefs = []
    length_prefs = []
    other_prefs = []

    for pref in preferences:
        if pref.get("confidence", 0) < 0.3:
            continue

        key = pref.get("key", "")
        value = pref.get("value")
        value_str = ", ".join(str(v) for v in value) if isinstance(value, list) else str(value)

        if "style" in key:
            style_prefs.append(value_str)
        elif "format" in key:
            format_prefs.append(value_str)
        elif "tone" in key:
            tone_prefs.append(value_str)
        elif "length" in key:
            length_prefs.append(value_str)
        else:
            other_prefs.append(value_str)

    parts = []
    if style_prefs:
        parts.append(f"文风偏好: {'/'.join(style_prefs)}")
    if format_prefs:
        parts.append(f"格式偏好: {'/'.join(format_prefs)}")
    if tone_prefs:
        parts.append(f"语气偏好: {'/'.join(tone_prefs)}")
    if length_prefs:
        parts.append(f"长度偏好: {'/'.join(length_prefs)}")
    if other_prefs:
        parts.append(f"其他偏好: {'/'.join(other_prefs)}")

    return "；".join(parts) if parts else ""
