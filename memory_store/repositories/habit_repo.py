"""习惯权重数据访问。"""
import logging
from datetime import datetime
from memory_store.repositories.base import BaseRepository
from config.app_const import WEIGHT_MAX, WEIGHT_MIN

logger = logging.getLogger(__name__)


class HabitRepository(BaseRepository):
    """用户习惯权重 CRUD。"""

    def get(self, habit_key: str) -> dict | None:
        return self._execute_one(
            "SELECT * FROM user_habit_weight WHERE habit_key = ?", (habit_key,)
        )

    def list_all(self, valid_only: bool = False) -> list[dict]:
        sql = "SELECT * FROM user_habit_weight"
        if valid_only:
            sql += " WHERE is_valid = 1"
        sql += " ORDER BY weight DESC"
        return self._execute(sql)

    def set_weight(self, habit_key: str, weight: float) -> None:
        weight = max(WEIGHT_MIN, min(WEIGHT_MAX, weight))
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._execute(
            """INSERT INTO user_habit_weight (habit_key, weight, freq_count, last_use_time, is_valid)
               VALUES (?, ?, 1, ?, 1)
               ON CONFLICT(habit_key) DO UPDATE SET weight = excluded.weight""",
            (habit_key, weight, now)
        )

    def inc_freq(self, habit_key: str, delta: float = 0.1) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        existing = self.get(habit_key)
        if existing:
            new_w = min(WEIGHT_MAX, existing["weight"] + delta)
            self._update(
                "UPDATE user_habit_weight SET freq_count = freq_count + 1, weight = ?, last_use_time = ? WHERE habit_key = ?",
                (new_w, now, habit_key)
            )
        else:
            self._execute(
                "INSERT INTO user_habit_weight (habit_key, weight, freq_count, last_use_time, is_valid) VALUES (?, ?, 1, ?, 1)",
                (habit_key, delta, now)
            )

    def decay(self, days: int = 30) -> int:
        return self._update(
            """UPDATE user_habit_weight
               SET weight = MAX(0, weight * 0.5),
                   is_valid = CASE WHEN weight * 0.5 < 0.5 THEN 0 ELSE is_valid END
               WHERE last_use_time < datetime('now', ?)""",
            (f"-{days} days",)
        )
