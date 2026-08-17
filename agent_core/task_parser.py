"""自然语言任务拆解（演化感知：模板优先 → LLM → 规则）。

反馈闭环：
  parse() → 尝试演化推荐（模板/模式/默认）→ 执行 → learn_from_task() → 强化模式 → 下次更容易命中
"""
import json
import logging
import re
from dataclasses import dataclass, asdict
from typing import Any

from agent_core.llm_client import chat_json
from config.app_const import TaskType

logger = logging.getLogger(__name__)


@dataclass
class TaskStep:
    """单个任务步骤。"""
    index: int
    name: str
    description: str
    step_type: str = "action"  # action / decision / parallel


# ── 系统提示词（从配置文件加载，带默认值） ──
def _get_parse_prompt() -> str:
    """获取拆解 prompt（优先配置文件，降级默认）。"""
    try:
        from config.prompt_manager import get_prompt
        prompt = get_prompt("parse_system_prompt")
        if prompt:
            return prompt
    except Exception:
        pass
    # 默认 prompt
    return """你是一个任务拆解助手。用户会输入一条自然语言指令，你需要将其拆解为有序的执行步骤。
返回严格 JSON：{"task_type": "work|life|mix", "steps": [{"name": "步骤名", "description": "描述", "step_type": "action|parallel"}]}"""


# 向后兼容：模块级变量（首次访问时加载）
_PARSE_SYSTEM_PROMPT = None


def _get_parse_prompt_static() -> str:
    """获取拆解 prompt（缓存）。"""
    global _PARSE_SYSTEM_PROMPT
    if _PARSE_SYSTEM_PROMPT is None:
        _PARSE_SYSTEM_PROMPT = _get_parse_prompt()
    return _PARSE_SYSTEM_PROMPT


def parse(task_text: str) -> list[TaskStep]:
    """将用户指令拆解为步骤列表（演化感知优先级）。

    优先级：
    1. 演化模板推荐（高频固化模板 / 挖掘模式 / 冷启动默认）
    2. LLM 拆解
    3. 规则兜底

    演化反馈闭环：命中模板/模板直接执行 → 执行后 learn_from_task 强化模式 → 下次更易命中
    """
    steps, _ = parse_with_source(task_text)
    return steps


def parse_with_source(task_text: str) -> tuple[list[TaskStep], dict[str, Any]]:
    """拆解任务并返回来源信息（供前端展示）。

    Returns:
        (steps, source_info)
        source_info 包含:
        - source: "template" | "pattern" | "default" | "llm" | "rule" | "empty"
        - source_label: 中文标签（如"您的习惯模板"、"AI 智能拆解"）
        - template_name: 模板名称（命中模板时）
        - confidence: 置信度（模式命中时）

    前端可根据 source 显示不同提示：
    - template: "正在使用您的习惯模板「周报」"
    - pattern: "基于您的历史最优流程"
    - default: "已加载最佳实践模板"
    - llm: "AI 智能拆解"
    """
    if not task_text or not task_text.strip():
        return [TaskStep(0, "空任务", "用户未输入有效指令")], {"source": "empty", "source_label": "空任务"}

    # ── 优先级 1：演化引擎推荐（模板 > 模式 > 默认） ──
    recommended = _try_recommend_steps(task_text)
    if recommended:
        raw_steps, source, template_name = recommended
        steps = [
            TaskStep(
                index=i,
                name=s.get("name", f"步骤{i}"),
                description=s.get("description", ""),
                step_type=s.get("step_type", "action"),
            )
            for i, s in enumerate(raw_steps)
        ]
        logger.info("演化推荐命中 [%s]: %d 步 — %s", source, len(steps), task_text[:40])

        # 构造来源信息（含程序性记忆）
        source_info = {
            "source": source,
            "source_label": _get_source_label(source),
            "template_name": template_name,
        }

        # 如果是模板命中，附加程序性记忆（决策规则/成功经验）
        if source == "template":
            procedural = _get_procedural_memory(template_name)
            if procedural:
                source_info["procedural_memory"] = procedural

        return steps, source_info

    # ── 优先级 2：LLM 拆解 ──
    steps = _parse_with_llm(task_text)
    if steps:
        return steps, {"source": "llm", "source_label": "AI 智能拆解"}

    # ── 优先级 3：规则兜底 ──
    logger.warning("LLM 拆解失败，使用规则兜底")
    return _parse_with_rules(task_text), {"source": "rule", "source_label": "规则兜底"}


