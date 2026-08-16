"""长期叙事：讲述"用户的故事"。

解决缺口：当前记忆是碎片化的，没有"用户是谁、在做什么、目标是什么"的连贯叙事。

核心能力：
1. 用户故事：生成用户的工作/生活叙事
2. 里程碑追踪：记录重要成就和转折点
3. 成长轨迹：展示用户能力变化曲线
4. 主题聚合：发现用户关注的核心主题
5. 时间线：按时间顺序展示重要事件
"""
import json
import logging
from collections import Counter
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


def generate_life_narrative(period: str = "monthly") -> dict[str, Any]:
    """生成用户的"故事"——连贯的叙事报告。

    Args:
        period: "weekly" / "monthly" / "all"

    Returns:
        叙事报告，包含故事线、里程碑、成长、主题
    """
    days = {"weekly": 7, "monthly": 30, "all": 365}.get(period, 30)
    since = datetime.now() - timedelta(days=days)

    narrative = {
        "period": period,
        "generated_at": datetime.now().isoformat(),
    }

    # 1. 故事线（按时间顺序的重要事件）
    narrative["timeline"] = _build_timeline(since)

    # 2. 里程碑（重要成就和转折点）
    narrative["milestones"] = _detect_milestones(since)

    # 3. 成长轨迹（能力变化）
    narrative["growth"] = _track_growth(since)

    # 4. 核心主题（最关注的事情）
    narrative["themes"] = _extract_themes(since)

    # 5. 叙事摘要（一句话故事）
    narrative["summary"] = _generate_narrative_summary(narrative)

    # 存储
    _store_narrative(narrative)

    return narrative


def _build_timeline(since: datetime) -> list[dict]:
    """构建时间线（按时间顺序的重要事件）。"""
    try:
        from memory_store.sqlite_db import get_conn

        conn = get_conn()
        try:
            rows = conn.execute(
                """SELECT task_content, work_score, life_score, status, create_time, task_type
                   FROM task_list
                   WHERE create_time >= ?
                   ORDER BY create_time DESC LIMIT 30""",
                (since.strftime("%Y-%m-%d %H:%M:%S"),),
            ).fetchall()
        finally:
            conn.close()

        timeline = []
        for r in rows:
            score = max(r["work_score"] or 0, r["life_score"] or 0)
            event = {
                "date": r["create_time"][:10],
                "time": r["create_time"][11:16],
                "content": r["task_content"][:60],
                "type": r["task_type"],
                "score": score,
                "status": r["status"],
            }

            # 标记重要事件
            if score >= 90:
                event["importance"] = "high"
                event["badge"] = "高分"
            elif r["status"] == "failed":
                event["importance"] = "medium"
                event["badge"] = "失败"
            else:
                event["importance"] = "normal"

            timeline.append(event)

        return timeline
    except Exception:
        return []


def _detect_milestones(since: datetime) -> list[dict]:
    """检测重要里程碑（成就和转折点）。"""
    milestones = []
    try:
        from memory_store.sqlite_db import get_conn

        conn = get_conn()
        try:
            # 里程碑 1：首次完成任务
            first_success = conn.execute(
                """SELECT task_content, create_time FROM task_list
                   WHERE status IN ('done', 'success')
                   ORDER BY create_time ASC LIMIT 1"""
            ).fetchone()

            if first_success:
                milestones.append({
                    "type": "first_success",
                    "title": "首次成功",
                    "description": f"第一次完成了「{first_success['task_content'][:40]}」",
                    "date": first_success["create_time"][:10],
                    "icon": "🎉",
                })

            # 里程碑 2：最高分任务
            best_task = conn.execute(
                """SELECT task_content, work_score, create_time FROM task_list
                   WHERE work_score > 0
                   ORDER BY work_score DESC LIMIT 1"""
            ).fetchone()

            if best_task and best_task["work_score"] >= 80:
                milestones.append({
                    "type": "best_score",
                    "title": "最佳表现",
                    "description": f"「{best_task['task_content'][:40]}」获得 {best_task['work_score']:.0f} 分",
                    "date": best_task["create_time"][:10],
                    "icon": "⭐",
                })

            # 里程碑 3：任务总量突破
            total = conn.execute(
                "SELECT COUNT(*) as cnt FROM task_list WHERE create_time >= ?",
                (since.strftime("%Y-%m-%d %H:%M:%S"),),
            ).fetchone()

            if total and total["cnt"] >= 10:
                milestones.append({
                    "type": "volume_milestone",
                    "title": f"完成 {total['cnt']} 个任务",
                    "description": f"本周期共完成 {total['cnt']} 个任务",
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "icon": "📊",
                })

            # 里程碑 4：连续成功
            recent_success = conn.execute(
                """SELECT COUNT(*) as cnt FROM (
                       SELECT status, create_time,
                              ROW_NUMBER() OVER (ORDER BY create_time DESC) as rn
                       FROM task_list) t
                   WHERE rn <= 5 AND status IN ('done', 'success')"""
            ).fetchone()

            if recent_success and recent_success["cnt"] >= 5:
                milestones.append({
                    "type": "streak",
                    "title": "连续成功",
                    "description": "最近 5 个任务全部成功完成",
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "icon": "🔥",
                })

            # 里程碑 5：偏好稳定
            stable_prefs = conn.execute(
                """SELECT COUNT(*) as cnt FROM user_preference
                   WHERE confidence >= 0.8 AND evidence_count >= 5"""
            ).fetchone()

            if stable_prefs and stable_prefs["cnt"] >= 3:
                milestones.append({
                    "type": "preference_established",
                    "title": "偏好形成",
                    "description": f"已形成 {stable_prefs['cnt']} 个稳定偏好",
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "icon": "💎",
                })

        finally:
            conn.close()
    except Exception:
        pass

    return milestones


