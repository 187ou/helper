"""办公服务：周报、月报、文书生成、报销分析（LLM 驱动，真实可用）。"""
import json
import logging
import re
from datetime import datetime
from typing import Any

from agent_core.llm_client import chat
from config.path_config import TEMPLATES_DIR

logger = logging.getLogger(__name__)


def gen_weekly_report(work_items: list[str] | None = None, notes: str = "") -> dict[str, Any]:
    """生成周报（记忆增强：注入用户偏好）。"""
    items_text = "\n".join(f"- {item}" for item in (work_items or ["请补充本周工作内容"]))

    # 注入用户偏好上下文
    memory_ctx = _get_document_memory_context("周报")

    prompt = f"""请根据以下工作信息，生成一份简洁专业的周报。

## 本周工作
{notes}

## 主要成果
{items_text}
{memory_ctx}

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


def _get_document_memory_context(task_hint: str) -> str:
    """获取文书生成的记忆上下文（用户偏好 + 历史参考）。"""
    try:
        from agent_core.memory_context import build_memory_context
        ctx = build_memory_context(task_hint, top_k=2)
        if ctx:
            return f"\n## 参考信息（根据您的历史和偏好）\n{ctx}"
        return ""
    except Exception as e:
        logger.debug("文书记忆上下文获取失败: %s", e)
        return ""


def process_reimbursement(files: list[str], texts: list[str] | None = None) -> dict[str, Any]:
    """整理报销材料（LLM 提取 + 分类汇总，真实可用）。

    Args:
        files: PDF/图片 文件路径列表
        texts: 预提取的 OCR 文本列表（可选）
    """
    from tools.pdf_tools import extract_text

    # 1. 提取所有票据文本
    all_texts: list[str] = list(texts or [])
    for f in files:
        if f.lower().endswith(".pdf"):
            text = extract_text(f)
            if text.strip():
                all_texts.append(text)

    if not all_texts:
        return {"files": files, "items": [], "total": 0, "status": "empty", "note": "未能提取到票据信息"}

    # 2. LLM 提取结构化报销明细
    combined = "\n---\n".join(all_texts[:8])  # 最多处理 8 张票据
    prompt = f"""请从以下票据/文本中提取报销明细：

{combined}

要求：
1. 提取每张票据的：日期（无则填"未知"）、类别（餐饮/交通/住宿/办公/通讯/其他）、金额（数字）、摘要（10字以内）
2. 计算总金额
3. 按类别汇总金额
4. 严格返回 JSON 格式，不要 markdown，不要其他文字

JSON 格式：
{{"items": [{{"date":"2026-08-10","category":"餐饮","amount":150.0,"summary":"客户招待"}}], "total": 150.0, "by_category": {{"餐饮": 150.0}}}}"""

    result_text = chat([
        {"role": "system", "content": "你是一位财务票据分析专家，擅长从票据中提取结构化信息。"},
        {"role": "user", "content": prompt},
    ], temperature=0.3, max_tokens=1500)

    # 3. 解析 JSON 结果
    try:
        match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
            # 标准化金额（确保是数字）
            for item in parsed.get("items", []):
                if isinstance(item.get("amount"), str):
                    amount_match = re.search(r'[\d.]+', item["amount"])
                    item["amount"] = float(amount_match.group()) if amount_match else 0.0
                item["amount"] = round(float(item.get("amount", 0)), 2)
            # 重新计算总金额（避免 LLM 计算错误）
            parsed["total"] = round(sum(item["amount"] for item in parsed.get("items", [])), 2)
            parsed["status"] = "ok"
            parsed["file_count"] = len(files)
            parsed["text_count"] = len(all_texts)
            logger.info("报销分析完成: %d 项, 总金额 %.2f", len(parsed.get("items", [])), parsed["total"])
            return parsed
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("报销分析 JSON 解析失败: %s", e)

    # 解析失败时返回原始文本
    return {
        "files": files,
        "items": [],
        "total": 0,
        "status": "parse_error",
        "raw_text": result_text[:500],
        "note": "LLM 输出解析失败，请检查原始文本",
    }
