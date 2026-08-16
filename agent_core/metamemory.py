"""元记忆（Metamemory）：记忆系统"知道自己知道什么"。

解决缺口：当前系统不知道信息的可靠程度，无法判断"我确定吗？"。

核心能力：
1. 信息来源追踪：每条记忆来自哪里（用户反馈/巩固/手动/推断）
2. 置信度展示：偏好/知识的可信程度
3. 冲突检测：发现互相矛盾的记忆
4. 新鲜度评估：信息是否过期
5. 系统健康监控：记忆系统的整体状态
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# ── 新鲜度阈值（天）──
FRESHNESS_THRESHOLDS = {
    "fresh": 7,       # 7 天内为新鲜
    "stale": 30,      # 30 天内为陈旧
    "expired": 90,    # 90 天以上为过期
}


def track_memory(memory_type: str, memory_key: str, source: str = "",
                 confidence: float = 0.5, evidence_count: int = 0,
                 metadata: dict | None = None) -> None:
    """追踪一条记忆的来源和状态（在记忆创建/更新时调用）。

    Args:
        memory_type: 记忆类型 (episodic / preference / procedural / semantic / prospective)
        memory_key: 记忆标识
        source: 信息来源
        confidence: 置信度
        evidence_count: 证据数
        metadata: 额外元数据
    """
    try:
        from memory_store.sqlite_db import get_conn

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        freshness = _calculate_freshness(confidence, evidence_count)

        conn = get_conn()
        try:
            # 检查是否已存在
            existing = conn.execute(
                "SELECT * FROM metamemory WHERE memory_type = ? AND memory_key = ?",
                (memory_type, memory_key),
            ).fetchone()

            if existing:
                conn.execute(
                    """UPDATE metamemory SET
                        source = ?, confidence = ?, evidence_count = ?,
                        last_verified = ?, freshness = ?, metadata = ?,
                        update_time = ?
                       WHERE memory_type = ? AND memory_key = ?""",
                    (source, confidence, evidence_count, now,
                     freshness, json.dumps(metadata or {}, ensure_ascii=False),
                     now, memory_type, memory_key),
                )
            else:
                conn.execute(
                    """INSERT INTO metamemory
                       (memory_type, memory_key, source, confidence, evidence_count,
                        last_verified, freshness, metadata, update_time)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (memory_type, memory_key, source, confidence, evidence_count,
                     now, freshness, json.dumps(metadata or {}, ensure_ascii=False), now),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.debug("元记忆追踪失败: %s", e)


def _calculate_freshness(confidence: float, evidence_count: int) -> str:
    """根据置信度和证据数计算新鲜度。"""
    if confidence >= 0.7 and evidence_count >= 3:
        return "fresh"
    elif confidence >= 0.4 or evidence_count >= 1:
        return "stale"
    else:
        return "expired"


def get_memory_reliability(memory_type: str, memory_key: str) -> dict[str, Any] | None:
    """获取某条记忆的可靠性信息。"""
    try:
        from memory_store.sqlite_db import get_conn

        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM metamemory WHERE memory_type = ? AND memory_key = ?",
                (memory_type, memory_key),
            ).fetchone()
        finally:
            conn.close()

        if not row:
            return None

        return {
            "memory_type": row["memory_type"],
            "memory_key": row["memory_key"],
            "source": row["source"],
            "confidence": row["confidence"],
            "evidence_count": row["evidence_count"],
            "freshness": row["freshness"],
            "is_conflicting": bool(row["is_conflicting"]),
            "last_verified": row["last_verified"],
        }
    except Exception:
        return None


