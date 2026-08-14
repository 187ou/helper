"""办公服务：周报、月报、文书生成（LLM 驱动，真实可用）。"""
import logging
from datetime import datetime
from typing import Any

from agent_core.llm_client import chat
from config.path_config import TEMPLATES_DIR

logger = logging.getLogger(__name__)


def gen_weekly_report(work_items: list[str] | None = None, notes: str = "") -> dict[str, Any]:
    """生成周报（LLM 生成）。"""
    items_text = "\n".join(f"- {item}" for item in (work_items or ["请补充本周工作内容"]))
    prompt = f"""请根据以下工作信息，生成一份简洁专业的周报。

## 本周工作
{notes}

## 主要成果
{items_text}

要求：
1. 包含"本周工作成果"和"下周计划"两部分
2. 语言正式简洁
3. 每项成果具体可量化
4. 输出 Markdown 格式"""

    content = chat([
        {"role": "system", "content": "你是一位专业的职场文书助手，擅长撰写规范的周报、月报。"},
        {"role": "user", "content": prompt},
    ], temperature=0.5, max_tokens=1500)

    return {"type": "weekly_report", "content": content, "generated_at": datetime.now().isoformat()}


def gen_monthly_report(month: str = "", highlights: list[str] | None = None) -> dict[str, Any]:
    """生成月报（LLM 生成）。"""
    if not month:
        month = datetime.now().strftime("%Y年%m月")
    items_text = "\n".join(f"- {h}" for h in (highlights or ["请补充本月工作亮点"]))

    prompt = f"""请生成{month}的月度工作总结报告。

## 本月亮点
{items_text}

要求：
1. 包含"工作回顾"、"数据成果"、"存在问题"、"下月计划"四部分
2. 语言正式，数据说话
3. 输出 Markdown 格式"""

    content = chat([
        {"role": "system", "content": "你是一位专业的职场文书助手，擅长撰写规范的月报和述职报告。"},
        {"role": "user", "content": prompt},
    ], temperature=0.5, max_tokens=2000)

    return {"type": "monthly_report", "month": month, "content": content}


def gen_meeting_minutes(raw_text: str) -> dict[str, Any]:
    """生成会议纪要（LLM 整理）。"""
    prompt = f"""请根据以下会议记录/草稿，整理成规范的会议纪要。

{raw_text}

要求：
1. 包含"会议主题"、"与会人员"、"会议要点"、"待办事项（含责任人和截止时间）"
2. 条理清晰，重点突出
3. 输出 Markdown 格式"""

    content = chat([
        {"role": "system", "content": "你是一位专业的会议纪要整理助手。"},
        {"role": "user", "content": prompt},
    ], temperature=0.4, max_tokens=1500)

    return {"type": "meeting_minutes", "content": content}


def polish_document(text: str, style: str = "正式") -> str:
    """公文润色。"""
    prompt = f"""请对以下文本进行润色，使其更符合{style}办公文风。

原文：
{text}

要求：语句通顺、用词准确、格式规范，保持原意。"""

    return chat([
        {"role": "system", "content": "你是一位公文润色专家，擅长优化职场文档。"},
        {"role": "user", "content": prompt},
    ], temperature=0.5, max_tokens=1500)


def process_excel(path: str) -> dict[str, Any]:
    """处理 Excel 表格。"""
    from tools.excel_tools import read_excel, sheet_names
    data = read_excel(path)
    sheets = sheet_names(path)
    return {"file": path, "sheets": sheets, "rows": len(data), "preview": data[:5]}


def archive_files(directory: str) -> dict[str, Any]:
    """归档工作文件。"""
    from service.file_service import classify_files
    from pathlib import Path
    p = Path(directory)
    if not p.exists():
        return {"directory": directory, "error": "目录不存在"}
    files = [str(f) for f in p.iterdir() if f.is_file()]
    classified = classify_files(files)
    return {"directory": directory, "total": len(files), "classified": classified}


def process_reimbursement(files: list[str]) -> dict[str, Any]:
    """整理报销材料。"""
    return {"files": files, "total_amount": 0, "status": "pending", "note": "请补充票据信息"}
