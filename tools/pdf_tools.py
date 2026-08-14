"""PDF 工具（基于 pypdf，真实可用）。"""
import logging
from typing import Any

logger = logging.getLogger(__name__)


def extract_text(path: str) -> str:
    """提取 PDF 全部文本。"""
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        texts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                texts.append(text)
        result = "\n\n".join(texts)
        logger.info("提取 PDF 文本: %s (%d 页, %d 字符)", path, len(reader.pages), len(result))
        return result
    except Exception as e:
        logger.error("提取 PDF 文本失败 %s: %s", path, e)
        return ""


def extract_metadata(path: str) -> dict[str, Any]:
    """提取 PDF 元数据。"""
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        meta = reader.metadata or {}
        return {
            "pages": len(reader.pages),
            "title": meta.get("/Title", ""),
            "author": meta.get("/Author", ""),
            "subject": meta.get("/Subject", ""),
            "creator": meta.get("/Creator", ""),
        }
    except Exception as e:
        logger.error("提取 PDF 元数据失败 %s: %s", path, e)
        return {"pages": 0}


def page_text(path: str, page_num: int) -> str:
    """提取指定页文本（page_num 从 0 开始）。"""
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        if 0 <= page_num < len(reader.pages):
            return reader.pages[page_num].extract_text() or ""
        return ""
    except Exception as e:
        logger.error("提取 PDF 页失败 %s: %s", path, e)
        return ""
