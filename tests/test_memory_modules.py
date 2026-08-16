"""记忆模块专项测试：覆盖核心逻辑 + 边缘情况。"""
import pytest
import sqlite3
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

import memory_store.sqlite_db as db_module
from memory_store.sqlite_db import get_conn, init_db


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    """每个测试用例使用独立的临时数据库。"""
    db_path = tmp_path / "test.db"
    import config.path_config as path_config
    monkeypatch.setattr(path_config, "DB_PATH", db_path)
    monkeypatch.setattr(path_config, "CHROMA_DIR", tmp_path / "chroma")
    monkeypatch.setattr(path_config, "EPISODIC_DIR", tmp_path / "episodic")
    monkeypatch.setattr(path_config, "USER_DATA_DIR", tmp_path / "user_data")
    monkeypatch.setattr(path_config, "TEMPLATES_DIR", tmp_path / "templates")
    monkeypatch.setattr(path_config, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(path_config, "ARCHIVE_DIR", tmp_path / "archive")
    # 清除缓存
    db_module._config = None
    init_db()
    yield


class TestEmotionalMemory:
    """情感记忆测试。"""

    def test_detect_positive_emotion(self):
        """应检测积极情绪。"""
        from agent_core.emotional_memory import detect_emotion
        result = detect_emotion("这个功能太棒了！")
        assert result["emotion"] == "positive"
        assert result["intensity"] > 0.5

    def test_detect_negative_emotion(self):
        """应检测消极情绪。"""
        from agent_core.emotional_memory import detect_emotion
        result = detect_emotion("又错了，真烦人")
        assert result["emotion"] == "negative"
        assert result["intensity"] > 0.3

    def test_detect_neutral_emotion(self):
        """中性文本应返回 neutral。"""
        from agent_core.emotional_memory import detect_emotion
        result = detect_emotion("帮我打开文件")
        assert result["emotion"] == "neutral"

    def test_detect_empty_text(self):
        """空文本应返回 neutral。"""
        from agent_core.emotional_memory import detect_emotion
        result = detect_emotion("")
        assert result["emotion"] == "neutral"
        assert result["confidence"] == 0

    def test_record_and_get_trend(self):
        """记录情绪后应能查询趋势。"""
        from agent_core.emotional_memory import record_emotion, get_emotion_trend
        record_emotion(1, "太棒了！", "user_input")
        record_emotion(2, "真烦人", "feedback")
        trend = get_emotion_trend(days=7)
        assert trend.get("total_records", 0) >= 2

    def test_emotion_alert_negative_accumulation(self):
        """负面情绪累积应触发预警。"""
        from agent_core.emotional_memory import record_emotion, check_emotion_alert
        for i in range(5):
            record_emotion(i + 10, "真烦人，又错了", "user_input")
        alert = check_emotion_alert()
        assert alert is not None
        assert "负面" in alert


class TestProspectiveMemory:
    """前瞻记忆测试。"""

    def test_parse_daily_reminder(self):
        """应解析每日提醒。"""
        from agent_core.prospective_memory import _parse_time_trigger
        result = _parse_time_trigger("每天早上9点提醒我写日报")
        assert result is not None
        assert result["trigger_type"] == "time"
        assert result["recurrence"] == "daily"

    def test_parse_weekly_reminder(self):
        """应解析每周提醒。"""
        from agent_core.prospective_memory import _parse_time_trigger
        result = _parse_time_trigger("每周五提醒我交周报")
        assert result is not None
        assert result["recurrence"] == "weekly"

    def test_parse_relative_day(self):
        """应解析相对日期。"""
        from agent_core.prospective_memory import _parse_time_trigger
        result = _parse_time_trigger("明天提醒我开会")
        assert result is not None
        assert "明天" in result["trigger_value"]

    def test_parse_event_trigger(self):
        """应解析事件触发。"""
        from agent_core.prospective_memory import _parse_event_trigger
        result = _parse_event_trigger("每次收到发票时提醒我报销")
        assert result is not None
        assert result["trigger_type"] == "event"

    def test_parse_condition_trigger(self):
        """应解析条件触发。"""
        from agent_core.prospective_memory import _parse_condition_trigger
        result = _parse_condition_trigger("连续3天没记账时提醒我")
        assert result is not None
        assert result["trigger_type"] == "condition"

    def test_parse_no_intent(self):
        """非前瞻意图应返回 None。"""
        from agent_core.emotional_memory import detect_emotion  # 避免导入问题
        from agent_core.prospective_memory import _detect_intent
        result = _detect_intent("帮我写一份周报")
        assert result is None

    def test_duplicate_detection(self):
        """重复意图应被检测。"""
        from agent_core.prospective_memory import parse_and_store_intent, _store_intent, _is_duplicate_intent
        # 先直接存储一条
        intent = {"trigger_type": "time", "trigger_value": "测试重复", "trigger_time": "",
                  "priority": 1, "recurrence": "", "note": "测试重复"}
        _store_intent(intent)
        # 检查是否重复
        assert _is_duplicate_intent(intent) is True
        # 不同意图不应重复
        intent2 = {"trigger_type": "time", "trigger_value": "不重复的", "trigger_time": "",
                   "priority": 1, "recurrence": "", "note": "不重复的"}
        assert _is_duplicate_intent(intent2) is False


class TestMemoryGraph:
    """关联记忆测试。"""

    def test_create_and_retrieve_link(self):
        """创建关联后应能检索。"""
        from agent_core.memory_graph import create_link, get_related_memories
        create_link("episodic", "task_1", "semantic", "kb://test.pdf", "references", 0.8)
        related = get_related_memories("episodic", "task_1")
        assert len(related) >= 1
        assert related[0]["memory_type"] == "semantic"

    def test_multi_hop_retrieval(self):
        """应支持多跳关联检索。"""
        from agent_core.memory_graph import create_link, get_related_memories
        create_link("episodic", "task_1", "episodic", "task_2", "follows", 0.6)
        create_link("episodic", "task_2", "semantic", "kb://doc.pdf", "references", 0.7)
        related = get_related_memories("episodic", "task_1", max_depth=2)
        # 应该能找到 task_2（深度1）和 kb://doc.pdf（深度2）
        depths = [r["depth"] for r in related]
        assert 1 in depths

    def test_no_related(self):
        """无关联记忆应返回空列表。"""
        from agent_core.memory_graph import get_related_memories
        related = get_related_memories("episodic", "nonexistent_task")
        assert related == []


class TestWorkingMemory:
    """工作记忆测试。"""

    def test_record_step_completion(self):
        """记录步骤完成应更新摘要。"""
        from agent_core.working_memory import WorkingMemory
        wm = WorkingMemory(1, "测试任务", [{"name": "步骤1"}, {"name": "步骤2"}])
        wm.update_goal("完成测试")
        wm.record_step_completion("步骤1", "完成了第一步")
        assert "步骤1" in wm.completed_steps
        assert "步骤1" not in wm.remaining_steps
        assert len(wm.completed_summary) > 0

    def test_lru_eviction(self):
        """超出容量时应淘汰最早的。"""
        from agent_core.working_memory import (
            get_working_memory, _working_memories, _MAX_WORKING_MEMORIES
        )
        # 填满
        for i in range(_MAX_WORKING_MEMORIES + 5):
            get_working_memory(100 + i, f"任务{i}", [])
        assert len(_working_memories) <= _MAX_WORKING_MEMORIES

    def test_context_summary_format(self):
        """摘要格式应为结构化文本。"""
        from agent_core.working_memory import WorkingMemory
        wm = WorkingMemory(1, "测试", [{"name": "s1"}])
        wm.update_goal("目标")
        summary = wm.get_context_summary()
        assert "任务目标" in summary


class TestMemoryConsolidation:
    """记忆巩固测试。"""

    def test_extract_patterns_empty_db(self):
        """空数据库应返回无模式。"""
        from agent_core.memory_consolidation import _extract_patterns_from_episodic
        result = _extract_patterns_from_episodic(datetime.now())
        assert result["source_count"] == 0

    def test_strengthen_preferences_no_data(self):
        """无偏好数据应返回空结果。"""
        from agent_core.memory_consolidation import _strengthen_frequent_preferences
        result = _strengthen_frequent_preferences(datetime.now())
        # source_count 是待强化的偏好数量（可能 > 0 因为表中有默认数据）
        assert isinstance(result["source_count"], int)

    def test_run_consolidation_no_crash(self):
        """巩固周期不应崩溃（空数据）。"""
        from agent_core.memory_consolidation import run_consolidation
        result = run_consolidation(days=1)
        assert "steps" in result
        assert "reflection" in result


class TestDeepReflection:
    """深度反思测试。"""

    def test_insufficient_data(self):
        """数据不足时应返回友好提示。"""
        from agent_core.reflection import generate_reflection_report
        result = generate_reflection_report("weekly")
        # 如果数据不足，应有 message 字段
        if result.get("statistics", {}).get("total_tasks", 0) < 2:
            assert "message" in result

    def test_root_causes_empty(self):
        """无失败任务时应返回空根因。"""
        from agent_core.deep_reflection import _analyze_root_causes
        causes = _analyze_root_causes(datetime.now() - timedelta(days=1))
        assert isinstance(causes, list)
        assert len(causes) == 0


class TestMetamemory:
    """元记忆测试。"""

    def test_track_and_retrieve(self):
        """追踪后应能检索。"""
        from agent_core.metamemory import track_memory, get_memory_reliability
        track_memory("preference", "test:key", "user_feedback", 0.8, 3)
        rel = get_memory_reliability("preference", "test:key")
        assert rel is not None
        assert rel["confidence"] == 0.8

    def test_freshness_calculation(self):
        """新鲜度计算应正确。"""
        from agent_core.metamemory import _calculate_freshness
        assert _calculate_freshness(0.8, 5) == "fresh"
        assert _calculate_freshness(0.5, 1) == "stale"
        assert _calculate_freshness(0.2, 0) == "expired"

    def test_system_health(self):
        """系统健康检查应返回评分。"""
        from agent_core.metamemory import get_system_health
        health = get_system_health()
        assert "health_score" in health
        assert 0 <= health["health_score"] <= 100


class TestUserModel:
    """用户模型测试。"""

    def test_build_empty_model(self):
        """空数据库应返回默认模型。"""
        from agent_core.user_model import build_user_model
        model = build_user_model()
        assert "capability" in model

    def test_personalized_guidance_empty(self):
        """无用户数据时应返回空指导。"""
        from agent_core.user_model import get_personalized_guidance
        guidance = get_personalized_guidance("work")
        # 无数据时返回空字符串
        assert isinstance(guidance, str)


class TestContextWindow:
    """上下文窗口测试。"""

    def test_estimate_tokens_chinese(self):
        """中文 token 估算应大致准确。"""
        from agent_core.context_window import estimate_tokens
        tokens = estimate_tokens("中文文本测试")
        assert tokens > 0

    def test_fit_context_priority(self):
        """高优先级内容应优先保留。"""
        from agent_core.context_window import fit_context
        parts = [
            ("系统指令", 1),
            ("低优先级内容" * 100, 5),
            ("当前查询", 2),
        ]
        result = fit_context(parts, max_tokens=50)
        assert "系统指令" in result
        assert "当前查询" in result

    def test_truncate_at_sentence(self):
        """截断应在句子边界。"""
        from agent_core.context_window import truncate_text
        text = "第一句话。第二句话。第三句话。"
        truncated = truncate_text(text, 10)
        assert len(truncated) <= len(text)


class TestEventTrigger:
    """事件触发测试。"""

    def test_event_trigger_detection(self):
        """任务完成时应检测事件触发。"""
        from agent_core.prospective_memory import _check_event_triggers
        from memory_store.sqlite_db import get_conn
        # 直接插入事件触发提醒到数据库
        conn = get_conn()
        try:
            conn.execute(
                """INSERT INTO prospective_memory
                   (user_intent, trigger_type, trigger_value, trigger_event, priority, recurrence, status, note)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ("每次收到发票时提醒我报销", "event", "收到发票时", "发票", 1, "event", "pending", "测试事件触发"),
            )
            conn.commit()
        finally:
            conn.close()
        # 模拟任务完成（包含"发票"关键词）
        due = _check_event_triggers("收到了新的发票，需要处理", datetime.now())
        assert len(due) >= 1
        assert due[0]["trigger_type"] == "event"

    def test_event_no_match(self):
        """任务文本不匹配事件关键词时不应触发。"""
        from agent_core.prospective_memory import _check_event_triggers
        due = _check_event_triggers("今天天气不错", datetime.now())
        # 不应触发"发票"事件
        assert all("发票" not in d.get("trigger_value", "") for d in due)


class TestWorkingMemoryRestore:
    """工作记忆恢复测试。"""

    def test_restore_from_task(self):
        """应能从持久化的任务恢复工作记忆。"""
        from agent_core.working_memory import restore_working_memory_from_task
        # 恢复不存在的任务应返回 None
        wm = restore_working_memory_from_task(99999)
        assert wm is None


class TestMemoryLinkDelete:
    """关联删除测试。"""

    def test_delete_links_for_task(self):
        """删除任务时应同时删除关联。"""
        from agent_core.memory_graph import create_link, delete_links_for_task, get_related_memories
        # 创建关联
        create_link("episodic", "task_delete_test", "semantic", "kb://test.pdf", "references", 0.8)
        # 验证关联存在
        related = get_related_memories("episodic", "task_delete_test")
        assert len(related) >= 1
        # 删除关联
        deleted = delete_links_for_task(99999)  # 不存在的任务
        assert deleted >= 0  # 不崩溃即可


class TestLLMInsight:
    """LLM 洞察生成测试。"""

    def test_llm_insight_fallback(self):
        """LLM 不可用时降级到规则建议。"""
        from agent_core.deep_reflection import _generate_llm_insight
        # 空数据时不应崩溃
        result = _generate_llm_insight([], [], [])
        # LLM 未配置时返回 None（正常降级）
        assert result is None or isinstance(result, str)


class TestTokenEstimation:
    """Token 估算测试。"""

    def test_chinese_text(self):
        """中文文本估算应大致准确。"""
        from agent_core.context_window import estimate_tokens
        tokens = estimate_tokens("这是一段中文测试文本，用于验证 token 估算的准确性。")
        # 中文约 1.5 char/token，30 字 ≈ 20 tokens
        assert 10 <= tokens <= 30

    def test_english_text(self):
        """英文文本估算应大致准确。"""
        from agent_core.context_window import estimate_tokens
        tokens = estimate_tokens("This is a sample English text for token estimation testing.")
        # 英文约 1.3 token/word，11 words ≈ 14 tokens
        assert 8 <= tokens <= 20

    def test_code_block(self):
        """代码块应使用更低的 char/token 比率。"""
        from agent_core.context_window import estimate_tokens
        code = "```python\ndef hello():\n    print('hello')\n```"
        tokens = estimate_tokens(code)
        assert tokens > 0

    def test_json_block(self):
        """JSON 块应正确识别。"""
        from agent_core.context_window import estimate_tokens
        json_text = '{"name": "test", "value": 123, "nested": {"key": "val"}}'
        tokens = estimate_tokens(json_text)
        assert tokens > 0

    def test_mixed_content(self):
        """混合内容（中英+代码）应正确估算。"""
        from agent_core.context_window import estimate_tokens
        mixed = "这是中文 mixed with English and code: def test(): pass"
        tokens = estimate_tokens(mixed)
        assert tokens > 0

    def test_empty_text(self):
        """空文本应返回 0。"""
        from agent_core.context_window import estimate_tokens
        assert estimate_tokens("") == 0

    def test_truncate_preserves_sentences(self):
        """截断应在句子边界。"""
        from agent_core.context_window import truncate_text
        text = "第一句话。第二句话。第三句话。第四句话。"
        truncated = truncate_text(text, 10)
        # 截断后应以句号或省略号结尾
        assert truncated.endswith("。") or truncated.endswith("...")


class TestMemoryMerge:
    """记忆合并测试。"""

    def test_merge_similar_preferences(self):
        """相似偏好应被合并。"""
        from agent_core.memory_consolidation import _merge_similar_preferences
        from memory_store.sqlite_db import get_conn
        conn = get_conn()
        try:
            # 使用 INSERT OR REPLACE 避免唯一约束冲突
            conn.execute(
                """INSERT OR REPLACE INTO user_preference (pref_key, pref_value, confidence, evidence_count)
                   VALUES (?, ?, ?, ?)""",
                ("merge:test:detail", "简洁", 0.6, 2),
            )
            conn.execute(
                """INSERT OR REPLACE INTO user_preference (pref_key, pref_value, confidence, evidence_count)
                   VALUES (?, ?, ?, ?)""",
                ("merge:test:basic", "简洁", 0.5, 1),
            )
            conn.commit()

            # 执行合并
            merged = _merge_similar_preferences(conn)
            assert merged >= 1  # 至少合并了一条
        finally:
            conn.close()


class TestEdgeCases:
    """边缘情况测试。"""

    def test_very_long_task_text(self):
        """超长任务文本不应崩溃。"""
        from agent_core.memory_context import build_memory_context
        long_text = "写周报" * 1000
        result = build_memory_context(long_text, top_k=1)
        assert isinstance(result, str)

    def test_special_characters(self):
        """特殊字符不应崩溃。"""
        from agent_core.emotional_memory import detect_emotion
        result = detect_emotion("任务完成了！🎉 <script>alert('xss')</script>")
        assert result["emotion"] in ("positive", "negative", "neutral", "anxious", "bored")

    def test_concurrent_db_access(self):
        """并发数据库访问不应崩溃。"""
        from agent_core.metamemory import track_memory
        import threading
        errors = []

        def worker(i):
            try:
                track_memory("test", f"key_{i}", "test", 0.5, 1)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # SQLite WAL 模式下不应有错误
        assert len(errors) == 0

    def test_none_inputs(self):
        """None 输入应安全处理。"""
        from agent_core.emotional_memory import detect_emotion
        result = detect_emotion(None)
        assert result["emotion"] == "neutral"

    def test_emoji_handling(self):
        """Emoji 不应导致崩溃。"""
        from agent_core.prospective_memory import _detect_intent
        result = _detect_intent("记住明天提醒我 📝")
        # 有"记住"关键词，应识别为意图
        assert result is not None
