"""安全沙箱、自定义工具生成（骨架：返回假工具描述）。"""
import logging
from typing import Any

logger = logging.getLogger(__name__)


def generate_tool(desc: str) -> dict[str, Any]:
    """根据需求描述生成工具。骨架返回假数据。"""
    tool = {
        "name": f"tool_{hash(desc) % 10000}",
        "description": desc,
        "code": f"# 自动生成的工具骨架\ndef run(*args, **kwargs):\n    return 'TODO: {desc}'\n",
        "status": "generated",
    }
    logger.info("生成工具: %s", tool["name"])
    return tool


def validate_tool(code: str) -> tuple[bool, str]:
    """沙箱安全校验。骨架始终返回通过。"""
    return True, "校验通过（骨架）"
