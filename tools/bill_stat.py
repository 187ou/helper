"""收支统计工具（骨架）。"""
import logging
from typing import Any

logger = logging.getLogger(__name__)


def monthly_summary(records: list[dict]) -> dict[str, Any]:
    """月度收支汇总。"""
    income = sum(r.get("amount", 0) for r in records if r.get("bill_type") == "income")
    expense = sum(r.get("amount", 0) for r in records if r.get("bill_type") == "expense")
    return {"income": income, "expense": expense, "balance": income - expense, "count": len(records)}


def category_breakdown(records: list[dict]) -> dict[str, float]:
    """分类汇总。"""
    result: dict[str, float] = {}
    for r in records:
        cat = r.get("category", "其他")
        result[cat] = result.get(cat, 0) + r.get("amount", 0)
    return result
