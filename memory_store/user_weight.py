"""用户习惯权重 —— 委托给 HabitRepository。"""
import logging
from memory_store.repositories.habit_repo import HabitRepository

logger = logging.getLogger(__name__)

_repo = HabitRepository()


def get_habit(habit_key: str):
    return _repo.get(habit_key)


def get_all_habits(valid_only: bool = False):
    return _repo.list_all(valid_only)


def set_weight(habit_key: str, weight: float):
    _repo.set_weight(habit_key, weight)


def inc_freq(habit_key: str, delta_weight: float = 0.1):
    _repo.inc_freq(habit_key, delta_weight)


def create_habit(habit_key: str, weight: float = 5.0) -> None:
    """创建新习惯条目。"""
    _repo.create(habit_key, weight)


def decay_expired(days: int = 30) -> int:
    affected = _repo.decay(days)
    logger.info("降权过期习惯 %d 条", affected)
    return affected
