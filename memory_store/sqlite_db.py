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
    create_time TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
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

CREATE TABLE IF NOT EXISTS behavior_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    event_data TEXT DEFAULT '',
    create_time TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS evolution_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT '1',
    update_time TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS health_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_type TEXT NOT NULL,
    value REAL DEFAULT 0,
    note TEXT DEFAULT '',
    record_date TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS personal_archive (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'other',
    file_path TEXT DEFAULT '',
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '',
    create_time TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS habit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    frequency TEXT DEFAULT 'daily',
    target_days INTEGER DEFAULT 30,
    create_time TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS habit_checkin (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    habit_id INTEGER NOT NULL,
    checkin_date TEXT NOT NULL,
    note TEXT DEFAULT '',
    create_time TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE(habit_id, checkin_date)
);

CREATE TABLE IF NOT EXISTS project (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    progress REAL DEFAULT 0,
    milestones TEXT DEFAULT '[]',
    related_docs TEXT DEFAULT '',
    create_time TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    update_time TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS note (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT DEFAULT '',
    category TEXT DEFAULT 'note',
    tags TEXT DEFAULT '',
    attachments TEXT DEFAULT '[]',
    linked_task_id INTEGER DEFAULT 0,
    version INTEGER DEFAULT 1,
    create_time TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    update_time TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
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
    """初始化数据库：建表 + 迁移。"""
    ensure_dirs()
    conn = get_conn()
    try:
        conn.executescript(SCHEMA)
        _migrate(conn)
        conn.commit()
        logger.info("数据库初始化完成: %s", DB_PATH)
    finally:
        conn.close()


def _migrate(conn: sqlite3.Connection) -> None:
    """平滑迁移：补齐旧表缺少的列。"""
    # task_list 新增列检测
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(task_list)").fetchall()}
    needed_cols = {
        "tags": "TEXT DEFAULT ''",
        "priority": "TEXT DEFAULT 'medium'",
        "deadline": "TEXT DEFAULT ''",
        "related_doc": "TEXT DEFAULT ''",
        "dag_json": "TEXT DEFAULT ''",
        "source": "TEXT DEFAULT 'manual'",
        "update_time": "TEXT DEFAULT ''",
    }
    for col, typ in needed_cols.items():
        if col not in existing_cols:
            try:
                conn.execute(f"ALTER TABLE task_list ADD COLUMN {col} {typ}")
                logger.info("迁移：task_list 新增列 %s", col)
            except sqlite3.OperationalError as e:
                logger.warning("迁移列 %s 失败: %s", col, e)

    # evolution_config 默认值
    defaults = {
        "enable_evolution": "1",
        "enable_behavior_track": "1",
        "enable_auto_optimize": "1",
        "enable_template_save": "1",
        "enable_tool_gen": "1",
        "evolution_threshold": "60",
    }
    for k, v in defaults.items():
        conn.execute(
            "INSERT OR IGNORE INTO evolution_config (key, value) VALUES (?, ?)",
            (k, v),
        )


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
