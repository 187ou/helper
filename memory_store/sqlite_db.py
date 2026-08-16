"""SQLite 结构化数据库初始化与连接。"""
import logging
import sqlite3
from datetime import datetime

from config.path_config import DB_PATH, ensure_dirs

logger = logging.getLogger(__name__)

# ── A/B 测试表 DDL ──
_AB_TEST_SCHEMA = """
CREATE TABLE IF NOT EXISTS ab_experiment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    variants TEXT NOT NULL,
    metric TEXT DEFAULT 'score',
    split_ratio REAL DEFAULT 0.5,
    status TEXT DEFAULT 'running',
    winner TEXT DEFAULT '',
    create_time TEXT DEFAULT (datetime('now', 'localtime')),
    end_time TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS ab_result (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id TEXT NOT NULL,
    variant_name TEXT NOT NULL,
    metric_value REAL DEFAULT 0,
    task_id INTEGER DEFAULT 0,
    create_time TEXT DEFAULT (datetime('now', 'localtime'))
);
"""

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
    task_goal TEXT DEFAULT '',                      # 任务目标（工作记忆）
    key_decisions TEXT DEFAULT '[]',                # 关键决策 JSON
    related_preferences TEXT DEFAULT '[]',          # 涉及偏好 JSON
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

# ── 演化引擎深化：模式挖掘 ──
CREATE TABLE IF NOT EXISTS task_pattern (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_key TEXT NOT NULL UNIQUE,          # 模式标识（如 "周报+月报"）
    pattern_type TEXT NOT NULL,                  # 类型: workflow / sequence / combo
    task_keywords TEXT NOT NULL,                 # 关联的关键词 JSON
    step_template TEXT NOT NULL,                 # 步骤模板 JSON
    usage_count INTEGER NOT NULL DEFAULT 1,      # 使用次数
    avg_score REAL DEFAULT 0,                    # 平均得分
    success_count INTEGER DEFAULT 0,             # 成功次数
    total_duration REAL DEFAULT 0,               # 总耗时（秒）
    avg_duration REAL DEFAULT 0,                 # 平均耗时
    confidence REAL DEFAULT 0,                   # 置信度 0-1
    source_task_ids TEXT DEFAULT '[]',           # 来源任务 ID JSON
    create_time TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    last_use_time TEXT DEFAULT ''
);

# ── 演化引擎深化：用户反馈学习 ──
CREATE TABLE IF NOT EXISTS user_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER DEFAULT 0,                   # 关联任务
    feedback_type TEXT NOT NULL,                 # 类型: modify / reject / retry / praise
    original_content TEXT,                       # 原始内容
    modified_content TEXT,                       # 修改后内容
    diff_summary TEXT,                           # 差异摘要
    task_type TEXT DEFAULT '',                   # 任务类型
    context TEXT DEFAULT '',                     # 上下文 JSON
    processed INTEGER NOT NULL DEFAULT 0,        # 是否已被演化闭环处理
    create_time TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

# ── 记忆巩固记录 ──
CREATE TABLE IF NOT EXISTS consolidation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    consolidation_type TEXT NOT NULL,            # 类型: pattern_extract / preference_strengthen / insight_generate / cleanup
    source_count INTEGER DEFAULT 0,              # 处理了多少条源记忆
    result_summary TEXT NOT NULL,                # 巩固结果摘要
    result_detail TEXT DEFAULT '',               # 详细结果 JSON
    period_start TEXT,                           # 周期开始
    period_end TEXT,                             # 周期结束
    create_time TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

# ── 元记忆：记忆系统自身的状态监控 ──
CREATE TABLE IF NOT EXISTS metamemory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_type TEXT NOT NULL,                   # 记忆类型: episodic / preference / procedural / semantic / prospective
    memory_key TEXT NOT NULL,                    # 记忆标识
    source TEXT DEFAULT '',                      # 信息来源: user_feedback / consolidation / manual / llm_inference
    confidence REAL DEFAULT 0.5,                 # 置信度
    evidence_count INTEGER DEFAULT 0,            # 证据数
    last_verified TEXT DEFAULT '',               # 最后验证时间
    is_conflicting INTEGER DEFAULT 0,            # 是否与其他记忆冲突
    conflict_with TEXT DEFAULT '',               # 与哪些记忆冲突
    freshness TEXT DEFAULT '',                   # 新鲜度: fresh / stale / expired
    metadata TEXT DEFAULT '{}',                  # 额外元数据 JSON
    update_time TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

# ── 关联记忆：记忆之间的关联图 ──
CREATE TABLE IF NOT EXISTS memory_link (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,                    # 源记忆类型
    source_key TEXT NOT NULL,                     # 源记忆标识
    target_type TEXT NOT NULL,                    # 目标记忆类型
    target_key TEXT NOT NULL,                     # 目标记忆标识
    relation TEXT NOT NULL,                       # 关联类型
    strength REAL DEFAULT 0.5,                    # 关联强度 0-1
    note TEXT DEFAULT '',                         # 关联说明
    create_time TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE(source_type, source_key, target_type, target_key, relation)
);

# ── 情感记忆：用户情绪追踪 ──
CREATE TABLE IF NOT EXISTS emotional_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER DEFAULT 0,                   # 关联任务
    emotion TEXT NOT NULL,                       # 情绪类型: positive / negative / anxious / bored
    emotion_label TEXT DEFAULT '',               # 中文标签
    intensity REAL DEFAULT 0,                    # 情绪强度 0-1
    direction TEXT DEFAULT 'neutral',            # positive / negative / neutral
    confidence REAL DEFAULT 0,                   # 检测置信度
    keywords TEXT DEFAULT '[]',                  # 触发关键词 JSON
    source TEXT DEFAULT 'user_input',            # 来源
    create_time TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