def check_conflicts() -> list[dict[str, Any]]:
    """检测记忆冲突（同一类型下互相矛盾的记忆）。"""
    conflicts = []
    try:
        from memory_store.sqlite_db import get_conn

        conn = get_conn()
        try:
            # 查找同一 memory_type 下 memory_key 相似但 confidence 差异大的记录
            rows = conn.execute(
                """SELECT * FROM metamemory
                   WHERE is_conflicting = 1
                   ORDER BY update_time DESC LIMIT 20"""
            ).fetchall()

            for row in rows:
                conflicts.append({
                    "memory_type": row["memory_type"],
                    "memory_key": row["memory_key"],
                    "confidence": row["confidence"],
                    "conflict_with": row["conflict_with"],
                    "freshness": row["freshness"],
                })
        finally:
            conn.close()
    except Exception:
        pass

    return conflicts


def mark_conflict(memory_type: str, memory_key: str, conflict_with: str) -> None:
    """标记记忆冲突。"""
    try:
        from memory_store.sqlite_db import get_conn

        conn = get_conn()
        try:
            conn.execute(
                """UPDATE metamemory SET
                    is_conflicting = 1, conflict_with = ?, update_time = ?
                   WHERE memory_type = ? AND memory_key = ?""",
                (conflict_with, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 memory_type, memory_key),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


def get_system_health() -> dict[str, Any]:
    """获取记忆系统健康状态（整体概览）。"""
    try:
        from memory_store.sqlite_db import get_conn

        conn = get_conn()
        try:
            # 各类型记忆数量
            type_counts = {}
            for mtype in ["episodic", "preference", "procedural", "semantic", "prospective"]:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM metamemory WHERE memory_type = ?",
                    (mtype,),
                ).fetchone()
                type_counts[mtype] = row["cnt"] if row else 0

            # 新鲜度分布
            freshness_counts = {}
            for fresh in ["fresh", "stale", "expired"]:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM metamemory WHERE freshness = ?",
                    (fresh,),
                ).fetchone()
                freshness_counts[fresh] = row["cnt"] if row else 0

            # 冲突数量
            conflict_row = conn.execute(
                "SELECT COUNT(*) as cnt FROM metamemory WHERE is_conflicting = 1"
            ).fetchone()
            conflict_count = conflict_row["cnt"] if conflict_row else 0

            # 平均置信度
            avg_row = conn.execute(
                "SELECT AVG(confidence) as avg_conf FROM metamemory"
            ).fetchone()
            avg_confidence = round(avg_row["avg_conf"], 3) if avg_row and avg_row["avg_conf"] else 0

            # 总记忆数
            total = sum(type_counts.values())

            # 健康评分（0-100）
            health_score = _calc_health_score(type_counts, freshness_counts, conflict_count, avg_confidence)

            return {
                "total_memories": total,
                "type_distribution": type_counts,
                "freshness_distribution": freshness_counts,
                "conflict_count": conflict_count,
                "avg_confidence": avg_confidence,
                "health_score": health_score,
                "status": "healthy" if health_score >= 70 else "needs_attention",
                "checked_at": datetime.now().isoformat(),
            }
        finally:
            conn.close()
    except Exception as e:
        logger.debug("系统健康检查失败: %s", e)
        return {"error": str(e)[:100]}


def _calc_health_score(type_counts: dict, freshness_counts: dict,
                       conflict_count: int, avg_confidence: float) -> int:
    """计算记忆系统健康评分。"""
    score = 50  # 基础分

    # 新鲜度加分
    fresh = freshness_counts.get("fresh", 0)
    stale = freshness_counts.get("stale", 0)
    expired = freshness_counts.get("expired", 0)
    total = fresh + stale + expired
    if total > 0:
        freshness_ratio = fresh / total
        score += int(freshness_ratio * 25)

    # 置信度加分
    score += int(avg_confidence * 15)

    # 冲突扣分
    score -= min(conflict_count * 3, 15)

    # 多样性加分（类型覆盖）
    non_empty_types = sum(1 for v in type_counts.values() if v > 0)
    score += non_empty_types * 2

    return max(0, min(100, score))


