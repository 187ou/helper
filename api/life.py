"""个人生活&健康&事务模块 API：记账、健康、资料归档、习惯打卡。"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException

from memory_store.sqlite_db import get_conn, now_str
from config.app_const import BillType
from service.life_service import (
    add_bill_record, list_bills, get_monthly_summary,
    category_breakdown, delete_bill,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ═══════════════════════════════════════════
# 4.1 收支记账
# ═══════════════════════════════════════════

@router.get("/bill/list")
def bill_list(month: str = "", limit: int = 100):
    """列出记账记录。"""
    return list_bills(month=month, limit=limit)


@router.post("/bill/add")
def bill_add(body: dict):
    """添加收支记录。"""
    amount = body.get("amount", 0)
    if not amount or amount <= 0:
        raise HTTPException(status_code=400, detail="金额必须大于 0")
    return add_bill_record(
        bill_type=body.get("bill_type", "expense"),
        amount=amount,
        category=body.get("category", ""),
        description=body.get("description", ""),
        bill_date=body.get("bill_date", ""),
    )


@router.delete("/bill/{bid}")
def bill_delete(bid: int):
    """删除记账记录。"""
    delete_bill(bid)
    return {"ok": True}


@router.get("/bill/summary")
def bill_summary(month: str = ""):
    """月度收支汇总。"""
    return get_monthly_summary(month)


@router.get("/bill/category")
def bill_category(month: str = ""):
    """分类支出统计。"""
    return category_breakdown(month)


@router.get("/bill/trend")
def bill_trend(months: int = 6):
    """近 N 月收支趋势。"""
    result = []
    now = datetime.now()
    for i in range(months - 1, -1, -1):
        m = (now.replace(day=1) - timedelta(days=i * 30)).strftime("%Y-%m")
        summary = get_monthly_summary(m)
        # 修正月份
        conn = get_conn()
        income = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM bill_record WHERE bill_type=? AND bill_date LIKE ?",
            (BillType.INCOME.value, f"{m}%"),
        ).fetchone()[0]
        expense = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM bill_record WHERE bill_type=? AND bill_date LIKE ?",
            (BillType.EXPENSE.value, f"{m}%"),
        ).fetchone()[0]
        conn.close()
        result.append({"month": m, "income": income, "expense": expense})
    return result


# ═══════════════════════════════════════════
# 4.3 健康管理
# ═══════════════════════════════════════════

@router.get("/health/reminders")
def health_reminders():
    """获取健康提醒配置。"""
    from service.schedule_service import _load_reminders
    return _load_reminders()


@router.put("/health/reminders")
def update_reminders(body: dict):
    """更新健康提醒配置。"""
    from service.schedule_service import _reminder_state, _save_reminders
    for key, val in body.items():
        if key in _reminder_state:
            _reminder_state[key].update(val)
    _save_reminders()
    return _reminder_state


@router.get("/health/records")
def health_records(record_type: str = "", limit: int = 30):
    """查询健康记录。"""
    conn = get_conn()
    sql = "SELECT * FROM health_record WHERE 1=1"
    params: list = []
    if record_type:
        sql += " AND record_type = ?"
        params.append(record_type)
    sql += " ORDER BY record_date DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/health/record")
def add_health_record(body: dict):
    """添加健康记录。"""
    record_type = body.get("record_type", "")
    if record_type not in ("sleep", "water", "exercise", "weight", "sedentary"):
        raise HTTPException(status_code=400, detail="无效记录类型")

    record_date = body.get("record_date", datetime.now().strftime("%Y-%m-%d"))
    conn = get_conn()
    cursor = conn.execute(
        "INSERT INTO health_record (record_type, value, note, record_date) VALUES (?, ?, ?, ?)",
        (record_type, body.get("value", 0), body.get("note", ""), record_date),
    )
    conn.commit()
    rid = cursor.lastrowid
    conn.close()
    return {"id": rid, "type": record_type}


@router.get("/health/stats")
def health_stats():
    """健康数据统计。"""
    conn = get_conn()
    today = datetime.now().strftime("%Y-%m-%d")

    # 今日数据
    today_sleep = conn.execute(
        "SELECT value FROM health_record WHERE record_type='sleep' AND record_date=?", (today,)
    ).fetchone()
    today_water = conn.execute(
        "SELECT COALESCE(SUM(value),0) FROM health_record WHERE record_type='water' AND record_date=?", (today,)
    ).fetchone()[0]
    today_exercise = conn.execute(
        "SELECT COALESCE(SUM(value),0) FROM health_record WHERE record_type='exercise' AND record_date=?", (today,)
    ).fetchone()[0]

    # 近 7 天平均睡眠
    week_sleep = conn.execute(
        "SELECT AVG(value) FROM health_record WHERE record_type='sleep' AND record_date >= date('now', '-7 days')"
    ).fetchone()[0]

    conn.close()
    return {
        "today": {
            "sleep": today_sleep["value"] if today_sleep else 0,
            "water": today_water,
            "exercise": today_exercise,
        },
        "avg_sleep_7d": round(week_sleep, 1) if week_sleep else 0,
    }


# ═══════════════════════════════════════════
# 4.4 个人资料归档
# ═══════════════════════════════════════════

@router.get("/archive/list")
def archive_list(category: str = "", keyword: str = ""):
    """列出个人资料。"""
    conn = get_conn()
    sql = "SELECT * FROM personal_archive WHERE 1=1"
    params: list = []
    if category:
        sql += " AND category = ?"
        params.append(category)
    if keyword:
        sql += " AND (title LIKE ? OR description LIKE ? OR tags LIKE ?)"
        params.extend([f"%{keyword}%"] * 3)
    sql += " ORDER BY create_time DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/archive/add")
def archive_add(body: dict):
    """添加个人资料。"""
    title = (body.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="标题不能为空")

    conn = get_conn()
    cursor = conn.execute(
        """INSERT INTO personal_archive (title, category, file_path, description, tags)
           VALUES (?, ?, ?, ?, ?)""",
        (title, body.get("category", "other"), body.get("file_path", ""),
         body.get("description", ""), body.get("tags", "")),
    )
    conn.commit()
    rid = cursor.lastrowid
    conn.close()
    return {"id": rid, "title": title}


@router.delete("/archive/{aid}")
def archive_delete(aid: int):
    """删除资料。"""
    conn = get_conn()
    conn.execute("DELETE FROM personal_archive WHERE id = ?", (aid,))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/archive/categories")
def archive_categories():
    """获取资料分类统计。"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT category, COUNT(*) as cnt FROM personal_archive GROUP BY category ORDER BY cnt DESC"
    ).fetchall()
    conn.close()
    return {r["category"]: r["cnt"] for r in rows}


