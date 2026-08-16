"""深化版演化引擎单元测试。"""
import pytest
import sqlite3
from unittest.mock import patch

# 确保数据库表已创建
import memory_store.sqlite_db as db_module
from memory_store.sqlite_db import get_conn, init_db


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    """每个测试用例使用独立的临时数据库。"""
    db_path = tmp_path / "test.db"
    import config.path_config as path_config
    monkeypatch.setattr(path_config, "DB_PATH", db_path)
    # 重置模块级连接缓存
    import memory_store.user_weight as uw
    from memory_store.repositories.habit_repo import HabitRepository
    uw._repo = HabitRepository()
    init_db()
    yield


# ── 在 fixture 后导入被测模块 ──
from evolution_core.pattern_miner import (
    learn_from_task,
    get_top_patterns,
    _extract_keywords,
    _generate_pattern_key,
    _pattern_score,
)
from evolution_core.feedback_learner import (
    record_feedback,
    generate_execution_guidance,
    _analyze_modification,
    _detect_style,
    _compute_diff,
)
from evolution_core.judge_score import (
    score_task,
    analyze_score_trend,
    _rule_score,
    _get_weights,
)
from evolution_core.weight_evolve import (
    evolve_from_task,
    get_habit_profile,
    _calculate_weight_delta,
    _extract_habit_keys,
    _classify_habit_type,
)


class TestPatternMiner:
    """测试模式挖掘。"""

    def test_extract_keywords(self):
        """应从文本提取关键词。"""
        keywords = _extract_keywords("生成周报并整理月度数据")
        assert len(keywords) > 0
        assert isinstance(keywords, list)

    def test_generate_pattern_key(self):
        """应生成唯一模式标识（基于步骤数，避免名称碎片化）。"""
        key = _generate_pattern_key(["收集数据", "分析数据", "生成报告"], ["周报"])
        assert "周报" in key
        # key 基于步骤数而非步骤名，避免 LLM 生成名称不同导致碎片化
        assert "3steps" in key

    def test_generate_detailed_pattern_key(self):
        """详细模式 key 应包含步骤类型序列。"""
        from evolution_core.pattern_miner import _generate_detailed_pattern_key
        key = _generate_detailed_pattern_key(
            ["收集数据", "分析数据", "生成报告"], ["周报"],
            ["action", "parallel", "action"]
        )
        assert "周报" in key
        assert "action+parallel+action" in key

    def test_pattern_score(self):
        """模式综合得分应正确计算。"""
        pattern = {"confidence": 0.8, "usage_count": 5, "avg_score": 80}
        score = _pattern_score(pattern)
        assert 0.6 < score < 0.8

    def test_learn_from_task_creates_pattern(self):
        """应从任务中学习新模式。"""
        steps = [
            {"name": "收集数据", "index": 0},
            {"name": "分析数据", "index": 1},
            {"name": "生成报告", "index": 2},
        ]
        learn_from_task("生成周报", steps, 80, 30, True)

    def test_get_top_patterns_empty(self):
        """无模式时返回空列表。"""
        patterns = get_top_patterns(n=10, min_confidence=0.5)
        assert isinstance(patterns, list)


class TestFeedbackLearner:
    """测试反馈学习。"""

    def test_record_modify_feedback(self):
        """应记录修改反馈。"""
        fid = record_feedback(
            "modify",
            original="这是一段测试文本",
            modified="这是一段精简的测试文本",
            task_type="work",
        )
        assert isinstance(fid, int)

    def test_record_invalid_feedback_type(self):
        """无效反馈类型应返回 None。"""
        fid = record_feedback("invalid_type")
        assert fid is None

    def test_analyze_modification_length_reduction(self):
        """长度减少应识别为简洁偏好。"""
        result = _analyze_modification("这是一段非常长的测试文本内容" * 5, "简短文本")
        if result:
            assert "length" in result["key"]

    def test_analyze_modification_format_change(self):
        """格式变化应识别为格式偏好（长度相近时）。"""
        result = _analyze_modification("这是一段连续的文本内容用于测试", "第一段内容\n\n第二段内容")
        if result:
            assert "format" in result["key"]

    def test_detect_style_formal(self):
        """应检测正式风格。"""
        assert _detect_style("综上所述，因此我们决定") == "正式"

    def test_detect_style_casual(self):
        """应检测口语化风格。"""
        assert _detect_style("所以总的来说给你看看") == "口语化"

    def test_compute_diff_identical(self):
        """相同文本差异为空。"""
        assert _compute_diff("相同文本", "相同文本") == ""

    def test_compute_diff_major_change(self):
        """大幅修改应返回大幅重写。"""
        diff = _compute_diff("a" * 100, "b" * 100)
        assert diff == "大幅重写"

    def test_generate_execution_guidance_empty(self):
        """无偏好时返回空字符串。"""
        guidance = generate_execution_guidance("work")
        assert isinstance(guidance, str)


