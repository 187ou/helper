"""主动推理：预测用户需求。

解决缺口：当前系统只能被动响应，无法预测"用户可能需要什么"。

核心能力：
1. 需求预测：基于当前上下文预测用户下一步需求
2. 时机判断：在合适的时机主动提供帮助
3. 关联推荐：基于当前任务推荐相关操作
4. 异常检测：发现用户可能需要帮助的信号
5. 智能建议：不等用户问，主动给出建议
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


def predict_next_needs(task_text: str = "", task_type: str = "",
                        step_results: list | None = None) -> list[dict]:
    """预测用户下一步可能需要什么。

    Args:
        task_text: 当前任务文本
        task_type: 任务类型
        step_results: 当前步骤结果

    Returns:
        预测需求列表，按相关度排序
    """
    needs = []

    try:
        # 推理 1：任务链预测（做完 A 通常需要做 B）
        chain_predictions = _predict_task_chain(task_text, task_type)
        needs.extend(chain_predictions)

        # 推理 2：缺失信息预测（当前任务可能需要但缺少的信息）
        missing_predictions = _predict_missing_info(task_text, step_results)
        needs.extend(missing_predictions)

        # 推理 3：历史模式预测（用户通常在什么时候做什么）
        pattern_predictions = _predict_from_patterns()
        needs.extend(pattern_predictions)

        # 推理 4：时间敏感预测（基于当前时间的特殊需求）
        time_predictions = _predict_time_sensitive()
        needs.extend(time_predictions)

        # 去重并排序
        seen = set()
        unique = []
        for need in needs:
            key = need.get("description", "")[:50]
            if key not in seen:
                seen.add(key)
                unique.append(need)

        unique.sort(key=lambda x: x.get("relevance", 0), reverse=True)
        return unique[:5]

    except Exception as e:
        logger.debug("需求预测失败: %s", e)
        return []


def _predict_task_chain(task_text: str, task_type: str) -> list[dict]:
    """基于任务链推理（做完 A 后通常做 B）。"""
    chains = []

    # 常见任务链
    task_chains = {
        "周报": [
            {"action": "生成月度总结", "reason": "周报完成后可能需要汇总月报", "relevance": 0.6},
            {"action": "归档周报文件", "reason": "完成后通常需要归档", "relevance": 0.7},
        ],
        "报销": [
            {"action": "整理报销凭证", "reason": "报销前需要收集票据", "relevance": 0.8},
            {"action": "提交审批", "reason": "整理完成后需要提交", "relevance": 0.7},
        ],
        "会议纪要": [
            {"action": "拆分待办事项", "reason": "纪要通常包含行动项", "relevance": 0.8},
            {"action": "发送给参会人", "reason": "完成后需要分发", "relevance": 0.6},
        ],
        "记账": [
            {"action": "查看月度汇总", "reason": "记账后常需要查看统计", "relevance": 0.5},
        ],
    }

    for key, chain in task_chains.items():
        if key in task_text:
            chains.extend(chain)

    return [{"type": "task_chain", **c} for c in chains]


def _predict_missing_info(task_text: str, step_results: list | None) -> list[dict]:
    """预测当前任务可能缺少的信息。"""
    missing = []

    # 检查任务中是否提到需要数据但没有提供
    data_indicators = {
        "数据": "可能需要从数据库或文件中提取数据",
        "文件": "可能需要上传或指定文件路径",
        "金额": "可能需要输入具体金额",
        "时间": "可能需要指定具体时间",
        "人员": "可能需要指定相关人员",
    }

    for indicator, suggestion in data_indicators.items():
        if indicator in task_text:
            # 检查结果中是否已有该信息
            has_info = False
            if step_results:
                for r in step_results:
                    result_text = r.get("result", "")
                    if indicator in result_text:
                        has_info = True
                        break

            if not has_info:
                missing.append({
                    "type": "missing_info",
                    "description": suggestion,
                    "relevance": 0.7,
                })

    return missing


def _predict_from_patterns() -> list[dict]:
    """基于历史模式预测（用户习惯）。"""
    predictions = []
    try:
        from memory_store.sqlite_db import get_conn

        conn = get_conn()
        try:
            # 获取当前时间信息
            now = datetime.now()
            weekday = now.weekday()  # 0=周一
            hour = now.hour

            # 查询同一时段用户常做的事
            rows = conn.execute(
                """SELECT task_content, COUNT(*) as cnt
                   FROM task_list
                   WHERE strftime('%w', create_time) = ?
                     AND ABS(CAST(strftime('%H', create_time) AS INTEGER) - ?) <= 2
                   GROUP BY task_content
                   ORDER BY cnt DESC LIMIT 5""",
                   (str(weekday), hour),
            ).fetchall()

            for row in rows:
                if row["cnt"] >= 2:
                    predictions.append({
                        "type": "pattern",
                        "description": f"您通常在{['周一','周二','周三','周四','周五','周六','周日'][weekday]}这个时间处理「{row['task_content'][:30]}」",
                        "action": f"是否需要处理{row['task_content'][:20]}？",
                        "relevance": min(row["cnt"] * 0.2, 0.8),
                    })

        finally:
            conn.close()
    except Exception:
        pass

    return predictions


def _predict_time_sensitive() -> list[dict]:
    """基于时间的特殊需求预测。"""
    predictions = []
    now = datetime.now()

    # 月末预测
    import calendar
    last_day = calendar.monthrange(now.year, now.month)[1]
    if now.day >= last_day - 3:
        predictions.append({
            "type": "time_sensitive",
            "description": "月末将至，可能需要准备月度总结或月报",
            "action": "是否需要生成月度总结？",
            "relevance": 0.6 if now.day >= last_day - 1 else 0.4,
        })

    # 周五预测
    if now.weekday() == 4 and now.hour >= 16:
        predictions.append({
            "type": "time_sensitive",
            "description": "周五下午，可能需要整理本周工作",
            "action": "是否需要生成本周周报？",
            "relevance": 0.5,
        })

    # 周一预测
    if now.weekday() == 0 and now.hour <= 10:
        predictions.append({
            "type": "time_sensitive",
            "description": "周一上午，可能需要规划本周工作",
            "action": "是否需要查看本周日程？",
            "relevance": 0.4,
        })

    return predictions


def generate_proactive_suggestion() -> str | None:
    """生成主动建议（在用户空闲时调用）。"""
    try:
        predictions = predict_next_needs()
        if not predictions:
            return None

        # 只返回相关性最高的
        top = predictions[0]
        if top.get("relevance", 0) < 0.4:
            return None

        return top.get("action") or top.get("description")
    except Exception:
        return None
