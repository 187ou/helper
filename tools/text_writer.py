"""文本/文书写入工具（真实可用）。"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def write_report(title: str, content: str, out_path: str) -> str:
    """写入 Markdown 格式报告。"""
    try:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"# {title}\n\n{content}")
        logger.info("写入报告: %s → %s", title, out_path)
        return out_path
    except Exception as e:
        logger.error("写入报告失败: %s", e)
        return ""


def write_text(content: str, out_path: str) -> str:
    """写入纯文本。"""
    try:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info("写入文本: %s (%d 字符)", out_path, len(content))
        return out_path
    except Exception as e:
        logger.error("写入文本失败: %s", e)
        return ""


def append_text(content: str, out_path: str) -> str:
    """追加文本到文件。"""
    try:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "a", encoding="utf-8") as f:
            f.write(content)
        return out_path
    except Exception as e:
        logger.error("追加文本失败: %s", e)
        return ""
