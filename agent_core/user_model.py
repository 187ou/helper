"""用户模型：理解用户的"全貌"。

解决缺口：当前只知道用户的偏好（简洁/详细），不知道用户的"全貌"。

核心能力：
1. 能力评估：用户的任务执行能力水平
2. 节奏感知：用户的工作节奏和习惯
3. 偏好演化：用户偏好的变化趋势
4. 痛点识别：用户反复遇到的问题
5. 目标推断：用户当前的工作重点
6. 个性化适配：基于用户模型调整系统行为
"""
import json
import logging
from collections import Counter
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


def build_user_model() -> dict[str, Any]:
    """构建完整的用户模型（综合分析）。

    Returns:
        用户模型，包含能力/节奏/偏好/痛点/目标
    """
    model = {
        "updated_at": datetime.now().isoformat(),
    }

    # 1. 能力评估
    model["capability"] = _assess_capability()

    # 2. 工作节奏
    model["rhythm"] = _analyze_rhythm()

    # 3. 偏好画像
    model["preference_profile"] = _build_preference_profile()

    # 4. 痛点识别
    model["pain_points"] = _identify_pain_points()

    # 5. 当前重点
    model["current_focus"] = _infer_current_focus()

    # 6. 个性化建议
    model["personalization"] = _generate_personalization(model)

    # 存储
    _store_user_model(model)

    return model


# ── 1. 能力评估 ──

def _assess_capability() -> dict:
    """评估用户的任务执行能力水平。"""
    try:
        from memory_store.sqlite_db import get_conn

        conn = get_conn()
        try:
            # 最近 30 天的任务
            since = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
            rows = conn.execute(
                """SELECT work_score, cost_time, status, task_steps
                   FROM task_list WHERE create_time >= ?""",
                (since,),
            ).fetchall()

            if not rows:
                return {"level": "unknown", "description": "数据不足，无法评估"}

            # 成功率
            success = sum(1 for r in rows if r["status"] in ("done", "success"))
            success_rate = success / len(rows)

            # 平均分数
            scores = [r["work_score"] for r in rows if r["work_score"] and r["work_score"] > 0]
            avg_score = sum(scores) / len(scores) if scores else 0

            # 平均耗时
            times = [r["cost_time"] for r in rows if r["cost_time"] and r["cost_time"] > 0]
            avg_time = sum(times) / len(times) if times else 0

            # 综合评级
            if success_rate >= 0.9 and avg_score >= 80:
                level = "excellent"
                description = "执行力强，任务完成质量高"
            elif success_rate >= 0.7 and avg_score >= 60:
                level = "proficient"
                description = "能力良好，大部分任务能顺利完成"
            elif success_rate >= 0.5:
                level = "developing"
                description = "正在成长，部分任务需要改进"
            else:
                level = "beginner"
                description = "需要更多练习，建议从简单任务开始"

            # 能力维度
            dimensions = {
                "completion": round(success_rate * 100, 1),  # 完成能力
                "quality": round(avg_score, 1),              # 质量能力
                "efficiency": max(0, 100 - avg_time / 2),    # 效率（越快越高）
            }

            return {
                "level": level,
                "description": description,
                "dimensions": dimensions,
                "stats": {
                    "total_tasks": len(rows),
                    "success_rate": round(success_rate * 100, 1),
                    "avg_score": round(avg_score, 1),
                    "avg_time": round(avg_time, 1),
                },
            }
        finally:
            conn.close()
    except Exception:
        return {"level": "unknown", "description": "评估失败"}


# ── 2. 工作节奏 ──

def _analyze_rhythm() -> dict:
    """分析用户的工作节奏和习惯。"""
    try:
        from memory_store.sqlite_db import get_conn

        conn = get_conn()
        try:
            since = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
            rows = conn.execute(
                """SELECT create_time, strftime('%H', create_time) as hour,
                          strftime('%w', create_time) as weekday
                   FROM task_list WHERE create_time >= ?""",
                (since,),
            ).fetchall()

            if not rows:
                return {"description": "数据不足"}

            # 小时分布
            hour_counts = Counter(r["hour"] for r in rows)
            peak_hours = hour_counts.most_common(3)

            # 星期分布
            weekday_counts = Counter(r["weekday"] for r in rows)
            # 0=周日, 1=周一, ..., 6=周六
            weekday_names = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"]
            peak_days = [(weekday_names[int(d)], c) for d, c in weekday_counts.most_common(3)]

            # 计算节奏类型
            total = len(rows)
            days_active = len(set(r["create_time"][:10] for r in rows))

            if days_active >= 20:
                rhythm_type = "daily_user"
                rhythm_desc = "几乎每天都在使用，是高活跃用户"
            elif days_active >= 10:
                rhythm_type = "regular_user"
                rhythm_desc = "定期使用，有稳定的工作习惯"
            elif days_active >= 5:
                rhythm_type = "casual_user"
                rhythm_desc = "偶尔使用，没有固定规律"
            else:
                rhythm_type = "new_user"
                rhythm_desc = "刚开始使用，还在熟悉中"

            return {
                "rhythm_type": rhythm_type,
                "description": rhythm_desc,
                "peak_hours": [f"{h}时({c}次)" for h, c in peak_hours],
                "peak_days": [f"{d}({c}次)" for d, c in peak_days],
                "active_days": days_active,
                "total_tasks": total,
            }
        finally:
            conn.close()
    except Exception:
        return {"description": "分析失败"}