def cleanup_expired_metamemory(max_age_days: int = 90) -> int:
    """清理过期的元记忆记录（防止表无限增长）。"""
    try:
        from memory_store.sqlite_db import get_conn
        cutoff = (datetime.now() - timedelta(days=max_age_days)).strftime("%Y-%m-%d %H:%M:%S")
        conn = get_conn()
        try:
            result = conn.execute(
                "DELETE FROM metamemory WHERE update_time < ?",
                (cutoff,),
            )
            conn.commit()
            cleaned = result.rowcount
            if cleaned > 0:
                logger.info("清理 %d 条过期元记忆", cleaned)
            return cleaned
        finally:
            conn.close()
    except Exception:
        return 0


def sync_metamemory() -> dict[str, Any]:
    """同步元记忆（从实际记忆表同步状态到 metamemory）。

    在巩固周期中调用，确保元记忆与实际记忆一致。
    """
    synced = 0
    try:
        from memory_store.sqlite_db import get_conn

        conn = get_conn()
        try:
            # 同步 user_preference → metamemory
            pref_rows = conn.execute("SELECT * FROM user_preference").fetchall()
            for row in pref_rows:
                track_memory(
                    memory_type="preference",
                    memory_key=row["pref_key"],
                    source="user_feedback",
                    confidence=row["confidence"],
                    evidence_count=row["evidence_count"],
                    metadata={"last_evidence": row["last_evidence"][:100]},
                )
                synced += 1

            # 同步 custom_template → metamemory
            tpl_rows = conn.execute("SELECT * FROM custom_template").fetchall()
            for row in tpl_rows:
                try:
                    flow = json.loads(row["task_flow_json"]) if row["task_flow_json"] else {}
                    track_memory(
                        memory_type="procedural",
                        memory_key=row["name"],
                        source="consolidation",
                        confidence=min(0.5 + flow.get("freq_count", 0) * 0.1, 0.95),
                        evidence_count=flow.get("freq_count", 0),
                        metadata={"avg_score": flow.get("avg_score", 0)},
                    )
                    synced += 1
                except (json.JSONDecodeError, TypeError):
                    continue

            # 同步 prospective_memory → metamemory
            pro_rows = conn.execute(
                "SELECT * FROM prospective_memory WHERE status = 'pending'"
            ).fetchall()
            for row in pro_rows:
                track_memory(
                    memory_type="prospective",
                    memory_key=str(row["id"]),
                    source="user_intent",
                    confidence=0.8 if row["priority"] >= 1 else 0.5,
                    evidence_count=1,
                    metadata={"trigger_type": row["trigger_type"]},
                )
                synced += 1

        finally:
            conn.close()

        logger.info("元记忆同步完成: %d 条记忆已同步", synced)
        return {"synced": synced}
    except Exception as e:
        logger.debug("元记忆同步失败: %s", e)
        return {"synced": 0, "error": str(e)[:100]}


def get_memory_with_reliability(memory_type: str = "", limit: int = 20) -> list[dict[str, Any]]:
    """获取记忆及其可靠性信息（供前端展示）。"""
    try:
        from memory_store.sqlite_db import get_conn

        conn = get_conn()
        try:
            if memory_type:
                rows = conn.execute(
                    """SELECT * FROM metamemory WHERE memory_type = ?
                       ORDER BY confidence DESC, update_time DESC LIMIT ?""",
                    (memory_type, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM metamemory
                       ORDER BY confidence DESC, update_time DESC LIMIT ?""",
                    (limit,),
                ).fetchall()

            result = []
            for row in rows:
                result.append({
                    "memory_type": row["memory_type"],
                    "memory_key": row["memory_key"],
                    "source": row["source"],
                    "confidence": row["confidence"],
                    "evidence_count": row["evidence_count"],
                    "freshness": row["freshness"],
                    "is_conflicting": bool(row["is_conflicting"]),
                    "last_verified": row["last_verified"],
                    "update_time": row["update_time"],
                })
            return result
        finally:
            conn.close()
    except Exception:
        return []
