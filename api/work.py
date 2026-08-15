"""职场办公模块 API：文书、Excel、报销、归档、项目。"""
import json
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse

from agent_core.llm_client import chat
from service import work_service
from tools import excel_tools, pdf_tools, text_writer
from service.file_service import classify_files, scan_desktop as _scan_desktop, batch_rename as _batch_rename, archive_file as _archive_file
from memory_store.sqlite_db import get_conn, now_str

logger = logging.getLogger(__name__)
router = APIRouter()


# ═══════════════════════════════════════════
# 3.1 文书撰写
# ═══════════════════════════════════════════

@router.post("/doc/weekly")
def weekly_report(body: dict):
    """生成周报。"""
    result = work_service.gen_weekly_report(
        work_items=body.get("work_items"),
        notes=body.get("notes", ""),
    )
    return result


@router.post("/doc/monthly")
def monthly_report(body: dict):
    """生成月报。"""
    result = work_service.gen_monthly_report(
        month=body.get("month", ""),
        highlights=body.get("highlights"),
    )
    return result


@router.post("/doc/meeting")
def meeting_minutes(body: dict):
    """生成会议纪要。"""
    raw = body.get("raw_text", "")
    if not raw.strip():
        raise HTTPException(status_code=400, detail="请输入会议记录内容")
    return work_service.gen_meeting_minutes(raw)


@router.post("/doc/polish")
def polish(body: dict):
    """公文润色。"""
    text = body.get("text", "")
    style = body.get("style", "正式")
    if not text.strip():
        raise HTTPException(status_code=400, detail="请输入需要润色的文本")
    content = work_service.polish_document(text, style)
    return {"content": content, "style": style}


@router.post("/doc/save")
def save_doc(body: dict):
    """保存文书到本地文件。"""
    title = body.get("title", "未命名")
    content = body.get("content", "")
    out_path = body.get("out_path", "")
    if not out_path:
        from config.path_config import ARCHIVE_DIR
        out_path = str(ARCHIVE_DIR / "docs" / f"{title}.md")
    path = text_writer.write_report(title, content, out_path)
    return {"ok": bool(path), "path": path}


# ═══════════════════════════════════════════
# 3.2 Excel 处理
# ═══════════════════════════════════════════

@router.post("/excel/analyze")
def analyze_excel(body: dict):
    """分析 Excel 文件。"""
    path = body.get("path", "")
    if not path:
        raise HTTPException(status_code=400, detail="请提供文件路径")
    data = excel_tools.read_excel(path)
    sheets = excel_tools.sheet_names(path)

    # 基础统计
    stats = {}
    if data and len(data) > 1:
        header = data[0]
        for col_idx, col_name in enumerate(header):
            values = [row[col_idx] for row in data[1:] if row[col_idx] is not None]
            numeric = [v for v in values if isinstance(v, (int, float))]
            if numeric:
                stats[str(col_name)] = {
                    "count": len(numeric),
                    "sum": round(sum(numeric), 2),
                    "avg": round(sum(numeric) / len(numeric), 2),
                    "max": max(numeric),
                    "min": min(numeric),
                }

    return {
        "file": path,
        "sheets": sheets,
        "rows": len(data),
        "columns": len(data[0]) if data else 0,
        "preview": data[:6],
        "stats": stats,
    }


