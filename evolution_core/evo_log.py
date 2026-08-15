"""演化日志记录 —— 委托给 EvoRepository。"""
import logging
from typing import Any
from memory_store.repositories.evo_repo import EvoRepository
from config.app_const import EvoType

logger = logging.getLogger(__name__)

_repo = EvoRepository()


def log_evo(evo_type: str, before: str, after: str) -> int:
    rid = _repo.log(evo_type, before, after)
    logger.info("演化日志 [%s]: %s → %s", evo_type, before[:50], after[:50])
    return rid


def log_flow_optimize(before_steps: list, after_steps: list) -> int:
    before_text = " → ".join(s.get("name", "?") for s in before_steps)
    after_text = " → ".join(s.get("name", "?") for s in after_steps)
    return log_evo(EvoType.FLOW.value, before_text, after_text)


def log_weight_change(habit_key: str, old_w: float, new_w: float) -> int:
    return log_evo(EvoType.WEIGHT.value, f"{habit_key} = {old_w:.1f}", f"{habit_key} = {new_w:.1f}")


def log_template_save(name: str, freq: int) -> int:
    return log_evo(EvoType.TEMPLATE.value, f"高频任务: {name}", f"固化模板 (频次 {freq})")


def list_logs(evo_type: str = "", limit: int = 50) -> list[dict[str, Any]]:
    return _repo.list_all(evo_type=evo_type, limit=limit)


def get_stats() -> dict[str, int]:
    return _repo.get_stats()
