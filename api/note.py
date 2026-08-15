"""笔记管理 API（5.2）+ 文档摘要 API（5.3）。"""
import json
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException

from memory_store.sqlite_db import get_conn, now_str
from agent_core.llm_client import chat

logger = logging.getLogger(__name__)
router = APIRouter()


# ═══════════════════════════════════════════
# 5.2 笔记管理
# ═══════════════════════════════════════════

@router.get("/list")
def list_notes(category: str = "", keyword: str = "", limit: int = 50):
    """列出笔记。"""
    conn = get_conn()
    sql = "SELECT * FROM note WHERE 1=1"
    params: list = []
    if category:
        sql += " AND category = ?"
        params.append(category)
    if keyword:
        sql += " AND (title LIKE ? OR content LIKE ? OR tags LIKE ?)"
        params.extend([f"%{keyword}%"] * 3)
    sql += " ORDER BY update_time DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    result = []
    for r in rows:
        d = dict(r)
        try:
            d["attachments"] = json.loads(d.get("attachments", "[]"))
        except json.JSONDecodeError:
            d["attachments"] = []
        result.append(d)
    return result


@router.get("/{nid}")
def get_note(nid: int):
    """获取笔记详情。"""
    conn = get_conn()
    row = conn.execute("SELECT * FROM note WHERE id = ?", (nid,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="笔记不存在")
    d = dict(row)
    d["attachments"] = json.loads(d.get("attachments", "[]"))
    return d


@router.post("/create")
def create_note(body: dict):
    """创建笔记。"""
    title = (body.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="标题不能为空")

    attachments = body.get("attachments", [])
    if isinstance(attachments, list):
        attachments = json.dumps(attachments, ensure_ascii=False)

    conn = get_conn()
    cursor = conn.execute(
        """INSERT INTO note (title, content, category, tags, attachments, linked_task_id)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (title, body.get("content", ""), body.get("category", "note"),
         body.get("tags", ""), attachments, body.get("linked_task_id", 0)),
    )
    conn.commit()
    nid = cursor.lastrowid
    conn.close()
    return {"id": nid, "title": title}


@router.put("/{nid}")
def update_note(nid: int, body: dict):
    """更新笔记（带版本递增）。"""
    allowed = {"title", "content", "category", "tags", "attachments", "linked_task_id"}
    fields = {k: v for k, v in body.items() if k in allowed and v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="无有效更新字段")

    if "attachments" in fields and isinstance(fields["attachments"], list):
        fields["attachments"] = json.dumps(fields["attachments"], ensure_ascii=False)

    # 版本递增
    conn = get_conn()
    row = conn.execute("SELECT version FROM note WHERE id = ?", (nid,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="笔记不存在")
    fields["version"] = row["version"] + 1
    fields["update_time"] = now_str()

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [nid]

    conn.execute(f"UPDATE note SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()
    return {"ok": True, "version": fields["version"]}


@router.delete("/{nid}")
def delete_note(nid: int):
    """删除笔记。"""
    conn = get_conn()
    conn.execute("DELETE FROM note WHERE id = ?", (nid,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ═══════════════════════════════════════════
# 5.3 文档智能摘要
# ═══════════════════════════════════════════

@router.post("/summarize")
def summarize_doc(body: dict):
    """生成文档摘要。"""
    text = body.get("text", "")
    doc_title = body.get("title", "未命名文档")
    max_length = body.get("max_length", 500)

    if not text.strip():
        raise HTTPException(status_code=400, detail="请提供文档内容")
    if len(text) < 50:
        raise HTTPException(status_code=400, detail="文档内容过短，无需摘要")

    # 截取过长文本
    if len(text) > 8000:
        text = text[:8000]

    prompt = f"""请对以下文档进行智能摘要提炼：

文档标题：{doc_title}
文档内容：
{text}

要求：
1. 生成 {max_length} 字以内的结构化摘要
2. 包含：核心要点（3-5 条）、关键数据/结论、行动建议（如有）
3. 使用 Markdown 格式
4. 保留原文重要细节，不要空泛概括"""

    summary = chat([
        {"role": "system", "content": "你是一位专业的文档分析专家，擅长提炼长文档的核心要点。"},
        {"role": "user", "content": prompt},
    ], temperature=0.4, max_tokens=1500)

    return {
        "summary": summary,
        "original_length": len(text),
        "title": doc_title,
    }


@router.post("/summarize/save")
def summarize_and_save(body: dict):
    """生成摘要并保存为笔记。"""
    summarize_result = summarize_doc(body)

    # 保存为笔记
    attachments = json.dumps([{"type": "summary", "source": body.get("title", "")}], ensure_ascii=False)
    conn = get_conn()
    cursor = conn.execute(
        """INSERT INTO note (title, content, category, tags, attachments)
           VALUES (?, ?, 'note', '摘要', ?)""",
        (f"摘要: {summarize_result['title']}", summarize_result["summary"], attachments),
    )
    conn.commit()
    nid = cursor.lastrowid
    conn.close()

    return {"ok": True, "note_id": nid, "summary": summarize_result["summary"]}
