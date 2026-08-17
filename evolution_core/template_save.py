"""高频模板自动固化（基于使用频次 + 质量门槛检测）。

固化门槛：
- 频次 >= 5 次（避免一次性任务污染模板库）
- 平均得分 >= 70 分（确保固化的是高质量流程）
"""
import json
import logging
from typing import Any

from memory_store.sqlite_db import get_conn, now_str
from memory_store.user_weight import get_all_habits

logger = logging.getLogger(__name__)

# ── 固化门槛 ──
MIN_TEMPLATE_FREQ = 5       # 最低频次（避免一次性任务污染）
MIN_AVG_SCORE = 70.0        # 最低平均分（确保高质量流程）


def check_and_save_template(task_text: str, steps: list[dict]) -> dict[str, Any] | None:
    """检查任务是否高频且高质量，若是则固化为模板。

    双重门槛：
    1. 频次 >= MIN_TEMPLATE_FREQ（默认 5 次）
    2. 历史平均得分 >= MIN_AVG_SCORE（默认 70 分）
    """
    if not steps:
        return None

    # 提取习惯关键词（与权重迭代共用同一套取键逻辑，保证能查到频次）
    from evolution_core.weight_evolve import extract_primary_habit_key
    habit_key = extract_primary_habit_key(task_text)

    conn = get_conn()
    try:
        # 1. 频次门槛
        habit = conn.execute(
            "SELECT * FROM user_habit_weight WHERE habit_key = ?", (habit_key,)
        ).fetchone()
        if not habit or habit["freq_count"] < MIN_TEMPLATE_FREQ:
            return None

        # 2. 质量门槛
        avg_score = _calc_habit_avg_score(conn, habit_key)
        if avg_score < MIN_AVG_SCORE:
            logger.debug("模板固化跳过 %s: 平均分 %.1f < %.1f", habit_key, avg_score, MIN_AVG_SCORE)
            return None

        # 3. 去重
        if conn.execute("SELECT id FROM custom_template WHERE name = ?", (habit_key,)).fetchone():
            logger.info("模板已存在: %s", habit_key)
            return None

        # 4. 固化（含程序性记忆：决策规则 + 成功经验 + 常见错误）
        flow = {
            "source_task": task_text,
            "habit_key": habit_key,
            "freq_count": habit["freq_count"],
            "avg_score": round(avg_score, 1),
            "steps": steps,
            "decision_rules": _extract_decision_rules(conn, habit_key),
            "success_patterns": _extract_success_patterns(conn, habit_key),
            "common_mistakes": _extract_common_mistakes(conn, habit_key),
        }
        conn.execute(
            "INSERT INTO custom_template (name, task_flow_json) VALUES (?, ?)",
            (habit_key, json.dumps(flow, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        conn.close()

    logger.info("固化模板: %s (频次 %d, 均分 %.1f, %d 条规则)",
                habit_key, habit["freq_count"], avg_score, len(flow["decision_rules"]))
    return {"name": habit_key, "freq": habit["freq_count"], "avg_score": round(avg_score, 1)}


def _extract_decision_rules(conn, habit_key: str) -> list[dict]:
    """从高分历史任务中提取决策规则（程序性记忆）。

    分析高分任务的关键决策，提炼为可复用的规则。
    """
    try:
        keyword = f"%{habit_key}%"
        rows = conn.execute(
            """SELECT key_decisions FROM task_list
               WHERE (task_content LIKE ? OR tags LIKE ?)
                 AND work_score > 70
                 AND key_decisions IS NOT NULL AND key_decisions != '[]'
               ORDER BY work_score DESC LIMIT 10""",
            (keyword, keyword),
        ).fetchall()

        rules = []
        seen_decisions = set()
        for row in rows:
            try:
                decisions = json.loads(row["key_decisions"]) if row["key_decisions"] else []
                for d in decisions:
                    decision_text = d.get("decision", "")
                    if decision_text and decision_text not in seen_decisions:
                        seen_decisions.add(decision_text)
                        rules.append({
                            "when": d.get("step", "执行时"),
                            "then": decision_text,
                        })
            except (json.JSONDecodeError, TypeError):
                continue

        return rules[:5]  # 最多保留 5 条规则
    except Exception:
        return []


def _extract_success_patterns(conn, habit_key: str) -> list[str]:
    """从高分任务中提取成功模式（程序性记忆）。"""
    try:
        keyword = f"%{habit_key}%"
        rows = conn.execute(
            """SELECT task_steps FROM task_list
               WHERE (task_content LIKE ? OR tags LIKE ?)
                 AND work_score > 80
                 AND task_steps IS NOT NULL AND task_steps != '[]'
               ORDER BY work_score DESC LIMIT 5""",
            (keyword, keyword),
        ).fetchall()

        # 统计高频步骤模式
        step_sequences = []
        for row in rows:
            try:
                steps = json.loads(row["task_steps"]) if row["task_steps"] else []
                names = [s.get("name", "") for s in steps if s.get("name")]
                if len(names) >= 2:
                    step_sequences.append(" → ".join(names))
            except (json.JSONDecodeError, TypeError):
                continue

        # 返回最常见的模式（去重）
        from collections import Counter
        counter = Counter(step_sequences)
        return [seq for seq, _ in counter.most_common(3)]
    except Exception:
        return []


def _extract_common_mistakes(conn, habit_key: str) -> list[str]:
    """从低分任务中提取常见错误（程序性记忆）。"""
    try:
        keyword = f"%{habit_key}%"
        rows = conn.execute(
            """SELECT task_steps FROM task_list
               WHERE (task_content LIKE ? OR tags LIKE ?)
                 AND work_score > 0 AND work_score < 50
                 AND task_steps IS NOT NULL AND task_steps != '[]'
               ORDER BY work_score ASC LIMIT 5""",
            (keyword, keyword),
        ).fetchall()

        mistakes = []
        for row in rows:
            try:
                steps = json.loads(row["task_steps"]) if row["task_steps"] else []
                for s in steps:
                    if s.get("status") == "failed":
                        mistakes.append(f"步骤「{s.get('name', '?')}」易失败")
            except (json.JSONDecodeError, TypeError):
                continue

        # 去重
        return list(set(mistakes))[:3]
    except Exception:
        return []


def _calc_habit_avg_score(conn, habit_key: str) -> float:
    """计算某习惯关键词的历史平均得分。"""
    try:
        keyword = f"%{habit_key}%"
        row = conn.execute(
            """SELECT AVG(work_score) as avg_work, AVG(life_score) as avg_life, COUNT(*) as cnt
               FROM task_list
               WHERE (task_content LIKE ? OR tags LIKE ?)
                 AND status IN ('done', 'success')
                 AND (work_score > 0 OR life_score > 0)""",
            (keyword, keyword),
        ).fetchone()

        if not row or row["cnt"] == 0:
            return 0.0

        # 取 work_score 和 life_score 中有效的一个
        scores = []
        if row["avg_work"] and row["avg_work"] > 0:
            scores.append(row["avg_work"])
        if row["avg_life"] and row["avg_life"] > 0:
            scores.append(row["avg_life"])

        return sum(scores) / len(scores) if scores else 0.0
    except Exception:
        return 0.0


def list_templates() -> list[dict[str, Any]]:
    """列出所有模板。"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM custom_template ORDER BY create_time DESC"
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        flow = json.loads(r["task_flow_json"]) if r["task_flow_json"] else {}
        result.append({
            "id": r["id"],
            "name": r["name"],
            "steps": flow.get("steps", []),
            "freq": flow.get("freq_count", 0),
            "avg_score": flow.get("avg_score", 0),
            # ── 程序性记忆字段 ──
            "decision_rules": flow.get("decision_rules", []),
            "success_patterns": flow.get("success_patterns", []),
            "common_mistakes": flow.get("common_mistakes", []),
            "create_time": r["create_time"],
        })
    return result


def get_template(name: str) -> dict[str, Any] | None:
    """获取指定模板。"""
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM custom_template WHERE name = ?", (name,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    return json.loads(row["task_flow_json"]) if row["task_flow_json"] else None
