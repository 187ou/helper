"""冷启动策略：让新用户立即感知演化引擎价值。

核心能力：
1. 默认模板库：预置常见任务的步骤模板
2. 快速学习：新用户前 N 次任务使用简化但有效的策略
3. 引导式首次体验：第一次使用时给出明确反馈
4. 渐进式激活：根据使用频率逐步解锁高级功能

设计原则：
- 新用户不应面对"空白"的演化系统
- 默认模板基于最佳实践，而非随机
- 快速学习在 3-5 次任务后就能产生个性化
"""
import logging
from datetime import datetime
from typing import Any

from evolution_core.safe_ops import safe_json_loads, sanitize_text

logger = logging.getLogger(__name__)

# ── 默认模板库（基于最佳实践） ──

DEFAULT_TEMPLATES: dict[str, dict[str, Any]] = {
    "周报": {
        "keywords": ["周报", "周总结", "weekly", "本周工作"],
        "steps": [
            {"name": "收集本周工作", "description": "整理本周完成的任务、会议、关键事件", "step_type": "action"},
            {"name": "梳理成果", "description": "提炼可量化的成果和进展", "step_type": "action"},
            {"name": "分析问题", "description": "识别本周遇到的问题和风险", "step_type": "action"},
            {"name": "规划下周", "description": "列出下周重点工作计划", "step_type": "action"},
            {"name": "汇总输出", "description": "整合为结构化周报", "step_type": "action"},
        ],
        "template_type": "workflow",
        "priority": 10,
    },
    "月报": {
        "keywords": ["月报", "月总结", "monthly", "本月工作"],
        "steps": [
            {"name": "汇总月度数据", "description": "收集本月关键数据指标", "step_type": "action"},
            {"name": "分析趋势", "description": "对比上月数据，识别趋势变化", "step_type": "action"},
            {"name": "提炼亮点", "description": "总结本月核心成果和突破", "step_type": "action"},
            {"name": "识别问题", "description": "分析未达预期的原因", "step_type": "action"},
            {"name": "制定计划", "description": "下月重点方向和行动计划", "step_type": "action"},
        ],
        "template_type": "workflow",
        "priority": 9,
    },
    "会议纪要": {
        "keywords": ["会议纪要", "会议记录", "会议总结", "meeting"],
        "steps": [
            {"name": "整理要点", "description": "提炼会议核心议题和讨论要点", "step_type": "action"},
            {"name": "记录决议", "description": "明确会议达成的共识和决议", "step_type": "action"},
            {"name": "拆分待办", "description": "列出行动项、责任人、截止时间", "step_type": "action"},
            {"name": "输出纪要", "description": "整理为规范的会议纪要文档", "step_type": "action"},
        ],
        "template_type": "workflow",
        "priority": 8,
    },
    "报销整理": {
        "keywords": ["报销", "票据", "发票", "reimbursement"],
        "steps": [
            {"name": "归集票据", "description": "整理所有相关发票和票据", "step_type": "action"},
            {"name": "分类整理", "description": "按类别（餐饮/交通/住宿等）分类", "step_type": "action"},
            {"name": "核对金额", "description": "验证每张票据的金额和日期", "step_type": "action"},
            {"name": "生成清单", "description": "输出报销明细清单", "step_type": "action"},
        ],
        "template_type": "workflow",
        "priority": 7,
    },
    "记账": {
        "keywords": ["记账", "开销", "收支", "账单", "消费"],
        "steps": [
            {"name": "记录收支", "description": "录入收入或支出金额", "step_type": "action"},
            {"name": "选择分类", "description": "选择收支类别", "step_type": "action"},
            {"name": "添加备注", "description": "补充说明信息", "step_type": "action"},
            {"name": "确认保存", "description": "核对并保存记录", "step_type": "action"},
        ],
        "template_type": "workflow",
        "priority": 6,
    },
    "文件归档": {
        "keywords": ["归档", "整理", "归类", "收纳", "分类"],
        "steps": [
            {"name": "扫描文件", "description": "识别需要归档的文件", "step_type": "action"},
            {"name": "确定分类", "description": "按类型/项目/时间等维度分类", "step_type": "action"},
            {"name": "批量处理", "description": "重命名、移动、整理", "step_type": "action"},
            {"name": "验证结果", "description": "检查归档结果是否正确", "step_type": "action"},
        ],
        "template_type": "workflow",
        "priority": 5,
    },
    "日程计划": {
        "keywords": ["日程", "计划", "排班", "出行", "schedule"],
        "steps": [
            {"name": "明确目标", "description": "确定日程的核心目标", "step_type": "action"},
            {"name": "列出事项", "description": "梳理需要安排的事项", "step_type": "action"},
            {"name": "排定优先级", "description": "按重要紧急程度排序", "step_type": "action"},
            {"name": "分配时间", "description": "为每项分配时间段", "step_type": "action"},
        ],
        "template_type": "workflow",
        "priority": 4,
    },
    "文书撰写": {
        "keywords": ["报告", "总结", "方案", "计划", "公文", "撰写"],
        "steps": [
            {"name": "明确目的", "description": "确定文书的目标读者和核心目的", "step_type": "action"},
            {"name": "收集素材", "description": "整理相关数据、案例、背景信息", "step_type": "action"},
            {"name": "构建框架", "description": "设计文书结构和章节", "step_type": "action"},
            {"name": "撰写内容", "description": "填充各章节内容", "step_type": "action"},
            {"name": "审核润色", "description": "检查逻辑、格式、用词", "step_type": "action"},
        ],
        "template_type": "workflow",
        "priority": 3,
    },
}

# ── 快速学习配置 ──