# ── 3. 偏好画像 ──

def _build_preference_profile() -> dict:
    """构建用户的偏好画像（含演化趋势）。"""
    try:
        from memory_store.sqlite_db import get_conn

        conn = get_conn()
        try:
            rows = conn.execute(
                "SELECT pref_key, pref_value, confidence, evidence_count, update_time "
                "FROM user_preference WHERE confidence >= 0.3 "
                "ORDER BY confidence DESC LIMIT 20"
            ).fetchall()

            if not rows:
                return {"description": "暂无足够偏好数据"}

            # 分类偏好
            style_prefs = []
            format_prefs = []
            tone_prefs = []
            other_prefs = []

            for r in rows:
                key = r["pref_key"]
                val = r["pref_value"]
                conf = r["confidence"]

                pref_item = {"key": key, "value": val, "confidence": conf}

                if "style" in key or "length" in key:
                    style_prefs.append(pref_item)
                elif "format" in key:
                    format_prefs.append(pref_item)
                elif "tone" in key:
                    tone_prefs.append(pref_item)
                else:
                    other_prefs.append(pref_item)

            # 偏好稳定性（证据数越多越稳定）
            avg_evidence = sum(r["evidence_count"] for r in rows) / len(rows)
            stability = "stable" if avg_evidence >= 5 else "evolving" if avg_evidence >= 2 else "initial"

            return {
                "stability": stability,
                "top_style_preferences": style_prefs[:3],
                "top_format_preferences": format_prefs[:2],
                "top_tone_preferences": tone_prefs[:2],
                "other_preferences": other_prefs[:3],
                "total_preferences": len(rows),
            }
        finally:
            conn.close()
    except Exception:
        return {"description": "构建失败"}


# ── 4. 痛点识别 ──

def _identify_pain_points() -> list[dict]:
    """识别用户反复遇到的问题（痛点）。"""
    pain_points = []
    try:
        from memory_store.sqlite_db import get_conn

        conn = get_conn()
        try:
            since = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")

            # 痛点 1：反复失败的步骤
            failed_steps = conn.execute(
                """SELECT task_steps FROM task_list
                   WHERE create_time >= ? AND status = 'failed'
                   AND task_steps IS NOT NULL""",
                (since,),
            ).fetchall()

            step_failures = Counter()
            for row in failed_steps:
                try:
                    steps = json.loads(row["task_steps"]) if row["task_steps"] else []
                    for s in steps:
                        if s.get("status") == "failed":
                            step_failures[s.get("name", "未知")] += 1
                except (json.JSONDecodeError, TypeError):
                    continue

            for step, count in step_failures.most_common(3):
                if count >= 2:
                    pain_points.append({
                        "type": "repeated_failure",
                        "target": step,
                        "frequency": count,
                        "suggestion": f"「{step}」步骤多次失败，建议优化或跳过",
                    })

            # 痛点 2：反复修改的内容
            feedback_rows = conn.execute(
                """SELECT diff_summary, COUNT(*) as cnt
                   FROM user_feedback
                   WHERE create_time >= ? AND feedback_type = 'modify'
                   AND diff_summary != ''
                   GROUP BY diff_summary ORDER BY cnt DESC LIMIT 5""",
                (since,),
            ).fetchall()

            for row in feedback_rows:
                if row["cnt"] >= 2:
                    pain_points.append({
                        "type": "frequent_modification",
                        "target": row["diff_summary"],
                        "frequency": row["cnt"],
                        "suggestion": f"用户频繁进行「{row['diff_summary']}」修改，建议调整默认输出",
                    })

            # 痛点 3：耗时异常的任务
            slow_tasks = conn.execute(
                """SELECT task_content, cost_time FROM task_list
                   WHERE create_time >= ? AND cost_time > 180
                   ORDER BY cost_time DESC LIMIT 5""",
                (since,),
            ).fetchall()

            for row in slow_tasks:
                pain_points.append({
                    "type": "slow_execution",
                    "target": row["task_content"][:50],
                    "cost_time": row["cost_time"],
                    "suggestion": f"任务耗时 {row['cost_time']:.0f} 秒，建议优化流程",
                })

        finally:
            conn.close()
    except Exception:
        pass

    return pain_points[:5]


# ── 5. 当前重点推断 ──

