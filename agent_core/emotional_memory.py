"""情感记忆：感知用户情绪。

解决缺口：当前系统不知道用户的情绪状态，无法感知"用户对这件事感到厌烦/焦虑/满意"。

核心能力：
1. 情绪检测：从用户输入/反馈中识别情绪
2. 情绪追踪：记录用户情绪变化趋势
3. 情绪关联：将情绪与具体任务/事件关联
4. 情绪适配：根据情绪调整系统响应方式
5. 情绪预警：检测负面情绪累积并预警
"""
import json
import logging
from collections import Counter
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# ── 情绪词典 ──
EMOTION_KEYWORDS = {
    "positive": {
        "满意": 0.8, "很好": 0.9, "不错": 0.7, "棒": 0.9, "完美": 1.0,
        "喜欢": 0.8, "感谢": 0.7, "谢谢": 0.7, "好用": 0.8, "方便": 0.7,
        "赞": 0.9, "优秀": 0.9, "清晰": 0.6, "简洁": 0.6, "快速": 0.6,
        "好用": 0.8, "行": 0.5, "可以": 0.5, "还行": 0.6,
        "good": 0.7, "great": 0.8, "excellent": 0.9, "perfect": 1.0, "thanks": 0.7,
    },
    "negative": {
        "烦": -0.7, "差": -0.8, "慢": -0.5, "难用": -0.8, "复杂": -0.5,
        "错误": -0.7, "失败": -0.8, "不行": -0.7, "糟糕": -0.9, "垃圾": -1.0,
        "重来": -0.6, "又错了": -0.8, "浪费时间": -0.9, "受不了": -0.9,
        "bad": -0.7, "terrible": -0.9, "awful": -0.9, "slow": -0.5, "error": -0.7,
    },
    "anxious": {
        "急": -0.6, "赶紧": -0.5, "来不及": -0.7, " deadline": -0.6, "截止": -0.5,
        "担心": -0.5, "焦虑": -0.7, "紧张": -0.5, "快点": -0.4,
        "urgent": -0.6, "asap": -0.5, "hurry": -0.5,
    },
    "bored": {
        "又来了": -0.4, "老是": -0.5, "天天": -0.4, "每次": -0.3, "重复": -0.3,
        "无聊": -0.5, "麻木": -0.4, "习惯": -0.2,
    },
}

EMOTION_LABELS = {
    "positive": "积极",
    "negative": "消极",
    "anxious": "焦虑",
    "bored": "厌烦",
    "neutral": "中性",
}


def detect_emotion(text: str) -> dict[str, Any]:
    """从文本中检测情绪（关键词 + 语义增强）。

    升级：除了关键词匹配外，还包含：
    1. 否定词检测（"不好" → 消极）
    2. 程度副词（"非常"/"有点" → 调整强度）
    3. 标点符号（"！" → 增强，"..." → 减弱）
    4. 感叹词（"唉"/"哇"/"哼" → 情绪信号）

    Args:
        text: 用户输入文本

    Returns:
        情绪分析结果 {emotion, intensity, confidence, keywords}
    """
    if not text:
        return {"emotion": "neutral", "intensity": 0, "confidence": 0, "keywords": []}

    text_lower = text.lower()
    detected = []
    total_score = 0

    # ── 1. 关键词匹配 ──
    for emotion, keywords in EMOTION_KEYWORDS.items():
        for keyword, score in keywords.items():
            if keyword in text_lower:
                detected.append({"keyword": keyword, "emotion": emotion, "score": score})
                total_score += score

    # ── 2. 否定词检测（翻转情绪）──
    NEGATION_WORDS = ["不", "没", "没有", "别", "不是", "不要", "别"]
    has_negation = any(neg in text_lower for neg in NEGATION_WORDS)

    # ── 3. 程度副词（调整强度）──
    INTENSIFIERS = {"非常": 1.5, "特别": 1.4, "极其": 1.6, "超级": 1.5, "太": 1.3,
                    "真": 1.2, "好": 1.2, "很": 1.1, "有点": 0.7, "稍微": 0.6, "略": 0.5}
    intensity_multiplier = 1.0
    for word, mult in INTENSIFIERS.items():
        if word in text_lower:
            intensity_multiplier = max(intensity_multiplier, mult)

    # ── 4. 标点符号分析 ──
    if "！" in text or "!" in text:
        intensity_multiplier *= 1.2
    elif "..." in text or "。。。" in text:
        intensity_multiplier *= 0.8

    # ── 5. 感叹词检测 ──
    EXCLAMATIONS = {
        "唉": ("negative", -0.5), "哎": ("negative", -0.4), "哼": ("negative", -0.6),
        "哇": ("positive", 0.7), "哇塞": ("positive", 0.8), "耶": ("positive", 0.7),
        "哈哈": ("positive", 0.6), "呵呵": ("bored", -0.3),
        "天哪": ("anxious", -0.5), "完了": ("anxious", -0.7), "糟糕": ("negative", -0.8),
        "无语": ("negative", -0.6), "崩溃": ("negative", -0.9), "崩溃了": ("negative", -0.9),
        "垃圾": ("negative", -0.9), "废物": ("negative", -0.9), "烂": ("negative", -0.7),
    }
    for excl, (emotion, score) in EXCLAMATIONS.items():
        if excl in text_lower:
            detected.append({"keyword": excl, "emotion": emotion, "score": score * intensity_multiplier})
            total_score += score * intensity_multiplier

    if not detected:
        return {"emotion": "neutral", "intensity": 0, "confidence": 0.3, "keywords": []}

    # 否定词翻转（"不好" → 消极，"不错" → 可能仍是积极）
    if has_negation:
        for d in detected:
            if d["emotion"] == "positive" and d["score"] > 0:
                keyword = d["keyword"]
                # "不错"/"还行"/"可以"是固定表达，不翻转
                if keyword in ("不错", "还行", "可以"):
                    continue
                # 翻转：积极 → 消极，分数取反
                d["emotion"] = "negative"
                d["score"] *= -0.6
        # 重新计算总分
        total_score = sum(d["score"] for d in detected)

    # 确定主导情绪
    emotion_scores = Counter()
    for d in detected:
        emotion_scores[d["emotion"]] += abs(d["score"])

    dominant_emotion = emotion_scores.most_common(1)[0][0]
    avg_score = (total_score / len(detected)) * intensity_multiplier
    confidence = min(len(detected) * 0.25 + 0.2, 0.95)

    return {
        "emotion": dominant_emotion,
        "emotion_label": EMOTION_LABELS.get(dominant_emotion, dominant_emotion),
        "intensity": round(min(abs(avg_score), 1.0), 2),
        "direction": "positive" if avg_score > 0 else "negative",
        "confidence": round(confidence, 2),
        "keywords": [d["keyword"] for d in detected],
    }


