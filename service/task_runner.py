"""定时任务调度器：周期性执行健康提醒、归档、遗忘周期等。"""
import logging
import threading
import time

import schedule

from service.schedule_service import check_reminders, ack_reminder, daily_archive

logger = logging.getLogger(__name__)

# ── 遗忘周期配置 ──
FORGETTING_INTERVAL_HOURS = 24  # 每 24 小时执行一次遗忘周期

_thread = None
_running = False
_main_window = None


def start(main_window=None) -> None:
    """启动定时任务调度。"""
    global _running, _thread, _main_window
    if _running:
        return
    _main_window = main_window
    _running = True

    # 健康提醒：每 30 分钟检查一次（实际触发间隔由 reminders.json 控制）
    schedule.every(30).minutes.do(_check_health_reminders)

    # 每日早 8:00 推送今日清单
    schedule.every().day.at("08:00").do(_morning_push)

    # 每日晚 18:00 归档
    schedule.every().day.at("18:00").do(_evening_archive)

    # 每日凌晨 02:00 执行遗忘周期（清理过期权重/偏好/模式）
    schedule.every().day.at("02:00").do(_forgetting_cycle)

    _thread = threading.Thread(target=_run_loop, daemon=True)
    _thread.start()
    logger.info("定时任务调度器启动")


def stop() -> None:
    """停止调度器。"""
    global _running
    _running = False
    schedule.clear()
    logger.info("定时任务调度器停止")


def _run_loop() -> None:
    while _running:
        schedule.run_pending()
        time.sleep(30)


def _check_health_reminders() -> None:
    """检查并触发健康提醒。"""
    due = check_reminders()
    for r in due:
        logger.info("触发提醒: %s", r["name"])
        # CLI 模式下仅记录日志，弹窗由 GUI 实现
        ack_reminder(r["name"])


def _morning_push() -> None:
    """早 8 点推送今日清单。"""
    from service.schedule_service import get_today_schedule
    items = get_today_schedule()
    if items:
        todo_list = "\n".join(f"• {i['title']}" for i in items[:5])
        logger.info("早间推送:\n%s", todo_list)


def _evening_archive() -> None:
    """晚 6 点归档。"""
    result = daily_archive()
    logger.info("每日归档: %s", result)


def _forgetting_cycle() -> None:
    """遗忘周期：清理过期数据，防止演化引擎越来越"脏"。"""
    try:
        from evolution_core.forgetting import run_forgetting_cycle
        result = run_forgetting_cycle()
        logger.info("遗忘周期完成: %s", result)
    except Exception as e:
        logger.error("遗忘周期执行失败: %s", e)