@router.post("/excel/merge")
def merge_excel(body: dict):
    """合并多个 Excel。"""
    files = body.get("files", [])
    out_path = body.get("out_path", "")
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="至少需要 2 个文件")
    if not out_path:
        from config.path_config import ARCHIVE_DIR
        out_path = str(ARCHIVE_DIR / "merged" / f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
    result = excel_tools.merge_excel(files, out_path)
    return result


@router.post("/excel/clean")
def clean_excel(body: dict):
    """清理 Excel 空白行。"""
    path = body.get("path", "")
    if not path:
        raise HTTPException(status_code=400, detail="请提供文件路径")
    removed = excel_tools.clean_blank_rows(path)
    return {"path": path, "removed_rows": removed}


@router.post("/excel/chart")
def excel_chart(body: dict):
    """生成数据可视化分析（文字版）。"""
    path = body.get("path", "")
    sheet = body.get("sheet", "")
    data = excel_tools.read_excel(path)
    if not data:
        raise HTTPException(status_code=400, detail="无法读取文件")

    # 用 LLM 生成数据分析文字
    preview = "\n".join("\t".join(str(c) for c in row) for row in data[:10])
    prompt = f"""请分析以下 Excel 数据，给出简要的数据洞察和可视化建议：

{preview}

要求：
1. 数据概况（行数、主要字段）
2. 关键趋势或异常
3. 建议的图表类型及原因
4. 简洁的 Markdown 格式"""

    analysis = chat([
        {"role": "system", "content": "你是一位数据分析专家，擅长从表格数据中提炼洞察。"},
        {"role": "user", "content": prompt},
    ], temperature=0.5, max_tokens=1000)

    return {"analysis": analysis, "rows": len(data), "file": path}


# ═══════════════════════════════════════════
# 3.3 报销整理
# ═══════════════════════════════════════════

@router.post("/reimbursement/analyze")
def analyze_reimbursement(body: dict):
    """分析报销票据。"""
    files = body.get("files", [])
    texts = body.get("texts", [])  # OCR 提取的文本

    if not files and not texts:
        raise HTTPException(status_code=400, detail="请提供票据文件或文本")

    # 从 PDF 提取文本
    all_texts = list(texts)
    for f in files:
        if f.lower().endswith(".pdf"):
            text = pdf_tools.extract_text(f)
            if text:
                all_texts.append(text)

    if not all_texts:
        return {"items": [], "total": 0, "note": "未能提取到票据信息"}

    # LLM 提取报销明细
    combined = "\n---\n".join(all_texts[:5])  # 最多 5 张
    prompt = """请从以下票据/文本中提取报销明细：

""" + combined + """

要求：
1. 提取每张票据的：日期、类别（餐饮/交通/住宿/办公/其他）、金额、摘要
2. 计算总金额
3. 按类别汇总
4. 严格返回 JSON 格式，不要 markdown，不要其他文字

JSON 格式示例：
{"items": [{"date":"2026-08-10","category":"餐饮","amount":150,"summary":"客户招待"}], "total": 150, "by_category": {"餐饮": 150}}"""

    result_text = chat([
        {"role": "system", "content": "你是一位财务票据分析专家，擅长从票据中提取结构化信息。"},
        {"role": "user", "content": prompt},
    ], temperature=0.3, max_tokens=1500)

    # 解析 JSON
    try:
        import re
        match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
            return parsed
    except json.JSONDecodeError:
        pass

    return {"raw": result_text, "items": [], "total": 0}


@router.post("/reimbursement/report")
def reimbursement_report(body: dict):
    """生成报销汇总报告。"""
    items = body.get("items", [])
    if not items:
        raise HTTPException(status_code=400, detail="请提供报销明细")

    total = sum(item.get("amount", 0) for item in items)
    by_category = {}
    for item in items:
        cat = item.get("category", "其他")
        by_category[cat] = by_category.get(cat, 0) + item.get("amount", 0)

    prompt = f"""请根据以下报销明细，生成一份规范的报销汇总报告：

总金额：{total:.2f} 元
分类汇总：{json.dumps(by_category, ensure_ascii=False, indent=2)}
明细：{json.dumps(items, ensure_ascii=False, indent=2)}

要求：
1. 报销单格式，含标题、明细表格、合计
2. 分类清晰，金额准确
3. Markdown 格式"""

    content = chat([
        {"role": "system", "content": "你是一位专业的财务报销助手。"},
        {"role": "user", "content": prompt},
    ], temperature=0.4, max_tokens=1500)

    return {"content": content, "total": total, "by_category": by_category, "count": len(items)}


# ═══════════════════════════════════════════
# 3.4 文件归档
# ═══════════════════════════════════════════

@router.get("/archive/scan")
def scan_archive():
    """扫描归档目录。"""
    from memory_store.file_archive import scan_archive
    return scan_archive()


@router.post("/archive/classify")
def classify(body: dict):
    """归类文件。"""
    files = body.get("files", [])
    if not files:
        raise HTTPException(status_code=400, detail="未提供文件")
    return classify_files(files)


@router.post("/archive/rename")
def rename_files(body: dict):
    """批量重命名。"""
    files = body.get("files", [])
    rule = body.get("rule", "prefix")
    if not files:
        raise HTTPException(status_code=400, detail="未提供文件")
    return _batch_rename(files, rule)


@router.post("/archive/move")
def move_to_archive(body: dict):
    """归档文件到指定目录。"""
    src = body.get("src", "")
    category = body.get("category", "")
    if not src:
        raise HTTPException(status_code=400, detail="未提供源文件路径")
    dest = _archive_file(src, category)
    return {"ok": bool(dest), "dest": dest}


@router.get("/archive/desktop")
def scan_desktop():
    """扫描桌面文件。"""
    return _scan_desktop()


# ═══════════════════════════════════════════
# 3.5 项目管控
# ═══════════════════════════════════════════

@router.get("/project/list")
def list_projects():
    """列出所有项目。"""
    conn = get_conn()
    rows = conn.execute("SELECT * FROM project ORDER BY update_time DESC").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["milestones"] = json.loads(d.get("milestones", "[]"))
        except json.JSONDecodeError:
            d["milestones"] = []
        result.append(d)
    return result


@router.get("/project/{pid}")
def get_project(pid: int):
    """获取项目详情。"""
    conn = get_conn()
    row = conn.execute("SELECT * FROM project WHERE id = ?", (pid,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="项目不存在")
    d = dict(row)
    d["milestones"] = json.loads(d.get("milestones", "[]"))
    return d


@router.post("/project/create")
def create_project(body: dict):
    """创建项目。"""
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="项目名称不能为空")

    milestones = body.get("milestones", [])
    if isinstance(milestones, list):
        # 标准化里程碑
        milestones = [
            {"name": m.get("name", str(m)) if isinstance(m, dict) else str(m), "done": False}
            for m in milestones
        ]

    conn = get_conn()
    cursor = conn.execute(
        """INSERT INTO project (name, description, status, milestones, related_docs)
           VALUES (?, ?, 'active', ?, ?)""",
        (name, body.get("description", ""), json.dumps(milestones, ensure_ascii=False), body.get("related_docs", "")),
    )
    conn.commit()
    pid = cursor.lastrowid
    conn.close()
    return {"id": pid, "name": name, "milestones": milestones}


@router.put("/project/{pid}")
def update_project(pid: int, body: dict):
    """更新项目。"""
    allowed = {"name", "description", "status", "related_docs", "milestones"}
    fields = {k: v for k, v in body.items() if k in allowed}
    if not fields:
        raise HTTPException(status_code=400, detail="无有效更新字段")

    if "milestones" in fields and isinstance(fields["milestones"], list):
        fields["milestones"] = json.dumps(fields["milestones"], ensure_ascii=False)

    # 自动计算进度
    milestones = body.get("milestones", [])
    if isinstance(milestones, list) and milestones:
        done = sum(1 for m in milestones if (m.get("done") if isinstance(m, dict) else False))
        fields["progress"] = round(done / len(milestones) * 100, 1)

    fields["update_time"] = now_str()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [pid]

    conn = get_conn()
    conn.execute(f"UPDATE project SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/project/{pid}")
def delete_project(pid: int):
    """删除项目。"""
    conn = get_conn()
    conn.execute("DELETE FROM project WHERE id = ?", (pid,))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.post("/project/{pid}/milestone/toggle")
def toggle_milestone(pid: int, body: dict):
    """切换里程碑完成状态。"""
    idx = body.get("index")
    if idx is None:
        raise HTTPException(status_code=400, detail="请提供里程碑索引")

    conn = get_conn()
    row = conn.execute("SELECT milestones FROM project WHERE id = ?", (pid,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="项目不存在")

    milestones = json.loads(row["milestones"])
    if idx < 0 or idx >= len(milestones):
        conn.close()
        raise HTTPException(status_code=400, detail="里程碑索引越界")

    m = milestones[idx]
    if isinstance(m, dict):
        m["done"] = not m.get("done", False)
    else:
        milestones[idx] = {"name": str(m), "done": True}

    # 重新计算进度
    done = sum(1 for m in milestones if (m.get("done") if isinstance(m, dict) else False))
    progress = round(done / len(milestones) * 100, 1) if milestones else 0

    conn.execute(
        "UPDATE project SET milestones = ?, progress = ?, update_time = ? WHERE id = ?",
        (json.dumps(milestones, ensure_ascii=False), progress, now_str(), pid),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "milestones": milestones, "progress": progress}
