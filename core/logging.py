"""日志配置：自动注入 task_id。"""
import logging
import sys
from pathlib import Path
from core.context import get_task_id


class TaskIdFilter(logging.Filter):
    """为每条日志注入 task_id 字段。"""
    def filter(self, record: logging.LogRecord) -> bool:
        record.task_id = get_task_id() or "-"
        return True


def setup_logging(level: str = "INFO", log_file: str = "") -> None:
    """配置全局日志。"""
    fmt = "%(asctime)s [%(levelname)s] %(task_id)s | %(name)s: %(message)s"
    datefmt = "%H:%M:%S"

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=fmt,
        datefmt=datefmt,
        handlers=handlers,
    )

    # 注入 task_id filter
    task_filter = TaskIdFilter()
    for handler in logging.root.handlers:
        handler.addFilter(task_filter)
    logging.root.addFilter(task_filter)