# ═══════════════════════════════════════════
# 4.5 习惯打卡
# ═══════════════════════════════════════════

@router.get("/habit/list")
def habit_list():
    """列出所有习惯。"""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    try:
        rows = conn.execute("SELECT * FROM habit ORDER BY create_time DESC").fetchall()

        result = []
        for r in rows:
            d = dict(r)
            # 计算连续打卡天数
            checkins = conn.execute(
                "SELECT checkin_date FROM habit_checkin WHERE habit_id = ? ORDER BY checkin_date DESC",
                (d["id"],),
            ).fetchall()
            streak = 0
            checkin_dates = [c["checkin_date"] for c in checkins]
            check_date = today
            while check_date in checkin_dates:
                streak += 1
                dt = datetime.strptime(check_date, "%Y-%m-%d")
                check_date = (dt - timedelta(days=1)).strftime("%Y-%m-%d")

            d["streak"] = streak
            d["checked_today"] = today in checkin_dates
            d["total_checkins"] = len(checkin_dates)
            result.append(d)
        return result
    finally:
        conn.close()


@router.post("/habit/create")
def habit_create(body: dict):
    """创建习惯。"""
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="习惯名称不能为空")

    conn = get_conn()
    cursor = conn.execute(
        "INSERT INTO habit (name, frequency, target_days) VALUES (?, ?, ?)",
        (name, body.get("frequency", "daily"), body.get("target_days", 30)),
    )
    conn.commit()
    hid = cursor.lastrowid
    conn.close()
    return {"id": hid, "name": name}


@router.post("/habit/{hid}/checkin")
def habit_checkin(hid: int, body: dict):
    """打卡。"""
    checkin_date = body.get("checkin_date", datetime.now().strftime("%Y-%m-%d"))
    note = body.get("note", "")

    conn = get_conn()
    # 检查是否已打卡
    existing = conn.execute(
        "SELECT id FROM habit_checkin WHERE habit_id = ? AND checkin_date = ?",
        (hid, checkin_date),
    ).fetchone()

    if existing:
        conn.close()
        return {"ok": False, "message": "今日已打卡"}

    conn.execute(
        "INSERT INTO habit_checkin (habit_id, checkin_date, note) VALUES (?, ?, ?)",
        (hid, checkin_date, note),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "date": checkin_date}


@router.delete("/habit/{hid}/checkin")
def habit_checkin_delete(hid: int, checkin_date: str = ""):
    """取消打卡。"""
    if not checkin_date:
        checkin_date = datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    conn.execute(
        "DELETE FROM habit_checkin WHERE habit_id = ? AND checkin_date = ?",
        (hid, checkin_date),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/habit/{hid}")
def habit_delete(hid: int):
    """删除习惯。"""
    conn = get_conn()
    conn.execute("DELETE FROM habit_checkin WHERE habit_id = ?", (hid,))
    conn.execute("DELETE FROM habit WHERE id = ?", (hid,))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/habit/{hid}/calendar")
def habit_calendar(hid: int, month: str = ""):
    """获取习惯月度打卡日历。"""
    if not month:
        month = datetime.now().strftime("%Y-%m")
    conn = get_conn()
    rows = conn.execute(
        "SELECT checkin_date FROM habit_checkin WHERE habit_id = ? AND checkin_date LIKE ?",
        (hid, f"{month}%"),
    ).fetchall()
    conn.close()
    return [r["checkin_date"] for r in rows]