# ── 前瞻记忆：承诺与提醒 ──
CREATE TABLE IF NOT EXISTS prospective_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_intent TEXT NOT NULL,                   # 用户原始意图（"记住下周三提醒我交周报"）
    trigger_type TEXT NOT NULL DEFAULT 'time',   # 触发类型: time / event / condition
    trigger_value TEXT NOT NULL,                 # 触发值（时间/事件/条件）
    trigger_time TEXT DEFAULT '',                # 触发时间（time 类型）
    trigger_event TEXT DEFAULT '',               # 触发事件（event 类型）
    trigger_condition TEXT DEFAULT '',           # 触发条件（condition 类型）
    priority INTEGER DEFAULT 1,                  # 优先级: 0=低 1=中 2=高
    status TEXT DEFAULT 'pending',               # pending / triggered / completed / dismissed
    recurrence TEXT DEFAULT '',                  # 周期性: daily / weekly / monthly / ''
    last_triggered TEXT DEFAULT '',              # 上次触发时间
    trigger_count INTEGER DEFAULT 0,             # 已触发次数
    max_triggers INTEGER DEFAULT 0,              # 最大触发次数（0=无限）
    note TEXT DEFAULT '',                        # 备注
    created_time TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    update_time TEXT DEFAULT ''
);

# ── 演化引擎深化：个性化偏好画像 ──
CREATE TABLE IF NOT EXISTS user_preference (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pref_key TEXT NOT NULL UNIQUE,               # 偏好键
    pref_value TEXT NOT NULL,                    # 偏好值 JSON
    confidence REAL DEFAULT 0.5,                 # 置信度
    evidence_count INTEGER DEFAULT 0,            # 证据数
    last_evidence TEXT DEFAULT '',               # 最近证据
    update_time TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

# ── 演化引擎深化：演化报告 ──
CREATE TABLE IF NOT EXISTS evolution_report (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_type TEXT NOT NULL,                   # 类型: daily / weekly / milestone
    period_start TEXT,                           # 周期开始
    period_end TEXT,                             # 周期结束
    content TEXT NOT NULL,                       # 报告内容 JSON
    highlights TEXT DEFAULT '[]',                # 亮点 JSON
    suggestions TEXT DEFAULT '[]',               # 建议 JSON
    score_trend TEXT DEFAULT '[]',               # 分数趋势 JSON
    create_time TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
"""


def get_conn() -> sqlite3.Connection:
    """获取数据库连接（自动建表）。"""
    ensure_dirs()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _clean_sql(schema: str) -> str:
    """移除 SQL 中的 # 注释（整行 + 行内）。"""
    import re
    lines = []
    for line in schema.split("\n"):
        # 跳过纯注释行
        if line.strip().startswith("#"):
            continue
        # 移除行内注释
        line = re.sub(r"#.*$", "", line)
        lines.append(line)
    return "\n".join(lines)


def init_db() -> None:
    """初始化数据库：建表 + 迁移。"""
    ensure_dirs()
    conn = get_conn()
    try:
        # 清理注释后逐条执行 DDL
        clean_schema = _clean_sql(SCHEMA)
        for statement in clean_schema.split(";"):
            stmt = statement.strip()
            if stmt:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError as e:
                    if "already exists" not in str(e):
                        raise
        _migrate(conn)
        # 初始化 A/B 测试表
        _init_ab_tables(conn)
        conn.commit()
        logger.info("数据库初始化完成: %s", DB_PATH)
    finally:
        conn.close()


def _init_ab_tables(conn: sqlite3.Connection) -> None:
    """初始化 A/B 测试表。"""
    try:
        # 逐条执行（executescript 不能在 execute 失败后继续）
        for statement in _AB_TEST_SCHEMA.split(";"):
            stmt = statement.strip()
            if stmt:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError as e:
                    if "already exists" not in str(e):
                        raise
                except sqlite3.DatabaseError:
                    pass  # 忽略其他错误
    except Exception as e:
        logger.warning("A/B 测试表初始化: %s", e)


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
        "task_goal": "TEXT DEFAULT ''",
        "key_decisions": "TEXT DEFAULT '[]'",
        "related_preferences": "TEXT DEFAULT '[]'",
        "update_time": "TEXT DEFAULT ''",
    }
    for col, typ in needed_cols.items():
        if col not in existing_cols:
            try:
                conn.execute(f"ALTER TABLE task_list ADD COLUMN {col} {typ}")
                logger.info("迁移：task_list 新增列 %s", col)
            except sqlite3.OperationalError as e:
                logger.warning("迁移列 %s 失败: %s", col, e)

    # prospective_memory 新增列检测
    prospective_cols = {row[1] for row in conn.execute("PRAGMA table_info(prospective_memory)").fetchall()}
    if "priority" not in prospective_cols:
        try:
            conn.execute("ALTER TABLE prospective_memory ADD COLUMN priority INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass
    if "recurrence" not in prospective_cols:
        try:
            conn.execute("ALTER TABLE prospective_memory ADD COLUMN recurrence TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass

    # user_feedback 新增 processed 列（反馈学习标记）
    fb_cols = {row[1] for row in conn.execute("PRAGMA table_info(user_feedback)").fetchall()}
    if "processed" not in fb_cols:
        try:
            conn.execute("ALTER TABLE user_feedback ADD COLUMN processed INTEGER NOT NULL DEFAULT 0")
            logger.info("迁移：user_feedback 新增列 processed")
        except sqlite3.OperationalError as e:
            logger.warning("迁移列 processed 失败: %s", e)

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
