"""常量、打分权重、演化阈值。"""
from enum import Enum


# ── 运行模式 ──
class RunMode(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"


# ── 任务类型 ──
class TaskType(str, Enum):
    WORK = "work"
    LIFE = "life"
    MIX = "mix"


# ── 任务状态 ──
class TaskStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAIL = "fail"


# ── 日程分类 ──
class ScheduleCategory(str, Enum):
    WORK = "work"
    LIFE = "life"
    HEALTH = "health"


# ── 日程状态 ──
class ScheduleStatus(str, Enum):
    PENDING = "pending"
    DONE = "done"


# ── 记账类型 ──
class BillType(str, Enum):
    INCOME = "income"
    EXPENSE = "expense"


# ── 演化类型 ──
class EvoType(str, Enum):
    FLOW = "flow"
    WEIGHT = "weight"
    TEMPLATE = "template"
    TOOL = "tool"


# ── 知识库分类 ──
class KBCategory(str, Enum):
    WORK_DOC = "work_doc"
    CONTRACT = "contract"
    PERSONAL = "personal"
    NOTE = "note"
    BILL = "bill"


# ── 打分权重 ──
WORK_SCORE_WEIGHTS = {
    "data_accuracy": 0.3,
    "report_completeness": 0.3,
    "reimbursement_norm": 0.2,
    "time_cost": 0.2,
}

LIFE_SCORE_WEIGHTS = {
    "expense_accuracy": 0.3,
    "schedule_fit": 0.3,
    "archive_completeness": 0.2,
    "preference_match": 0.2,
}

# ── 演化阈值 ──
EVOLUTION_THRESHOLD = 60.0       # 低于此分触发优化
WEIGHT_DECAY_DAYS = 30           # 超过未使用天数开始降权
WEIGHT_MAX = 10.0
WEIGHT_MIN = 0.0

# ── 窗口 ──
MAIN_WINDOW_DEFAULT_SIZE = (1000, 700)

# ── 健康提醒默认间隔（分钟）──
SEDENTARY_REMIND_INTERVAL = 60
DRINK_WATER_REMIND_INTERVAL = 45
