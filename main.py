"""程序入口：CLI 终端 + 全局快捷键唤起。"""
import os
import sys

# 解决 Windows 控制台 GBK 编码问题
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import logging
import threading
import ctypes
from core.logging import setup_logging
from config.path_config import ensure_dirs, APP_LOG_PATH
from config.settings import load_config
from memory_store.sqlite_db import init_db
from service.task_runner import start as start_scheduler


def bring_window_to_front():
    """将当前终端窗口置顶（Windows）."""
    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception:
        pass


def hotkey_listener():
    """全局快捷键监听线程."""
    try:
        import keyboard
        # Ctrl+Alt+J 唤起终端
        keyboard.add_hotkey("ctrl+alt+j", bring_window_to_front)
        logger.info("全局快捷键 Ctrl+Alt+J 已注册")
        keyboard.wait()  # 阻塞等待
    except ImportError:
        logger.warning("keyboard 库未安装，全局快捷键不可用")
    except Exception as e:
        logger.error("快捷键监听异常: %s", e)


def main() -> int:
    setup_logging(level="INFO", log_file=str(APP_LOG_PATH))
    global logger
    logger = logging.getLogger("main")
    logger.info("═══ 桌面智能助手启动 (CLI) ═══")

    # 初始化
    ensure_dirs()
    load_config()
    init_db()

    # 启动定时任务调度器
    try:
        start_scheduler(None)
    except Exception as e:
        logger.warning("定时任务启动失败: %s", e)

    # 启动全局快捷键监听（守护线程）
    hotkey_thread = threading.Thread(target=hotkey_listener, daemon=True)
    hotkey_thread.start()

    # 启动 CLI
    from cli import cli_main
    cli_main()

    logger.info("程序退出")
    return 0


if __name__ == "__main__":
    sys.exit(main())
