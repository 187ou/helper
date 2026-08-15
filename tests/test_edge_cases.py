"""演化引擎边缘场景测试。"""
import pytest
import sqlite3

# 确保数据库初始化
from memory_store.sqlite_db import init_db


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    """每个测试用例使用独立临时数据库。"""
    db_path = tmp_path / "test.db"
    import config.path_config as path_config
    monkeypatch.setattr(path_config, "DB_PATH", db_path)
    import memory_store.user_weight as uw
    from memory_store.repositories.habit_repo import HabitRepository
    uw._repo = HabitRepository()
    init_db()
    yield


from evolution_core.safe_ops import (
    safe_divide, clamp_value, safe_avg, safe_sum,
    safe_json_loads, safe_json_dumps, sanitize_text,
    validate_task_result, safe_db_read, safe_db_write,
)
from evolution_core.pattern_miner import _extract_keywords, _pattern_score, learn_from_task
from evolution_core.feedback_learner import _analyze_modification, _detect_style, _compute_diff
from evolution_core.judge_score import _rule_score, score_task
from evolution_core.weight_evolve import _calculate_weight_delta, _extract_habit_keys


class TestSafeOps:
    """测试安全操作工具。"""

    def test_safe_divide_by_zero(self):
        """零除应返回默认值。"""
        assert safe_divide(10, 0, default=0.0) == 0.0
        assert safe_divide(10, 0, default=99) == 99

    def test_safe_divide_normal(self):
        """正常除法。"""
        assert safe_divide(10, 2) == 5.0
        assert safe_divide(7, 3) == pytest.approx(2.333, rel=1e-2)

    def test_clamp_value_overflow(self):
        """溢出应限幅。"""
        assert clamp_value(150, 0, 100) == 100
        assert clamp_value(-10, 0, 100) == 0
        assert clamp_value(50, 0, 100) == 50

    def test_safe_avg_empty(self):
        """空列表返回默认值。"""
        assert safe_avg([], default=0) == 0
        assert safe_avg([1, 2, 3]) == 2.0

    def test_safe_sum_empty(self):
        """空列表返回默认值。"""
        assert safe_sum([], default=0) == 0
        assert safe_sum([1, 2, 3]) == 6

    def test_safe_json_loads_invalid(self):
        """非法 JSON 返回默认值。"""
        assert safe_json_loads("not json", default=[]) == []
        assert safe_json_loads(None, default={}) == {}
        assert safe_json_loads("", default=[]) == []

    def test_safe_json_loads_valid(self):
        """合法 JSON 正常解析。"""
        assert safe_json_loads('[1, 2, 3]') == [1, 2, 3]
        assert safe_json_loads('{"a": 1}') == {"a": 1}

    def test_safe_json_dumps_unserializable(self):
        """不可序列化对象使用 default 函数处理（str 转换）。"""
        result = safe_json_dumps(object(), default="{}")
        # default=str 会将 object 转为字符串表示
        assert isinstance(result, str)
        assert len(result) > 0

    def test_sanitize_text_none(self):
        """None 返回空字符串。"""
        assert sanitize_text(None) == ""

    def test_sanitize_text_long(self):
        """超长文本截断。"""
        long_text = "a" * 2000
        result = sanitize_text(long_text, max_length=100)
        assert len(result) == 100

    def test_validate_task_result_none(self):
        """None 返回空 dict。"""
        assert validate_task_result(None) == {}

    def test_validate_task_result_missing_fields(self):
        """缺失字段补全默认值。"""
        result = validate_task_result({"task_text": "test"})
        assert isinstance(result["steps"], list)
        assert isinstance(result["step_results"], list)
        assert isinstance(result["cost_time"], (int, float))


class TestSafeDbDecorators:
    """测试安全数据库装饰器。"""

    def test_safe_db_read_handles_exception(self):
        """DB 异常返回 None。"""
        @safe_db_read
        def failing_func():
            raise sqlite3.OperationalError("no such table")

        assert failing_func() is None

    def test_safe_db_write_handles_exception(self):
        """DB 异常返回默认值。"""
        @safe_db_write(default_return=False)
        def failing_func():
            raise sqlite3.OperationalError("no such table")

        assert failing_func() is False


class TestPatternMinerEdgeCases:
    """测试模式挖掘边缘情况。"""

    def test_extract_keywords_empty(self):
        """空文本返回空列表。"""
        assert _extract_keywords("") == []

    def test_pattern_score_zero_confidence(self):
        """零置信度返回低分。"""
        score = _pattern_score({"confidence": 0, "usage_count": 0, "avg_score": 0})
        assert score == 0

    def test_learn_from_task_empty_steps(self):
        """空步骤不抛异常。"""
        learn_from_task("", [], 80, 30, True)  # 不应抛异常

    def test_learn_from_task_single_step(self):
        """单一步骤不形成模式。"""
        learn_from_task("test", [{"name": "步骤1"}], 80, 30, True)


class TestFeedbackLearnerEdgeCases:
    """测试反馈学习边缘情况。"""

    def test_analyze_modification_identical(self):
        """相同内容返回 None。"""
        assert _analyze_modification("相同", "相同") is None

    def test_analyze_modification_empty(self):
        """空内容返回 None。"""
        assert _analyze_modification("", "") is None

    def test_detect_style_empty(self):
        """空文本返回中性。"""
        assert _detect_style("") == "中性"

    def test_compute_diff_identical(self):
        """相同文本差异为空。"""
        assert _compute_diff("abc", "abc") == ""

    def test_compute_diff_empty(self):
        """空文本差异为空。"""
        assert _compute_diff("", "") == ""


class TestJudgeScoreEdgeCases:
    """测试打分边缘情况。"""

    def test_rule_score_empty_result(self):
        """空结果不抛异常。"""
        scores = _rule_score({}, "work")
        assert "overall" in scores
        assert 0 <= scores["overall"] <= 100

    def test_rule_score_missing_fields(self):
        """缺失字段不抛异常。"""
        scores = _rule_score({"cost_time": 30}, "life")
        assert "overall" in scores

    def test_rule_score_zero_steps(self):
        """零步骤不抛异常（零除保护）。"""
        scores = _rule_score({"steps": [], "step_results": []}, "work")
        assert scores["completeness"] == 0

    def test_score_task_none_result(self):
        """None 结果不抛异常。"""
        scores = score_task(None, "work")
        assert "overall" in scores

    def test_score_task_negative_cost_time(self):
        """负耗时处理。"""
        scores = _rule_score({"cost_time": -10, "steps": [1], "step_results": [1]}, "work")
        assert "overall" in scores


class TestWeightEvolveEdgeCases:
    """测试权重迭代边缘情况。"""

    def test_calculate_delta_extreme_high_score(self):
        """极高分的 delta 为正。"""
        delta = _calculate_weight_delta("test", 150, "work", True, 10)
        assert delta > 0

    def test_calculate_delta_extreme_low_score(self):
        """极低分的 delta 为负。"""
        delta = _calculate_weight_delta("test", -50, "work", False, 10)
        assert delta < 0

    def test_extract_habit_keys_empty_text(self):
        """空文本返回空列表。"""
        assert _extract_habit_keys("", "work") == []

    def test_extract_habit_keys_unknown_type(self):
        """未知类型返回空列表。"""
        assert _extract_habit_keys("test", "unknown_type") == []
