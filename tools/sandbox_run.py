"""安全沙箱运行脚本（骨架）。"""
import logging

logger = logging.getLogger(__name__)


def run_script(code: str, timeout: int = 30) -> str:
    """在沙箱中运行 Python 代码。骨架仅打印日志。"""
    logger.info("沙箱执行 %d 字符代码，超时 %ds", len(code), timeout)
    return "TODO: 沙箱执行结果"


def check_safety(code: str) -> tuple[bool, str]:
    """代码安全检查。骨架始终通过。"""
    dangerous = ["os.system", "subprocess", "eval(", "exec(", "__import__"]
    for d in dangerous:
        if d in code:
            return False, f"检测到危险调用: {d}"
    return True, "安全检查通过"
