"""文件服务：PDF/Excel 批量处理、归类（真实可用）。"""
import logging
import shutil
from pathlib import Path
from typing import Any

from config.path_config import ARCHIVE_DIR

logger = logging.getLogger(__name__)


def scan_desktop() -> list[dict[str, Any]]:
    """扫描桌面文件。"""
    desktop = Path.home() / "Desktop"
    if not desktop.exists():
        return []
    result = []
    for p in desktop.iterdir():
        if p.is_file():
            result.append({
                "name": p.name, "path": str(p), "size": p.stat().st_size,
                "suffix": p.suffix.lower(), "modified": p.stat().st_mtime,
            })
    return result


def batch_rename(files: list[str], rule: str = "prefix") -> dict[str, Any]:
    """批量重命名（添加序号前缀）。"""
    renamed = []
    for i, f in enumerate(files, 1):
        p = Path(f)
        if not p.exists():
            continue
        new_name = f"{i:03d}_{p.name}"
        new_path = p.parent / new_name
        p.rename(new_path)
        renamed.append(str(new_path))
    logger.info("批量重命名: %d 个文件", len(renamed))
    return {"renamed": len(renamed), "rule": rule}


def classify_files(files: list[str]) -> dict[str, list[str]]:
    """按类型归类文件。"""
    result: dict[str, list[str]] = {
        "doc": [], "excel": [], "pdf": [], "image": [], "archive": [], "other": []
    }
    ext_map = {
        ".doc": "doc", ".docx": "doc", ".txt": "doc",
        ".xls": "excel", ".xlsx": "excel", ".csv": "excel",
        ".pdf": "pdf",
        ".png": "image", ".jpg": "image", ".jpeg": "image", ".gif": "image",
        ".zip": "archive", ".rar": "archive", ".7z": "archive",
    }
    for f in files:
        suffix = Path(f).suffix.lower()
        category = ext_map.get(suffix, "other")
        result[category].append(f)
    return result


def archive_file(src: str, category: str = "") -> str:
    """归档文件到指定分类目录。"""
    p = Path(src)
    if not p.exists():
        return ""
    if not category:
        category = classify_files([src]).get("other", ["other"])[0] if classify_files([src]) else "other"
    dest_dir = ARCHIVE_DIR / category
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / p.name
    shutil.copy2(src, dest)
    logger.info("归档: %s → %s", p.name, dest)
    return str(dest)