def record_emotion(task_id: int, text: str, source: str = "user_input") -> dict | None:
    """记录用户情绪（任务执行中/反馈时调用）。

    Args:
        task_id: 关联任务 ID
        text: 用户输入文本
        source: 来源 (user_input / feedback / system_detected)

    Returns:
        情绪记录，无情绪时返回 None
    """
    emotion = detect_emotion(text)
    if emotion["emotion"] == "neutral":
        return None

    try:
        from memory_store.sqlite_db import get_conn

        conn = get_conn()
        try:
            conn.execute(
                """INSERT INTO emotional_memory
                   (task_id, emotion, emotion_label, intensity, direction,
                    confidence, keywords, source, create_time)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (task_id, emotion["emotion"], emotion["emotion_label"],
                 emotion["intensity"], emotion["direction"],
                 emotion["confidence"],
                 json.dumps(emotion["keywords"], ensure_ascii=False),
                 source, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            conn.commit()
        finally:
            conn.close()

        logger.debug("情绪记录: task #%d → %s (%.2f)", task_id, emotion["emotion"], emotion["intensity"])
    except Exception as e:
        logger.debug("情绪记录失败: %s", e)

    return emotion


def get_emotion_trend(days: int = 7) -> dict[str, Any]:
    """获取用户情绪变化趋势。"""
    try:
        from memory_store.sqlite_db import get_conn

        conn = get_conn()
        try:
            since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
            rows = conn.execute(
                """SELECT emotion, intensity, direction, create_time
                   FROM emotional_memory
                   WHERE create_time >= ?
                   ORDER BY create_time""",
                (since,),
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            return {"description": "近期无情绪数据", "trend": "neutral"}

        # 统计各情绪占比
        emotion_counts = Counter(r["emotion"] for r in rows)
        dominant = emotion_counts.most_common(1)[0]

        # 计算平均强度
        avg_intensity = sum(r["intensity"] for r in rows) / len(rows)

        # 趋势（前后对比）
        mid = len(rows) // 2
        if mid > 0:
            first_half = [r["intensity"] if r["direction"] == "positive" else -r["intensity"]
                          for r in rows[:mid]]
            second_half = [r["intensity"] if r["direction"] == "positive" else -r["intensity"]
                           for r in rows[mid:]]
            first_avg = sum(first_half) / len(first_half)
            second_avg = sum(second_half) / len(second_half)

            if second_avg > first_avg + 0.2:
                trend = "improving"
                trend_desc = "情绪状态在改善"
            elif second_avg < first_avg - 0.2:
                trend = "declining"
                trend_desc = "情绪状态有所下降，建议关注"
            else:
                trend = "stable"
                trend_desc = "情绪状态稳定"
        else:
            trend = "stable"
            trend_desc = "数据不足"

        return {
            "dominant_emotion": dominant[0],
            "dominant_label": EMOTION_LABELS.get(dominant[0], dominant[0]),
            "emotion_distribution": dict(emotion_counts),
            "avg_intensity": round(avg_intensity, 2),
            "total_records": len(rows),
            "trend": trend,
            "trend_description": trend_desc,
        }
    except Exception:
        return {"description": "分析失败"}


def check_emotion_alert() -> str | None:
    """检查是否需要情绪预警（负面情绪累积）。"""
    try:
        trend = get_emotion_trend(days=3)
        if trend.get("dominant_emotion") in ("negative", "anxious") and trend.get("avg_intensity", 0) > 0.6:
            return f"负面情绪累积预警：用户近期主要情绪为「{trend['dominant_label']}」，建议减少任务复杂度或提供鼓励"
        return None
    except Exception:
        return None


def get_emotional_guidance() -> str:
    """获取基于情绪的系统响应建议（注入 prompt）。"""
    try:
        trend = get_emotion_trend(days=3)
        emotion = trend.get("dominant_emotion", "neutral")
        intensity = trend.get("avg_intensity", 0)

        if emotion == "negative" and intensity > 0.5:
            return "用户近期情绪偏负面，请简化输出、减少步骤，并提供鼓励"
        elif emotion == "anxious":
            return "用户可能感到焦虑，请给出明确的时间预期和步骤指导"
        elif emotion == "bored":
            return "用户可能感到重复乏味，尝试提供新的角度或简化流程"
        elif emotion == "positive":
            return "用户情绪积极，可以适当增加任务复杂度或提供进阶功能"
        return ""
    except Exception:
        return ""
