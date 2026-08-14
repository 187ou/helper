"""SQLite 结构化数据库初始化与连接。"""
import logging
import sqlite3
from datetime import datetime

from config.path_config import DB_PATH, ensure_dirs

logger = logging.getLogger(__name__)

# ── 建表 DDL ──
SCHEMA = """
CREATE TABLE IF NOT EXISTS task_list (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT NOT NULL DEFAULT 'work',
    task_content TEXT NOT NULL,
    task_steps TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    cost_time REAL DEFAULT 0,
    work_score REAL DEFAULT 0,
    life_score REAL DEFAULT 0,
    user_modify TEXT,
    create_time TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
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
    evo_time TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS custom_template (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    task_flow_json TEXT,
    create_time TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS daily_schedule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    schedule_date TEXT,
    schedule_time TEXT,
    category TEXT NOT NULL DEFAULT 'work',
    priority INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    note TEXT,
    create_time TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS bill_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_type TEXT NOT NULL DEFAULT 'expense',
    amount REAL NOT NULL DEFAULT 0,
    category TEXT,
    description TEXT,
    bill_date TEXT,
    create_time TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS kb_file_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_type TEXT,
    category TEXT,
    file_size INTEGER DEFAULT 0,
    chunk_count INTEGER DEFAULT 0,
    upload_time TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    is_indexed INTEGER NOT NULL DEFAULT 0
);
"""


def get_conn() -> sqlite3.Connection:
    """获取数据库连接（自动建表）。"""
    ensure_dirs()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """初始化数据库：建表。"""
    ensure_dirs()
    conn = get_conn()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        logger.info("数据库初始化完成: %s", DB_PATH)
    finally:
        conn.close()


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
