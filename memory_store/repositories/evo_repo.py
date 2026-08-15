"""演化日志数据访问。"""
import json
import logging
from datetime import datetime
from memory_store.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class EvoRepository(BaseRepository):
    """演化日志 CRUD。"""

    def log(self, evo_type: str, before: str, after: str) -> int:
        """记录演化。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_id = self._insert(
            "INSERT INTO evolution_log (evo_type, before_content, after_content, evo_time) VALUES (?, ?, ?, ?)",
            (evo_type, before, after, now)
        )
        logger.debug("演化记录: id=%d, type=%s", log_id, evo_type)
        return log_id

    def list_all(self, evo_type: str = "", limit: int = 100) -> list[dict]:
        if evo_type:
            return self._execute(
                "SELECT * FROM evolution_log WHERE evo_type = ? ORDER BY id DESC LIMIT ?",
                (evo_type, limit)
            )
        return self._execute(
            "SELECT * FROM evolution_log ORDER BY id DESC LIMIT ?", (limit,)
        )

    def get_stats(self) -> dict:
        """统计各类演化数量。"""
        rows = self._execute(
            "SELECT evo_type, COUNT(*) as cnt FROM evolution_log GROUP BY evo_type"
        )
        stats = {"flow_optimizations": 0, "tool_count": 0, "template_count": 0, "weight_count": 0}
        type_map = {"flow": "flow_optimizations", "tool": "tool_count",
                    "template": "template_count", "weight": "weight_count"}
        for row in rows:
            key = type_map.get(row["evo_type"])
            if key:
                stats[key] = row["cnt"]
        return stats

    def log_flow_optimize(self, old_steps: list, new_steps: list) -> None:
        self.log("flow", str(len(old_steps)), str(len(new_steps)))

    def log_template_save(self, name: str, freq: int) -> None:
        self.log("template", name, f"freq={freq}")
