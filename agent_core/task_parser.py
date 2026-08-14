"""自然语言任务拆解（LLM 驱动 + 规则兜底）。"""
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
    """将用户指令拆解为步骤列表（LLM 优先，失败则规则兜底）。"""
    if not task_text or not task_text.strip():
        return [TaskStep(0, "空任务", "用户未输入有效指令")]

    # 尝试 LLM 拆解
    steps = _parse_with_llm(task_text)
    if steps:
        return steps

    # 兜底：规则拆解
    logger.warning("LLM 拆解失败，使用规则兜底")
    return _parse_with_rules(task_text)


def _parse_with_llm(task_text: str) -> list[TaskStep] | None:
    """用 LLM 拆解任务。"""
    try:
        resp = chat_json([
            {"role": "system", "content": _PARSE_SYSTEM_PROMPT},
            {"role": "user", "content": task_text},
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
        logger.info("LLM 拆解为 %d 个步骤", len(steps))
        return steps if steps else None
    except Exception as e:
        logger.error("LLM 拆解异常: %s", e)
        return None


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
