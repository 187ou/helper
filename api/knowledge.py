"""知识库 API。"""
import logging
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form

from memory_store.chroma_kb import (
    add_document, search, list_documents, delete_document,
    get_stats, COLLECTIONS,
)
from config.app_const import KBCategory

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/list")
def list_docs():
    return list_documents()


@router.get("/search")
def search_docs(q: str = "", top_k: int = 5):
    if not q:
        return []
    return search(q, top_k=top_k)


@router.post("/upload")
def upload(file: UploadFile = File(...), category: str = Form("work_doc")):
    # 保存上传文件到临时目录
    tmp_path = Path("user_data/tmp") / file.filename
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    content = file.file.read()
    tmp_path.write_bytes(content)

    # 提取文本并入库
    text = _extract(tmp_path)
    if not text.strip():
        return {"ok": False, "error": "empty"}

    result = add_document(str(tmp_path), text, category, file_name=file.filename)
    return {"ok": True, **result}


@router.delete("/{doc_id}")
def delete(doc_id: str, category: str = ""):
    delete_document(doc_id, category)
    return {"ok": True}


@router.get("/stats")
def stats():
    return get_stats()


def _extract(fp: Path) -> str:
    s = fp.suffix.lower()
    try:
        if s == ".pdf":
            from tools.pdf_tools import extract_text
            return extract_text(str(fp))
        elif s in (".txt", ".md", ".csv"):
            for e in ["utf-8", "gbk"]:
                try:
                    with open(fp, "r", encoding=e) as f:
                        return f.read()
                except UnicodeDecodeError:
                    continue
        elif s == ".xlsx":
            from tools.excel_tools import read_excel
            return "\n".join("\t".join(str(c) for c in r) for r in read_excel(str(fp)))
    except Exception:
        pass
    return ""
