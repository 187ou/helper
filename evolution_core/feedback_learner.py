"""用户反馈学习：从用户修改/驳回中提炼偏好（含完整边缘处理）。

边缘情况处理：
1. 空内容/None → 跳过处理
2. 超长内容 → 自动截断
3. 数据库写入失败 → 记录日志 + 不影响主流程
4. JSON 解析失败 → 使用默认值
5. 并发写入 → 利用 SQLite WAL 模式
6. 相同反馈重复记录 → 允许（每次反馈都是证据）
"""
import difflib
import json
import logging
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from memory_store.sqlite_db import get_conn, now_str
from evolution_core.safe_ops import (
    safe_db_write, safe_json_loads, safe_json_dumps,
    safe_divide, sanitize_text, clamp_value,
)

logger = logging.getLogger(__name__)

# 内容最大长度（防止 DB 膨胀）
_MAX_CONTENT_LEN = 1000
_MAX_EVIDENCE_LEN = 200


@safe_db_write(default_return=None)
def record_feedback(
    feedback_type: str,
    original: str = "",
    modified: str = "",
    task_id: int = 0,
    task_type: str = "",
    context: dict | None = None,
) -> int | None:
    """记录一条用户反馈。"""
    if feedback_type not in ("modify", "reject", "retry", "praise"):
        return None

    # 清理输入
    original = sanitize_text(original, _MAX_CONTENT_LEN)
    modified = sanitize_text(modified, _MAX_CONTENT_LEN)
    task_type = sanitize_text(task_type, 50)

    # 计算差异摘要
    diff_summary = _compute_diff(original, modified) if original and modified else ""
    diff_summary = sanitize_text(diff_summary, _MAX_EVIDENCE_LEN)

    conn = get_conn()
    try:
        cursor = conn.execute(
            """INSERT INTO user_feedback
               (task_id, feedback_type, original_content, modified_content, diff_summary, task_type, context)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                task_id, feedback_type, original, modified,
                diff_summary, task_type,
                safe_json_dumps(context or {}),
            ),
        )
        conn.commit()
        fid = cursor.lastrowid
    finally:
        conn.close()

    logger.info("用户反馈: [%s] task=%d", feedback_type, task_id)

    # 触发偏好学习
    try:
        _learn_from_feedback(feedback_type, original, modified, task_type, diff_summary)
    except Exception as e:
        logger.warning("偏好学习异常: %s", e)

    return fid


def get_preference(pref_key: str) -> dict[str, Any] | None:
    """获取用户偏好。"""
    if not pref_key:
        return None

    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM user_preference WHERE pref_key = ?", (pref_key,)
        ).fetchone()
    except Exception:
        return None
    finally:
        conn.close()

    if not row:
        return None

    value = safe_json_loads(row["pref_value"], default=row["pref_value"])

    return {
        "key": row["pref_key"],
        "value": value,
        "confidence": row["confidence"],
        "evidence_count": row["evidence_count"],
        "last_evidence": row["last_evidence"],
    }


def get_all_preferences() -> list[dict[str, Any]]:
    """获取所有用户偏好。"""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM user_preference ORDER BY confidence DESC, evidence_count DESC"
        ).fetchall()
    except Exception:
        return []
    finally:
        conn.close()

    result = []
    for row in rows:
        value = safe_json_loads(row["pref_value"], default=row["pref_value"])
        result.append({
            "key": row["pref_key"],
            "value": value,
            "confidence": row["confidence"],
            "evidence_count": row["evidence_count"],
            "last_evidence": row["last_evidence"],
            "update_time": row["update_time"],
        })
    return result


def generate_execution_guidance(task_type: str = "") -> str:
    """生成执行指导。"""
    try:
        preferences = get_all_preferences()
    except Exception:
        return ""

    if not preferences:
        return ""

    guidance_parts = []
    task_type = sanitize_text(task_type, 50)

    for pref in preferences:
        if pref["confidence"] < 0.3:
            continue

        key = pref["key"]
        value = pref["value"]

        if key.startswith("style:"):
            guidance_parts.append(f"文风: {_format_pref_value(value)}")
        elif key.startswith("format:"):
            guidance_parts.append(f"格式: {_format_pref_value(value)}")
        elif key.startswith("length:"):
            guidance_parts.append(f"长度: {_format_pref_value(value)}")
        elif key.startswith("tone:"):
            guidance_parts.append(f"语气: {_format_pref_value(value)}")
        elif key.startswith("avoid:"):
            guidance_parts.append(f"避免: {_format_pref_value(value)}")
        elif key.startswith("prefer:"):
            guidance_parts.append(f"偏好: {_format_pref_value(value)}")
        elif key.startswith(f"type:{task_type}:"):
            guidance_parts.append(f"该类型偏好: {_format_pref_value(value)}")

    return "\n".join(guidance_parts)


def analyze_feedback_trends(days: int = 30) -> dict[str, Any]:
    """分析反馈趋势。"""
    days = clamp_value(days, 1, 365)

    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT feedback_type, COUNT(*) as cnt FROM user_feedback
               WHERE create_time >= datetime('now', ?)
               GROUP BY feedback_type ORDER BY cnt DESC""",
            (f"-{int(days)} days",)
        ).fetchall()
    except Exception:
        return {"total": 0, "satisfaction": 0, "by_type": {}}
    finally:
        conn.close()

    total = sum(r["cnt"] for r in rows)
    if total == 0:
        return {"total": 0, "satisfaction": 0, "by_type": {}}

    by_type = {r["feedback_type"]: r["cnt"] for r in rows}
    praise = by_type.get("praise", 0)
    modify = by_type.get("modify", 0)
    reject = by_type.get("reject", 0)

    satisfaction = safe_divide(praise, praise + modify + reject, default=0)

    return {
        "total": total,
        "satisfaction": round(satisfaction, 3),
        "by_type": by_type,
        "trend": "improving" if satisfaction > 0.7 else "needs_improvement",
    }