def _get_source_label(source: str) -> str:
    """获取来源的中文标签。"""
    labels = {
        "template": "您的习惯模板",
        "pattern": "历史最优流程",
        "default": "最佳实践模板",
        "llm": "AI 智能拆解",
        "rule": "规则兜底",
    }
    return labels.get(source, "未知来源")


def _get_procedural_memory(habit_key: str) -> dict | None:
    """获取模板的程序性记忆（决策规则+成功经验+常见错误）。"""
    if not habit_key:
        return None
    try:
        from evolution_core.template_save import get_template
        tpl = get_template(habit_key)
        if not tpl:
            return None

        # 只返回有数据的字段
        memory = {}
        if tpl.get("decision_rules"):
            memory["decision_rules"] = tpl["decision_rules"]
        if tpl.get("success_patterns"):
            memory["success_patterns"] = tpl["success_patterns"]
        if tpl.get("common_mistakes"):
            memory["common_mistakes"] = tpl["common_mistakes"]

        return memory if memory else None
    except Exception:
        return None


def _try_recommend_steps(task_text: str) -> tuple[list[dict], str, str] | None:
    """尝试从演化引擎获取推荐步骤。

    Returns:
        (steps, source, template_name) 命中时返回，
        source 为 "template" / "pattern" / "default"；template_name 仅模板命中时非空
        None 表示无命中，需回退到 LLM
    """
    task_type = detect_task_type(task_text).value

    # ── 1. 已固化模板（最高优先级：用户高频习惯） ──
    try:
        from evolution_core.template_save import list_templates
        templates = list_templates()
        for tpl in templates:
            name = tpl.get("name", "")
            if name and _is_valid_template_match(name, task_text):
                tpl_steps = tpl.get("steps", [])
                if tpl_steps:
                    logger.info("固化模板命中: %s", name)
                    return tpl_steps, "template", name
    except Exception as e:
        logger.debug("模板匹配失败: %s", e)

    # ── 2. 挖掘模式（中优先级：历史最优流程） ──
    try:
        from evolution_core.pattern_miner import recommend_steps
        pattern_steps = recommend_steps(task_text, task_type)
        if pattern_steps:
            # 标准化：pattern_miner 返回 list[str]，转为统一 list[dict]
            return _normalize_steps(pattern_steps), "pattern", ""
    except Exception as e:
        logger.debug("模式推荐失败: %s", e)

    # ── 3. 冷启动默认模板（低优先级：最佳实践） ──
    try:
        from evolution_core.cold_start import get_default_template
        default_steps = get_default_template(task_text)
        if default_steps:
            return _normalize_steps(default_steps), "default", ""
    except Exception as e:
        logger.debug("默认模板匹配失败: %s", e)

    return None


def _normalize_steps(raw_steps: list) -> list[dict]:
    """标准化步骤格式：将 list[str] 或 list[dict] 统一为 list[dict]。

    不同来源的步骤格式不同：
    - pattern_miner: list[str]（步骤名）
    - template_save: list[dict]（含 name/description/step_type）
    - cold_start: list[dict]（含 name/description/step_type）
    """
    normalized = []
    for s in raw_steps:
        if isinstance(s, dict):
            normalized.append(s)
        elif isinstance(s, str):
            normalized.append({
                "name": s[:20],
                "description": s,
                "step_type": "action",
            })
    return normalized


