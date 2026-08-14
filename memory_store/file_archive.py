"""本地文件归档目录扫描与管理。"""
import logging
from pathlib import Path
from typing import Any

from config.path_config import ARCHIVE_DIR

logger = logging.getLogger(__name__)


def scan_archive() -> list[dict[str, Any]]:
    """扫描归档目录，返回文件信息列表。"""
    if not ARCHIVE_DIR.exists():
        return []
    result = []
    for p in ARCHIVE_DIR.rglob("*"):
        if p.is_file():
            stat = p.stat()
            result.append(
                {
                    "name": p.name,
                    "path": str(p),
                    "size": stat.st_size,
                    "suffix": p.suffix.lower(),
                    "modified": stat.st_mtime,
                }
            )
    result.sort(key=lambda x: x["modified"], reverse=True)
    return result


def list_by_type(suffix: str) -> list[dict[str, Any]]:
    """按后缀过滤归档文件。"""
    suffix = suffix.lower() if suffix.startswith(".") else f".{suffix.lower()}"
    return [f for f in scan_archive() if f["suffix"] == suffix]


def get_file(path: str) -> Path | None:
    p = Path(path)
    if p.exists() and p.is_file():
        return p
    return None