def get_feedback_stats() -> dict[str, Any]:
    """获取反馈统计。"""
    conn = get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM user_feedback").fetchone()[0]

        type_rows = conn.execute(
            "SELECT feedback_type, COUNT(*) as cnt FROM user_feedback GROUP BY feedback_type"
        ).fetchall()

        task_type_rows = conn.execute(
            "SELECT task_type, COUNT(*) as cnt FROM user_feedback WHERE task_type != '' GROUP BY task_type"
        ).fetchall()

        recent = conn.execute(
            "SELECT COUNT(*) FROM user_feedback WHERE create_time >= datetime('now', '-7 days')"
        ).fetchone()[0]
    except Exception:
        return {"total": 0, "by_type": {}, "by_task_type": {}, "recent_7d": 0}
    finally:
        conn.close()

    return {
        "total": total,
        "by_type": {r["feedback_type"]: r["cnt"] for r in type_rows},
        "by_task_type": {r["task_type"]: r["cnt"] for r in task_type_rows},
        "recent_7d": recent,
    }


# ── 内部实现 ──

def _learn_from_feedback(
    feedback_type: str,
    original: str,
    modified: str,
    task_type: str,
    diff_summary: str,
) -> None:
    """分析反馈内容，提炼偏好规则。"""
    if feedback_type == "praise":
        _reinforce_preference(f"type:{task_type}:style", _detect_style(original), task_type)
        return

    if feedback_type in ("modify", "reject"):
        if original and modified:
            diff = _analyze_modification(original, modified)
            if diff:
                _store_preference(diff["key"], diff["value"], diff["evidence"], task_type)