def _infer_current_focus() -> dict:
    """推断用户当前的工作重点。"""
    try:
        from memory_store.sqlite_db import get_conn

        conn = get_conn()
        try:
            # 最近一周的任务类型分布
            since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
            rows = conn.execute(
                """SELECT task_content, task_type, COUNT(*) as cnt
                   FROM task_list WHERE create_time >= ?
                   GROUP BY task_type ORDER BY cnt DESC LIMIT 5""",
                (since,),
            ).fetchall()

            if not rows:
                return {"description": "数据不足"}

            # 最多任务类型
            top_type = rows[0]["task_type"] if rows else "unknown"
            top_count = rows[0]["cnt"] if rows else 0

            # 提取高频关键词
            content_rows = conn.execute(
                "SELECT task_content FROM task_list WHERE create_time >= ? LIMIT 20",
                (since,),
            ).fetchall()

            all_text = " ".join(r["task_content"] or "" for r in content_rows)
            # 简单关键词提取（2-4 字中文词组）
            import re
            words = re.findall(r'[一-鿿]{2,4}', all_text)
            word_counts = Counter(words)
            # 过滤常见词
            stopwords = {"任务", "完成", "进行", "使用", "需要", "可以", "已经", "开始"}
            keywords = [(w, c) for w, c in word_counts.most_common(10) if w not in stopwords and c >= 2]

            return {
                "primary_type": top_type,
                "primary_count": top_count,
                "keywords": [w for w, _ in keywords[:5]],
                "description": f"近期主要集中在「{top_type}」类任务" +
                               (f"，涉及：{', '.join(w for w, _ in keywords[:3])}" if keywords else ""),
            }
        finally:
            conn.close()
    except Exception:
        return {"description": "推断失败"}


# ── 6. 个性化建议 ──

def _generate_personalization(model: dict) -> dict:
    """基于用户模型生成个性化适配建议。"""
    personalization = {}

    # 基于能力水平
    capability = model.get("capability", {})
    level = capability.get("level", "")
    if level == "beginner":
        personalization["complexity"] = "建议从简单任务开始，逐步增加复杂度"
        personalization["guidance"] = "提供更详细的步骤指导"
    elif level == "developing":
        personalization["complexity"] = "可以尝试中等复杂度任务"
        personalization["guidance"] = "在关键步骤给出提示"
    elif level in ("proficient", "excellent"):
        personalization["complexity"] = "可以处理复杂任务"
        personalization["guidance"] = "减少不必要的指导，提高效率"

    # 基于工作节奏
    rhythm = model.get("rhythm", {})
    if rhythm.get("rhythm_type") == "daily_user":
        personalization["proactivity"] = "可以主动推送相关提醒和建议"
    elif rhythm.get("rhythm_type") == "new_user":
        personalization["proactivity"] = "减少主动推送，避免打扰"

    # 基于痛点
    pain_points = model.get("pain_points", [])
    if pain_points:
        top_pain = pain_points[0]
        personalization["priority_fix"] = top_pain.get("suggestion", "")

    return personalization


# ── 存储 ──

def _store_user_model(model: dict) -> None:
    """存储用户模型。"""
    try:
        from memory_store.sqlite_db import get_conn
        conn = get_conn()
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            latest_key = "user_model:latest"

            existing = conn.execute(
                "SELECT pref_key FROM user_preference WHERE pref_key = ?", (latest_key,)
            ).fetchone()

            if existing:
                conn.execute(
                    "UPDATE user_preference SET pref_value = ?, update_time = ? WHERE pref_key = ?",
                    (json.dumps(model, ensure_ascii=False, default=str),
                     datetime.now().strftime("%Y-%m-%d %H:%M:%S"), latest_key),
                )
            else:
                conn.execute(
                    """INSERT INTO user_preference
                       (pref_key, pref_value, confidence, evidence_count, last_evidence)
                       VALUES (?, ?, 0.9, 1, ?)""",
                    (latest_key, json.dumps(model, ensure_ascii=False, default=str),
                     f"用户模型 {today}"),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.debug("用户模型存储失败: %s", e)


def get_user_model() -> dict:
    """获取最新用户模型。"""
    try:
        from memory_store.sqlite_db import get_conn
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT pref_value FROM user_preference WHERE pref_key = ?",
                ("user_model:latest",),
            ).fetchone()
            return json.loads(row["pref_value"]) if row else {}
        finally:
            conn.close()
    except Exception:
        return {}


def get_personalized_guidance(task_type: str = "") -> str:
    """获取个性化指导（注入 prompt 用）。

    基于用户模型生成针对性的执行建议。
    """
    model = get_user_model()
    if not model:
        return ""

    parts = []

    # 能力适配
    capability = model.get("capability", {})
    if capability.get("level") == "beginner":
        parts.append("用户是新手，请提供详细指导和鼓励")
    elif capability.get("level") == "excellent":
        parts.append("用户经验丰富，可以简洁高效地执行")

    # 偏好适配
    pref_profile = model.get("preference_profile", {})
    style_prefs = pref_profile.get("top_style_preferences", [])
    if style_prefs:
        top_style = style_prefs[0].get("value", "")
        if top_style:
            parts.append(f"用户偏好：{top_style}")

    # 痛点规避
    pain_points = model.get("pain_points", [])
    if pain_points:
        top_pain = pain_points[0]
        if top_pain.get("type") == "repeated_failure":
            parts.append(f"注意：「{top_pain['target']}」步骤容易出错，请特别关注")

    return "\n".join(parts) if parts else ""