def _is_valid_template_match(template_name: str, task_text: str) -> bool:
    """校验模板是否真正匹配任务文本（避免否定句误匹配 + 部分匹配）。

    问题：
    1. 子串匹配 "周报" in "我不想写周报" 会误命中（否定句）
    2. 子串匹配 "周报" in "周报总结很重要" 会误命中（部分匹配）

    解决：
    1. 检查否定词前缀（"不想"、"别"、"不要"）
    2. 要求模板名后不是中文字符（避免"周报"匹配"周报总结"）
    """
    if template_name not in task_text:
        return False

    # 否定词列表：模板名前面出现这些词表示否定意图
    NEGATION_WORDS = ["不想", "别", "不要", "无需", "不用", "不需要", "no", "not", "don't", "never"]

    # 找到模板名在任务文本中的位置
    idx = task_text.find(template_name)
    if idx < 0:
        return False

    # ── 1. 检查否定词（前 6 个字符内） ──
    prefix = task_text[max(0, idx - 6):idx].lower()
    for neg in NEGATION_WORDS:
        if neg in prefix:
            logger.debug("模板匹配跳过（否定意图）: %s in %s", template_name, task_text[:30])
            return False

    # ── 2. 检查模板名后面的字符（仅对 2 字模板做部分匹配保护） ──
    # 注意：中文无空格分词，无法完美区分"报销材料"（两词）和"周报总结"（复合词）
    # 务实方案：只保护 2 字模板，3 字以上容忍（长词本身区分度高）
    end_idx = idx + len(template_name)
    if end_idx < len(task_text) and len(template_name) <= 2:
        next_char = task_text[end_idx]
        if '一' <= next_char <= '鿿':
            logger.debug("模板匹配跳过（2字模板部分匹配）: %s | next=%s", template_name, next_char)
            return False

    return True


def _parse_with_llm(task_text: str) -> list[TaskStep] | None:
    """用 LLM 拆解任务（记忆增强）。"""
    try:
        # 构建记忆增强上下文
        memory_context = _build_memory_context_for_parse(task_text)

        # 拼接 prompt：原始任务 + 记忆上下文
        user_message = task_text
        if memory_context:
            user_message = f"{task_text}\n\n{memory_context}"

        resp = chat_json([
            {"role": "system", "content": _get_parse_prompt_static()},
            {"role": "user", "content": user_message},
        ])
        if "steps" not in resp:
            return None

        raw_steps = resp["steps"]
        steps: list[TaskStep] = []
        for i, s in enumerate(raw_steps):
            steps.append(TaskStep(
                index=i,
                name=s.get("name", f"步骤{i}"),
                description=s.get("description", ""),
                step_type=s.get("step_type", "action"),
            ))
        logger.info("LLM 拆解为 %d 个步骤（记忆增强: %s）", len(steps),
                    "有" if memory_context else "无")
        return steps if steps else None
    except Exception as e:
        logger.error("LLM 拆解异常: %s", e)
        return None


def _build_memory_context_for_parse(task_text: str) -> str:
    """为任务拆解构建记忆上下文。"""
    try:
        from agent_core.memory_context import build_memory_context
        return build_memory_context(task_text, top_k=2)
    except Exception as e:
        logger.debug("记忆上下文构建失败: %s", e)
        return ""


# ── 关键词（规则兜底用）──
WORK_KEYWORDS = {
    "周报": "生成周报", "月报": "生成月报", "日报": "生成日报",
    "报销": "整理报销材料", "会议纪要": "梳理会议纪要",
    "Excel": "处理表格数据", "表格": "处理表格数据",
    "PDF": "处理PDF文档", "合同": "研读合同文档", "归档": "归档工作文件",
}
LIFE_KEYWORDS = {
    "记账": "记录收支", "开销": "统计开销", "预算": "制定预算",
    "日程": "安排日程", "购物": "整理购物清单", "家务": "安排家务",
}


def _parse_with_rules(task_text: str) -> list[TaskStep]:
    """规则式兜底拆解。"""
    segments = re.split(r"[，。；;\n]+", task_text.strip())
    segments = [s.strip() for s in segments if s.strip()]

    steps: list[TaskStep] = [TaskStep(0, "理解需求", "解析用户指令")]
    for i, seg in enumerate(segments, start=1):
        name = _match_keyword(seg)
        steps.append(TaskStep(i, name, seg))
    steps.append(TaskStep(len(steps), "结果汇总", "整合所有步骤结果"))
    return steps


def _match_keyword(text: str) -> str:
    for kw, action in {**WORK_KEYWORDS, **LIFE_KEYWORDS}.items():
        if kw in text:
            return action
    return f"处理: {text[:20]}"


def detect_task_type(text: str) -> TaskType:
    """判断任务类型。"""
    has_work = any(k in text for k in WORK_KEYWORDS)
    has_life = any(k in text for k in LIFE_KEYWORDS)
    if has_work and has_life:
        return TaskType.MIX
    if has_life:
        return TaskType.LIFE
    return TaskType.WORK
