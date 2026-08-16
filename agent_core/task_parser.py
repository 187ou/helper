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


# ── 系统提示词 ──
_PARSE_SYSTEM_PROMPT = """你是一个任务拆解助手。用户会输入一条自然语言指令（可能混合工作和生活任务），你需要将其拆解为有序的执行步骤。

规则：
1. 将复杂任务拆分为 2-6 个具体可执行的步骤
2. 步骤之间尽量并行（无依赖的标为 parallel），有依赖的标为 action
3. 步骤名要简短（5-10 字），描述要具体
4. 首个步骤通常是"理解需求/收集信息"，最后一个是"汇总输出"
5. 返回严格 JSON 格式，不要 markdown

输出 JSON 格式：
{
  "task_type": "work | life | mix",
  "steps": [
    {"name": "步骤名", "description": "具体描述", "step_type": "action|parallel"}
  ]
}"""


def parse(task_text: str) -> list[TaskStep]:
    """将用户指令拆解为步骤列表（演化感知优先级）。

    优先级：
    1. 演化模板推荐（高频固化模板 / 挖掘模式 / 冷启动默认）
    2. LLM 拆解
    3. 规则兜底

    演化反馈闭环：命中模板/模板直接执行 → 执行后 learn_from_task 强化模式 → 下次更易命中
    """
    if not task_text or not task_text.strip():
        return [TaskStep(0, "空任务", "用户未输入有效指令")]

    # ── 优先级 1：演化引擎推荐（模板 > 模式 > 默认） ──
    recommended = _try_recommend_steps(task_text)
    if recommended:
        raw_steps, source = recommended
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
        return steps

    # ── 优先级 2：LLM 拆解 ──
    steps = _parse_with_llm(task_text)
    if steps:
        return steps

    # ── 优先级 3：规则兜底 ──
    logger.warning("LLM 拆解失败，使用规则兜底")
    return _parse_with_rules(task_text)


def _try_recommend_steps(task_text: str) -> tuple[list[dict], str] | None:
    """尝试从演化引擎获取推荐步骤。

    Returns:
        (steps, source) 命中时返回，source 为 "template" / "pattern" / "default"
        None 表示无命中，需回退到 LLM
    """
    task_type = detect_task_type(task_text).value

    # ── 1. 已固化模板（最高优先级：用户高频习惯） ──
    try:
        from evolution_core.template_save import list_templates
        templates = list_templates()
        for tpl in templates:
            name = tpl.get("name", "")
            if name and name in task_text:
                tpl_steps = tpl.get("steps", [])
                if tpl_steps:
                    logger.info("固化模板命中: %s", name)
                    return tpl_steps, "template"
    except Exception as e:
        logger.debug("模板匹配失败: %s", e)

    # ── 2. 挖掘模式（中优先级：历史最优流程） ──
    try:
        from evolution_core.pattern_miner import recommend_steps
        pattern_steps = recommend_steps(task_text, task_type)
        if pattern_steps:
            return pattern_steps, "pattern"
    except Exception as e:
        logger.debug("模式推荐失败: %s", e)

    # ── 3. 冷启动默认模板（低优先级：最佳实践） ──
    try:
        from evolution_core.cold_start import get_default_template
        default_steps = get_default_template(task_text)
        if default_steps:
            return default_steps, "default"
    except Exception as e:
        logger.debug("默认模板匹配失败: %s", e)

    return None


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
            {"role": "system", "content": _PARSE_SYSTEM_PROMPT},
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