def _analyze_modification(original: str, modified: str) -> dict | None:
    """分析用户修改内容，提炼偏好。"""
    if original == modified:
        return None

    # 长度变化分析
    len_diff = len(modified) - len(original)
    if abs(len_diff) > len(original) * 0.3:
        if len_diff < 0:
            return {"key": "length:prefer", "value": "简洁", "evidence": f"从 {len(original)} 字精简到 {len(modified)} 字"}
        else:
            return {"key": "length:prefer", "value": "详细", "evidence": f"从 {len(original)} 字扩充到 {len(modified)} 字"}

    # 格式变化分析
    if "\n" in modified and "\n" not in original:
        return {"key": "format:prefer", "value": "分段结构", "evidence": "改为分段格式"}

    # 语气变化分析
    formal_words = ["因此", "综上所述", "特此", "谨此"]
    casual_words = ["所以", "总的来说", "给你", "看看"]
    original_formal = sum(1 for w in formal_words if w in original)
    modified_formal = sum(1 for w in formal_words if w in modified)
    original_casual = sum(1 for w in casual_words if w in original)
    modified_casual = sum(1 for w in casual_words if w in modified)

    if modified_formal > original_formal:
        return {"key": "tone:prefer", "value": "正式", "evidence": "增加正式用语"}
    if modified_casual > original_casual:
        return {"key": "tone:prefer", "value": "口语化", "evidence": "增加口语化表达"}

    # 关键词替换分析
    diff = list(difflib.unified_diff(original.split(), modified.split()))
    added_words = [d[1:] for d in diff if d.startswith("+") and not d.startswith("+++")]

    if added_words:
        return {"key": "prefer:additions", "value": added_words[:5], "evidence": f"添加: {', '.join(added_words[:5])}"}

    return None


def _detect_style(text: str) -> str:
    """检测文本风格。"""
    if not text:
        return "中性"
    if any(w in text for w in ["因此", "综上所述", "特此"]):
        return "正式"
    if any(w in text for w in ["所以", "总的来说", "给你"]):
        return "口语化"
    if "\n\n" in text or "1." in text:
        return "结构化"
    return "中性"


def _store_preference(key: str, value: Any, evidence: str, task_type: str = "") -> None:
    """存储或更新偏好。"""
    if not key:
        return

    key = sanitize_text(key, 100)
    evidence = sanitize_text(evidence, _MAX_EVIDENCE_LEN)

    conn = get_conn()
    try:
        existing = conn.execute(
            "SELECT * FROM user_preference WHERE pref_key = ?", (key,)
        ).fetchone()

        if existing:
            new_evidence = existing["evidence_count"] + 1
            new_confidence = round(clamp_value(1 - 1 / (new_evidence + 1), 0, 1), 3)

            conn.execute(
                """UPDATE user_preference SET
                    pref_value = ?, confidence = ?, evidence_count = ?,
                    last_evidence = ?, update_time = ?
                   WHERE pref_key = ?""",
                (
                    safe_json_dumps(value),
                    new_confidence, new_evidence, evidence, now_str(), key,
                ),
            )
        else:
            conn.execute(
                """INSERT INTO user_preference
                   (pref_key, pref_value, confidence, evidence_count, last_evidence)
                   VALUES (?, ?, 0.5, 1, ?)""",
                (key, safe_json_dumps(value), evidence),
            )
        conn.commit()
    except Exception as e:
        logger.warning("偏好存储失败: %s", e)
    finally:
        conn.close()


def _reinforce_preference(key: str, value: str, task_type: str) -> None:
    """正反馈强化偏好。"""
    if key:
        _store_preference(key, value, f"正反馈确认: {value}", task_type)


def _compute_diff(original: str, modified: str) -> str:
    """计算两段文本的差异摘要。"""
    if original == modified:
        return ""
    try:
        matcher = difflib.SequenceMatcher(None, original, modified)
        ratio = matcher.ratio()
        if ratio > 0.9:
            return "微调"
        elif ratio > 0.7:
            return "中等修改"
        else:
            return "大幅重写"
    except Exception:
        return "修改"


def _format_pref_value(value: Any) -> str:
    """格式化偏好值为可读字符串。"""
    if isinstance(value, list):
        return "、".join(str(v) for v in value[:5])
    return str(value)