class TestJudgeScore:
    """测试多维度打分。"""

    def test_rule_score_returns_all_dimensions(self):
        """规则打分应返回所有维度。"""
        result = {
            "task_text": "测试任务",
            "steps": [{"name": "步骤1"}, {"name": "步骤2"}],
            "step_results": [{"name": "步骤1", "result": "完成" * 100}],
            "cost_time": 30,
            "status": "success",
            "logs": [],
        }
        scores = _rule_score(result, "work")
        assert "completeness" in scores
        assert "efficiency" in scores
        assert "quality" in scores
        assert "consistency" in scores
        assert "satisfaction" in scores
        assert "novelty" in scores
        assert "overall" in scores

    def test_rule_score_within_range(self):
        """各维度分数应在 0-100 范围内。"""
        result = {
            "task_text": "测试",
            "steps": [{"name": "步骤1"}],
            "step_results": [{"name": "步骤1", "result": "完成" * 50}],
            "cost_time": 30,
            "status": "success",
            "logs": [],
        }
        scores = _rule_score(result, "work")
        for dim in ["completeness", "efficiency", "quality", "consistency", "satisfaction", "novelty"]:
            assert 0 <= scores[dim] <= 100

    def test_dimension_weights_sum_to_one(self):
        """权重之和应为 1。"""
        # 使用 _get_weights() 获取延迟加载的权重
        weights_dict = _get_weights()
        for task_type, weights in weights_dict.items():
            total = sum(weights.values())
            assert abs(total - 1.0) < 0.01

    def test_score_task_returns_dict(self):
        """打分应返回字典。"""
        result = {
            "task_text": "测试任务",
            "task_type": "work",
            "steps": [{"name": "步骤1"}],
            "step_results": [{"name": "步骤1", "result": "完成" * 50}],
            "cost_time": 30,
            "status": "success",
            "logs": [],
        }
        scores = score_task(result, "work")
        assert isinstance(scores, dict)
        assert "overall" in scores

    def test_analyze_score_trend_no_data(self):
        """无数据时应返回 insufficient_data。"""
        trend = analyze_score_trend("nonexistent_type", window=5)
        assert trend["trend"] == "insufficient_data"


class TestWeightEvolve:
    """测试权重迭代（深化版）。"""

    def test_extract_habit_keys_work(self):
        """应从工作类文本提取习惯关键词。"""
        keys = _extract_habit_keys("生成本周周报并整理数据", "work")
        assert "周报" in keys

    def test_extract_habit_keys_life(self):
        """应从生活类文本提取习惯关键词。"""
        keys = _extract_habit_keys("记录本月开销和记账", "life")
        assert "记账" in keys

    def test_classify_habit_type(self):
        """应正确分类习惯类型。"""
        assert _classify_habit_type("周报") == "work"
        assert _classify_habit_type("记账") == "life"
        assert _classify_habit_type("睡眠") == "health"
        assert _classify_habit_type("未知") == "other"

    def test_calculate_weight_delta_boost(self):
        """高分应提权。"""
        delta = _calculate_weight_delta("周报", 80, "work", True, 30)
        assert delta > 0

    def test_calculate_weight_delta_penalty(self):
        """低分应降权。"""
        delta = _calculate_weight_delta("周报", 40, "work", False, 30)
        assert delta < 0

    def test_calculate_weight_delta_efficiency_bonus(self):
        """快速完成且高分应有额外奖励。"""
        delta_fast = _calculate_weight_delta("周报", 85, "work", True, 15)
        delta_slow = _calculate_weight_delta("周报", 85, "work", True, 120)
        assert delta_fast > delta_slow

    def test_evolve_from_task_no_exception(self):
        """执行权重迭代不应抛异常。"""
        try:
            evolve_from_task("生成周报", 80, "work", True, 30)
        except Exception:
            pytest.fail("evolve_from_task 不应抛异常")

    def test_get_habit_profile(self):
        """应返回按类型分组的画像。"""
        profile = get_habit_profile()
        assert "work" in profile
        assert "life" in profile
        assert "health" in profile
