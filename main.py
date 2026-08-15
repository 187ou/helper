"""程序入口：FastAPI 后端服务 + 定时任务。"""
import os
import sys
import logging
import threading

# 解决 Windows 控制台 GBK 编码问题
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from core.logging import setup_logging
from config.path_config import ensure_dirs, APP_LOG_PATH
from config.settings import load_config
from memory_store.sqlite_db import init_db
from service.task_runner import start as start_scheduler


def main() -> int:
    setup_logging(level="INFO", log_file=str(APP_LOG_PATH))
    logger = logging.getLogger("main")
    logger.info("═══ 桌面智能助手启动 (API Server) ═══")

    # 初始化
    ensure_dirs()
    load_config()
    init_db()

    # 启动定时任务调度器
    try:
        start_scheduler(None)
    except Exception as e:
        logger.warning("定时任务启动失败: %s", e)

    # 启动 FastAPI
    import uvicorn
    from api.app import app

    logger.info("API 服务启动: http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")

    return 0


if __name__ == "__main__":
    sys.exit(main())
