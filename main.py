"""程序入口：托盘启动、全局初始化。"""
import os
import sys

# 解决 Windows 控制台 GBK 编码问题
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from PyQt6.QtWidgets import QApplication

import logging
from core.logging import setup_logging
from config.path_config import ensure_dirs, APP_LOG_PATH
from config.settings import load_config
from memory_store.sqlite_db import init_db
from gui.main_window import MainWindow
from gui.tray_icon import TrayIcon
from gui.style import GLOBAL_QSS


def main() -> int:
    setup_logging(level="INFO", log_file=str(APP_LOG_PATH))
    logger = logging.getLogger("main")
    logger.info("═══ 桌面智能助手启动 ═══")

    # 初始化
    ensure_dirs()
    load_config()
    init_db()

    # Qt 应用
    app = QApplication(sys.argv)
    app.setApplicationName("桌面智能助手")
    app.setStyleSheet(GLOBAL_QSS)
    # 关闭最后一个窗口不退出（托盘常驻）
    app.setQuitOnLastWindowClosed(False)

    # 主窗口
    window = MainWindow()

    # 托盘图标
    tray = TrayIcon(window)
    tray.show()

    # 启动定时任务调度器
    from service.task_runner import start as start_scheduler
    start_scheduler(window)

    # 显示主窗口
    window.show()
    logger.info("主窗口已显示，托盘已就绪，定时任务已启动")

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