def _track_growth(since: datetime) -> dict:
    """追踪用户成长轨迹。"""
    try:
        from memory_store.sqlite_db import get_conn

        conn = get_conn()
        try:
            # 按周统计平均分数
            rows = conn.execute(
                """SELECT strftime('%Y-W%W', create_time) as week,
                          AVG(COALESCE(work_score, 0)) as avg_score,
                          COUNT(*) as cnt
                   FROM task_list
                   WHERE create_time >= ?
                   GROUP BY week
                   ORDER BY week""",
                (since.strftime("%Y-%m-%d %H:%M:%S"),),
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            return {"description": "数据不足"}

        scores = [{"week": r["week"], "score": round(r["avg_score"], 1), "tasks": r["cnt"]}
                   for r in rows if r["avg_score"] > 0]

        if len(scores) < 2:
            return {"description": "需要更多数据", "current": scores[0] if scores else None}

        # 计算成长趋势
        first_score = scores[0]["score"]
        last_score = scores[-1]["score"]
        change = last_score - first_score

        if change > 10:
            trend = "显著提升"
        elif change > 5:
            trend = "稳步提升"
        elif change > -5:
            trend = "保持稳定"
        else:
            trend = "有所下滑"

        return {
            "trend": trend,
            "change": round(change, 1),
            "weekly_scores": scores,
            "peak": max(scores, key=lambda x: x["score"]) if scores else None,
        }
    except Exception:
        return {"description": "分析失败"}


def _extract_themes(since: datetime) -> list[dict]:
    """提取用户关注的核心主题。"""
    try:
        from memory_store.sqlite_db import get_conn

        conn = get_conn()
        try:
            rows = conn.execute(
                "SELECT task_content FROM task_list WHERE create_time >= ? LIMIT 100",
                (since.strftime("%Y-%m-%d %H:%M:%S"),),
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            return []

        # 提取关键词
        import re
        all_text = " ".join(r["task_content"] or "" for r in rows)
        words = re.findall(r'[一-鿿]{2,6}', all_text)
        word_counts = Counter(words)

        # 过滤常见词
        stopwords = {"任务", "完成", "进行", "使用", "需要", "可以", "已经", "开始", "一个", "这个", "那个"}
        themes = []
        for word, count in word_counts.most_common(10):
            if word not in stopwords and count >= 2:
                themes.append({"theme": word, "mentions": count})

        return themes[:5]
    except Exception:
        return []


def _generate_narrative_summary(narrative: dict) -> str:
    """生成一句话叙事摘要。"""
    parts = []

    # 基于成长趋势
    growth = narrative.get("growth", {})
    if growth.get("trend"):
        parts.append(f"近期表现{growth['trend']}")

    # 基于里程碑
    milestones = narrative.get("milestones", [])
    if milestones:
        top = milestones[0]
        parts.append(f"最新成就：{top['title']}")

    # 基于主题
    themes = narrative.get("themes", [])
    if themes:
        theme_names = "、".join(t["theme"] for t in themes[:3])
        parts.append(f"主要关注：{theme_names}")

    return "，".join(parts) if parts else "继续记录你的故事"


def _store_narrative(narrative: dict) -> None:
    """存储叙事报告。"""
    try:
        from memory_store.sqlite_db import get_conn
        conn = get_conn()
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            period = narrative.get("period", "monthly")

            latest_key = f"life_narrative:{period}:latest"
            existing = conn.execute(
                "SELECT pref_key FROM user_preference WHERE pref_key = ?", (latest_key,)
            ).fetchone()

            if existing:
                conn.execute(
                    "UPDATE user_preference SET pref_value = ?, update_time = ? WHERE pref_key = ?",
                    (json.dumps(narrative, ensure_ascii=False, default=str),
                     datetime.now().strftime("%Y-%m-%d %H:%M:%S"), latest_key),
                )
            else:
                conn.execute(
                    """INSERT INTO user_preference
                       (pref_key, pref_value, confidence, evidence_count, last_evidence)
                       VALUES (?, ?, 0.85, 1, ?)""",
                    (latest_key, json.dumps(narrative, ensure_ascii=False, default=str),
                     f"生活叙事 {today}"),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


def get_latest_narrative(period: str = "monthly") -> dict:
    """获取最新叙事报告。"""
    try:
        from memory_store.sqlite_db import get_conn
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT pref_value FROM user_preference WHERE pref_key = ?",
                (f"life_narrative:{period}:latest",),
            ).fetchone()
            return json.loads(row["pref_value"]) if row else {}
        finally:
            conn.close()
    except Exception:
        return {}


def get_story_so_far() -> str:
    """获取"你的故事"摘要（用于前端展示）。"""
    narrative = get_latest_narrative("monthly")
    if not narrative:
        return "还没有足够的故事，继续完成任务来书写你的篇章"

    parts = []

    # 开头
    summary = narrative.get("summary", "")
    if summary:
        parts.append(summary)

    # 里程碑
    milestones = narrative.get("milestones", [])
    if milestones:
        parts.append(f"\n🏆 最近成就：{milestones[0].get('description', '')}")

    # 成长
    growth = narrative.get("growth", {})
    if growth.get("trend"):
        parts.append(f"\n📈 成长趋势：{growth['trend']}")

    # 主题
    themes = narrative.get("themes", [])
    if themes:
        theme_str = "、".join(t["theme"] for t in themes[:3])
        parts.append(f"\n🎯 核心关注：{theme_str}")

    return "\n".join(parts)
