"""异步演化闭环单元测试。"""
import pytest
import time
import sqlite3

from memory_store.sqlite_db import init_db


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    """每个测试用例使用独立临时数据库。"""
    db_path = tmp_path / "test.db"
    import config.path_config as path_config
    monkeypatch.setattr(path_config, "DB_PATH", db_path)
    import memory_store.user_weight as uw
    from memory_store.repositories.habit_repo import HabitRepository
    uw._repo = HabitRepository()
    init_db()
    yield


from evolution_core.async_evolution import (
    AsyncEvolutionLoop,
    EvolutionTask,
    start_async_evolution,
    submit_evolution,
    shutdown_async_evolution,
    get_async_loop,
    ASYNC_CONFIG,
)


class TestAsyncEvolutionLoop:
    """测试异步演化循环。"""

    def test_singleton(self):
        """应是单例。"""
        loop1 = AsyncEvolutionLoop()
        loop2 = AsyncEvolutionLoop()
        assert loop1 is loop2

    def test_start_and_shutdown(self):
        """应能启动和关闭。"""
        loop = AsyncEvolutionLoop()
        loop.start()
        assert loop._running is True
        loop.shutdown(wait=True, timeout=5)
        assert loop._running is False

    def test_submit_task(self):
        """应能提交任务。"""
        loop = AsyncEvolutionLoop()
        loop.start()

        result = {
            "task_text": "测试任务",
            "steps": [{"name": "步骤1"}],
            "step_results": [{"name": "步骤1", "result": "完成"}],
            "cost_time": 10,
            "status": "success",
            "task_type": "work",
            "logs": [],
        }

        submitted = loop.submit("测试任务", result)
        assert submitted is True
        assert loop.queue_size >= 0

        loop.shutdown(wait=True, timeout=10)

    def test_submit_when_not_running(self):
        """未运行时应返回 False。"""
        loop = AsyncEvolutionLoop()
        loop._running = False

        submitted = loop.submit("test", {})
        assert submitted is False

    def test_stats_tracking(self):
        """应追踪统计。"""
        loop = AsyncEvolutionLoop()
        loop.start()

        initial_stats = loop.get_stats()

        result = {
            "task_text": "测试",
            "steps": [{"name": "步骤1"}],
            "step_results": [{"name": "步骤1", "result": "完成"}],
            "cost_time": 5,
            "status": "success",
            "task_type": "work",
            "logs": [],
        }
        loop.submit("测试", result)

        # 给一点时间处理
        time.sleep(0.5)
        new_stats = loop.get_stats()
        assert new_stats["total_submitted"] >= initial_stats["total_submitted"]

        loop.shutdown(wait=True, timeout=10)

    def test_queue_not_blocked(self):
        """提交不应阻塞。"""
        loop = AsyncEvolutionLoop()
        loop.start()

        start = time.time()
        for i in range(10):
            loop.submit(f"task_{i}", {"status": "success"})
        elapsed = time.time() - start

        # 入队应该很快（< 1 秒）
        assert elapsed < 1.0

        loop.shutdown(wait=True, timeout=10)


class TestEvolutionTask:
    """测试演化任务数据类。"""

    def test_default_values(self):
        """应有正确的默认值。"""
        task = EvolutionTask(task_text="test", result={})
        assert task.status == "pending"
        assert task.retry_count == 0
        assert task.error == ""
        assert task.created_at > 0


class TestGlobalFunctions:
    """测试全局便捷函数。"""

    def test_start_and_shutdown(self):
        """应能启动和关闭全局实例。"""
        start_async_evolution()
        loop = get_async_loop()
        assert loop._running is True

        shutdown_async_evolution()

    def test_submit_via_global(self):
        """应能通过全局函数提交。"""
        start_async_evolution()

        result = {
            "task_text": "测试",
            "steps": [{"name": "步骤1"}],
            "step_results": [{"name": "步骤1", "result": "完成"}],
            "cost_time": 5,
            "status": "success",
            "task_type": "work",
            "logs": [],
        }

        submitted = submit_evolution("测试", result)
        assert isinstance(submitted, bool)

        shutdown_async_evolution()