FAST_LEARN_CONFIG = {
    "fast_learn_threshold": 5,          # 少于 N 次任务时启用快速学习
    "min_evidence_for_preference": 2,   # 快速学习时降低偏好证据门槛
    "boost_factor": 1.5,                # 快速学习期提权倍率
    "default_confidence": 0.6,          # 默认模板初始置信度
}


def get_default_template(task_text: str) -> list[dict] | None:
    """获取默认模板（基于关键词匹配）。

    优先级：
    1. 精确关键词匹配
    2. 模糊匹配（包含关系）
    3. 返回 None（无匹配）
    """
    if not task_text:
        return None

    task_text = sanitize_text(task_text, max_length=200).lower()

    # 按优先级排序候选模板
    candidates = []

    for template_name, template in DEFAULT_TEMPLATES.items():
        match_score = _match_template(task_text, template)
        if match_score > 0:
            candidates.append((match_score, template))

    if not candidates:
        return None

    # 返回得分最高的模板
    candidates.sort(key=lambda x: x[0], reverse=True)
    best_template = candidates[0][1]

    logger.info("默认模板命中: %s (得分 %d)", best_template.get("template_type"), candidates[0][0])
    return best_template["steps"]


def _match_template(task_text: str, template: dict) -> int:
    """计算任务文本与模板的匹配得分。

    得分规则：
    - 关键词精确匹配：+20 分
    - 关键词包含匹配：+10 分/个
    - 反向包含：+5 分/个
    - 模板优先级：0~10 分（仅在有关键词匹配时加分）

    无关键词匹配时返回 0（优先级不单独计分）。
    """
    score = 0
    keywords = template.get("keywords", [])

    for kw in keywords:
        kw_lower = kw.lower()
        if kw_lower == task_text:
            score += 20  # 完全匹配
        elif kw_lower in task_text:
            score += 10  # 包含匹配
        elif task_text in kw_lower:
            score += 5   # 反向包含

    # 只有关键词匹配时才加优先级分
    if score > 0:
        score += template.get("priority", 0)

    return score


def is_fast_learn_phase(task_count: int) -> bool:
    """判断是否处于快速学习期。"""
    return task_count < FAST_LEARN_CONFIG["fast_learn_threshold"]


def get_fast_learn_boost() -> float:
    """获取快速学习期提权倍率。"""
    return FAST_LEARN_CONFIG["boost_factor"]


def get_task_count(task_type: str = "") -> int:
    """获取历史任务数量。"""
    from memory_store.sqlite_db import get_conn
    conn = get_conn()
    try:
        if task_type:
            count = conn.execute(
                "SELECT COUNT(*) FROM task_list WHERE task_type = ?", (task_type,)
            ).fetchone()[0]
        else:
            count = conn.execute("SELECT COUNT(*) FROM task_list").fetchone()[0]
        return count
    except Exception:
        return 0
    finally:
        conn.close()


def get_cold_start_guidance(task_text: str, task_count: int) -> dict[str, Any]:
    """获取冷启动引导信息。

    根据使用阶段给出不同的引导：
    - 首次使用（0 次）：给出默认模板 + 鼓励
    - 快速学习期（1-4 次）：给出模板 + 反馈收集
    - 正常期（5+ 次）：使用演化引擎推荐
    """
    guidance = {
        "phase": "normal",
        "use_default_template": False,
        "collect_feedback": False,
        "message": "",
    }

    if task_count == 0:
        # 首次使用
        guidance["phase"] = "first_time"
        guidance["use_default_template"] = True
        guidance["collect_feedback"] = True
        guidance["message"] = "首次使用，已为您加载最佳实践模板。完成后请反馈，帮助系统学习您的偏好。"
    elif is_fast_learn_phase(task_count):
        # 快速学习期
        guidance["phase"] = "fast_learn"
        guidance["use_default_template"] = True
        guidance["collect_feedback"] = True
        guidance["message"] = f"快速学习期（{task_count + 1}/{FAST_LEARN_CONFIG['fast_learn_threshold']}），系统正在学习您的偏好。"
    else:
        # 正常期
        guidance["phase"] = "normal"
        guidance["use_default_template"] = False
        guidance["collect_feedback"] = False
        guidance["message"] = ""

    return guidance


def get_recommended_steps(task_text: str, task_type: str = "") -> tuple[list[dict] | None, str]:
    """获取推荐步骤（冷启动感知）。

    策略：
    1. 先尝试演化引擎推荐（个性化）
    2. 无推荐时使用默认模板
    3. 返回推荐来源（用于前端展示）

    Returns:
        (steps, source) - source: "evolution" / "default" / "none"
    """
    if not task_text:
        return None, "none"

    task_count = get_task_count(task_type)

    # 快速学习期：优先使用默认模板（更可靠）
    if is_fast_learn_phase(task_count):
        default_steps = get_default_template(task_text)
        if default_steps:
            return default_steps, "default"

    # 正常期：优先使用演化引擎推荐
    try:
        from evolution_core.pattern_miner import recommend_steps
        evolution_steps = recommend_steps(task_text, task_type)
        if evolution_steps:
            return evolution_steps, "evolution"
    except Exception:
        pass

    # 兜底：默认模板
    default_steps = get_default_template(task_text)
    if default_steps:
        return default_steps, "default"

    return None, "none"


def get_all_default_templates() -> dict[str, dict]:
    """获取所有默认模板（供前端展示）。"""
    return dict(DEFAULT_TEMPLATES)


def add_default_template(name: str, keywords: list[str], steps: list[dict], priority: int = 5) -> None:
    """添加自定义默认模板。"""
    if not name or not keywords or not steps:
        return

    DEFAULT_TEMPLATES[name] = {
        "keywords": keywords,
        "steps": steps,
        "template_type": "custom",
        "priority": priority,
    }
    logger.info("添加默认模板: %s", name)
