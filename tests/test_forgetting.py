"""遗忘机制单元测试。

测试策略：每个测试用例使用独立的临时数据库文件，
通过 patch DB_PATH 实现隔离。
"""
import pytest
import os
import sqlite3
from datetime import datetime, timedelta
from unittest.mock import patch

from memory_store.sqlite_db import init_db


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    """每个测试用例使用独立临时数据库。"""
    db_path = tmp_path / "test.db"

    # Patch 所有引用了 DB_PATH 的模块
    monkeypatch.setattr("config.path_config.DB_PATH", db_path)
    monkeypatch.setattr("memory_store.sqlite_db.DB_PATH", db_path)
    monkeypatch.setattr("memory_store.repositories.base.DB_PATH", db_path)

    # 重置模块级缓存
    import memory_store.user_weight as uw
    from memory_store.repositories.habit_repo import HabitRepository
    uw._repo = HabitRepository()

    init_db()
    yield


def _insert_preference(pref_key, value, confidence, update_time):
    """直接插入偏好。"""
    from memory_store.sqlite_db import get_conn
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO user_preference (pref_key, pref_value, confidence, evidence_count, update_time) VALUES (?, ?, ?, ?, ?)",
        (pref_key, value, confidence, 1, update_time)
    )
    conn.commit()


def _insert_habit(habit_key, weight, last_use_time):
    """直接插入习惯。"""
    from memory_store.sqlite_db import get_conn
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO user_habit_weight (habit_key, weight, freq_count, last_use_time, is_valid) VALUES (?, ?, ?, ?, ?)",
        (habit_key, weight, 1, last_use_time, 1)
    )
    conn.commit()


def _insert_feedback(feedback_type, content, create_time):
    """直接插入反馈。"""
    from memory_store.sqlite_db import get_conn
    conn = get_conn()
    conn.execute(
        "INSERT INTO user_feedback (feedback_type, original_content, create_time) VALUES (?, ?, ?)",
        (feedback_type, content, create_time)
    )
    conn.commit()


def _insert_task(content, status, score, create_time):
    """直接插入任务。"""
    from memory_store.sqlite_db import get_conn
    conn = get_conn()
    conn.execute(
        "INSERT INTO task_list (task_content, status, work_score, create_time) VALUES (?, ?, ?, ?)",
        (content, status, score, create_time)
    )
    conn.commit()


from evolution_core.forgetting import (
    decay_preferences,
    enhanced_weight_decay,
    cleanup_expired_data,
    get_windowed_stats,
    get_active_preferences,
    FORGET_CONFIG,
)


class TestDecayPreferences:
    """测试偏好过期衰减。"""

    def test_no_preferences(self):
        """无偏好时返回零结果。"""
        result = decay_preferences()
        assert result["decayed"] == 0
        assert result["expired"] == 0

    def test_recent_preference_unchanged(self):
        """近期偏好不应衰减。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _insert_preference("test:recent", '"test"', 0.8, now)

        result = decay_preferences()
        assert result["decayed"] == 0
        assert result["expired"] == 0

    def test_old_preference_decays(self):
        """过期偏好应衰减或清除（指数衰减后 <0.05 会被清除）。"""
        old_date = (datetime.now() - timedelta(days=FORGET_CONFIG["preference_expire_days"] + 30)).strftime("%Y-%m-%d %H:%M:%S")
        _insert_preference("test:old", '"test"', 0.8, old_date)

        result = decay_preferences()
        # 衰减或清除都算有效处理
        assert result["decayed"] + result["expired"] >= 1


class TestEnhancedWeightDecay:
    """测试增强版权重衰减。"""

    def test_no_habits(self):
        """无习惯时返回零结果。"""
        result = enhanced_weight_decay()
        assert result["decayed"] == 0
        assert result["expired"] == 0

    def test_recent_habit_unchanged(self):
        """近期使用的习惯不应衰减。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _insert_habit("周报", 8.0, now)

        result = enhanced_weight_decay()
        assert result["decayed"] == 0

    def test_old_habit_decays(self):
        """长期未使用的习惯应衰减。"""
        old_date = (datetime.now() - timedelta(days=FORGET_CONFIG["weight_decay_days"] + 60)).strftime("%Y-%m-%d %H:%M:%S")
        _insert_habit("旧习惯", 5.0, old_date)

        result = enhanced_weight_decay()
        assert result["decayed"] >= 1


class TestCleanupExpiredData:
    """测试数据清理。"""

    def test_no_data(self):
        """无数据时不报错。"""
        result = cleanup_expired_data()
        assert isinstance(result, dict)

    def test_cleanup_old_feedback(self):
        """过期反馈应被清理。"""
        old_date = (datetime.now() - timedelta(days=FORGET_CONFIG["feedback_retention_days"] + 10)).strftime("%Y-%m-%d %H:%M:%S")
        _insert_feedback("modify", "old feedback", old_date)

        result = cleanup_expired_data()
        assert result.get("feedback_cleaned", 0) >= 1


class TestWindowedStats:
    """测试时间窗口统计。"""

    def test_no_data(self):
        """无数据时返回零值。"""
        stats = get_windowed_stats(days=30)
        assert stats["task_total"] == 0
        assert stats["success_rate"] == 0

    def test_window_filtering(self):
        """窗口应过滤过期数据。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        old_date = (datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d %H:%M:%S")

        _insert_task("recent task", "success", 80, now)
        _insert_task("old task", "success", 50, old_date)

        stats = get_windowed_stats(days=90)
        assert stats["task_total"] == 1


class TestGetActivePreferences:
    """测试活跃偏好获取。"""

    def test_empty(self):
        """无偏好时返回空列表。"""
        prefs = get_active_preferences()
        assert prefs == []

    def test_filters_by_confidence(self):
        """低置信度偏好应被过滤。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _insert_preference("low:conf", '"test"', 0.1, now)

        prefs = get_active_preferences(min_confidence=0.3)
        assert len(prefs) == 0
