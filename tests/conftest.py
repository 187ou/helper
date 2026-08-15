"""测试共享配置和 fixtures。"""
import os
import sys
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(scope="session")
def test_dir():
    """返回测试临时目录。"""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def mock_db(test_dir):
    """创建并返回一个临时 SQLite 数据库连接。"""
    db_path = test_dir / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # 创建测试表
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS task_list (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_type TEXT NOT NULL DEFAULT 'work',
            task_content TEXT NOT NULL,
            task_steps TEXT,
            status TEXT NOT NULL DEFAULT 'todo',
            cost_time REAL DEFAULT 0,
            work_score REAL DEFAULT 0,
            life_score REAL DEFAULT 0,
            user_modify TEXT,
            tags TEXT DEFAULT '',
            priority TEXT DEFAULT 'medium',
            deadline TEXT DEFAULT '',
            related_doc TEXT DEFAULT '',
            dag_json TEXT DEFAULT '',
            source TEXT DEFAULT 'manual',
            create_time TEXT DEFAULT (datetime('now', 'localtime')),
            update_time TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS user_habit_weight (
            habit_key TEXT PRIMARY KEY,
            weight REAL NOT NULL DEFAULT 5.0,
            freq_count INTEGER NOT NULL DEFAULT 0,
            last_use_time TEXT,
            is_valid INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS evolution_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evo_type TEXT NOT NULL,
            before_content TEXT,
            after_content TEXT,
            evo_time TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS health_record (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_type TEXT NOT NULL,
            value REAL DEFAULT 0,
            note TEXT DEFAULT '',
            record_date TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS behavior_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            event_data TEXT DEFAULT '',
            create_time TEXT DEFAULT (datetime('now', 'localtime'))
        );
    """)
    conn.commit()
    return conn
