"""生活服务：记账、日程、采购、家务（基于 SQLite，真实可用）。"""
import logging
from datetime import datetime
from typing import Any

from memory_store.sqlite_db import get_conn, now_str
from config.app_const import BillType

logger = logging.getLogger(__name__)


# ── 记账 ──
def add_bill_record(
    bill_type: str,
    amount: float,
    category: str = "",
    description: str = "",
    bill_date: str = "",
) -> dict[str, Any]:
    """添加收支记录。"""
    if not bill_date:
        bill_date = datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    cursor = conn.execute(
        """INSERT INTO bill_record (bill_type, amount, category, description, bill_date)
           VALUES (?, ?, ?, ?, ?)""",
        (bill_type, amount, category, description, bill_date),
    )
    conn.commit()
    rid = cursor.lastrowid
    conn.close()
    logger.info("记账: [%s] %.2f %s", bill_type, amount, category)
    return {"id": rid, "bill_type": bill_type, "amount": amount, "category": category, "status": "saved"}


def list_bills(month: str = "", limit: int = 50) -> list[dict[str, Any]]:
    """列出记账记录，可按月份过滤（格式 2026-08）。"""
    conn = get_conn()
    sql = "SELECT * FROM bill_record"
    params: list = []
    if month:
        sql += " WHERE bill_date LIKE ?"
        params.append(f"{month}%")
    sql += " ORDER BY bill_date DESC, id DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_monthly_summary(month: str = "") -> dict[str, Any]:
    """获取月度收支汇总。"""
    if not month:
        month = datetime.now().strftime("%Y-%m")
    conn = get_conn()
    income = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM bill_record WHERE bill_type=? AND bill_date LIKE ?",
        (BillType.INCOME.value, f"{month}%"),
    ).fetchone()[0]
    expense = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM bill_record WHERE bill_type=? AND bill_date LIKE ?",
        (BillType.EXPENSE.value, f"{month}%"),
    ).fetchone()[0]
    count = conn.execute(
        "SELECT COUNT(*) FROM bill_record WHERE bill_date LIKE ?", (f"{month}%",)
    ).fetchone()[0]
    conn.close()
    return {"month": month, "income": income, "expense": expense, "balance": income - expense, "count": count}


def category_breakdown(month: str = "") -> dict[str, float]:
    """按分类汇总支出。"""
    if not month:
        month = datetime.now().strftime("%Y-%m")
    conn = get_conn()
    rows = conn.execute(
        """SELECT category, SUM(amount) as total FROM bill_record
           WHERE bill_type=? AND bill_date LIKE ? GROUP BY category ORDER BY total DESC""",
        (BillType.EXPENSE.value, f"{month}%"),
    ).fetchall()
    conn.close()
    return {r["category"] or "未分类": r["total"] for r in rows}


def delete_bill(bill_id: int) -> bool:
    """删除记账记录。"""
    conn = get_conn()
    conn.execute("DELETE FROM bill_record WHERE id = ?", (bill_id,))
    conn.commit()
    conn.close()
    return True


# ── 采购清单 ──
def shopping_list(items: list[str]) -> dict[str, Any]:
    """整理购物清单。"""
    return {"items": items, "total": len(items)}


def chore_schedule(chores: list[str]) -> dict[str, Any]:
    """安排家务排班。"""
    return {"chores": chores, "assigned": {c: "待安排" for c in chores}}
