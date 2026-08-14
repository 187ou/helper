"""程序入口：托盘启动、全局初始化。"""
import os
import sys
import logging

# 解决 Windows 控制台 GBK 编码问题（LLM 返回 emoji/特殊字符）
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from PyQt6.QtWidgets import QApplication

from config.path_config import ensure_dirs, APP_LOG_PATH
from config.settings import load_config
from memory_store.sqlite_db import init_db
from gui.main_window import MainWindow
from gui.tray_icon import TrayIcon
from gui.style import GLOBAL_QSS


def setup_logging() -> None:
    """配置日志：文件 + 控制台。"""
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    try:
        from pathlib import Path
        Path(APP_LOG_PATH).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(APP_LOG_PATH, encoding="utf-8"))
    except OSError:
        pass
    logging.basicConfig(level=logging.INFO, format=log_format, handlers=handlers)


def main() -> int:
    setup_logging()
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
