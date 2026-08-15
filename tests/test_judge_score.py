"""演化打分模块单元测试（深化版）。"""
import pytest
from evolution_core.judge_score import (
    score_work,
    score_life,
    combined_score,
    score_task,
    analyze_score_trend,
    _rule_score,
    _DIMENSION_WEIGHTS,
)


class TestRuleScore:
    """测试多维度规则打分。"""

    def test_returns_all_dimensions(self):
        """应返回所有维度。"""
        result = {
            "task_text": "测试任务",
            "steps": [{"name": "步骤1"}, {"name": "步骤2"}],
            "step_results": [{"name": "步骤1", "result": "完成" * 100}],
            "cost_time": 30,
            "status": "success",
            "logs": [],
        }
        scores = _rule_score(result, "work")
        for dim in ["completeness", "efficiency", "quality", "consistency", "satisfaction", "novelty"]:
            assert dim in scores

    def test_within_range(self):
        """各维度应在 0-100 范围内。"""
        result = {
            "cost_time": 30, "steps": [1], "step_results": [{"result": "完成" * 50}],
            "status": "success",
        }
        scores = _rule_score(result, "work")
        for dim in ["completeness", "efficiency", "quality", "consistency", "satisfaction", "novelty"]:
            assert 0 <= scores[dim] <= 100

    def test_failed_task_lower_score(self):
        """失败任务分数应较低。"""
        success_result = {
            "cost_time": 30, "steps": [1, 2], "step_results": [{"result": "完成"}, {"result": "完成"}], "status": "success",
        }
        fail_result = {
            "cost_time": 30, "steps": [1, 2, 3], "step_results": [{"result": "部分"}], "status": "fail",
        }
        success_score = _rule_score(success_result, "work")["overall"]
        fail_score = _rule_score(fail_result, "work")["overall"]
        assert success_score > fail_score


class TestCombinedScore:
    """测试综合打分。"""

    def test_work_type(self):
        assert combined_score(80, 60, "work") == 80

    def test_life_type(self):
        assert combined_score(80, 60, "life") == 60

    def test_mix_type(self):
        assert combined_score(80, 60, "mix") == 70


class TestScoreWorkLife:
    """测试兼容接口。"""

    def test_score_work_returns_number(self):
        result = {
            "task_text": "测试",
            "cost_time": 30, "steps": [1], "step_results": [{"result": "完成" * 50}],
            "status": "success", "logs": [],
        }
        score = score_work(result)
        assert 0 <= score <= 100

    def test_score_life_returns_number(self):
        result = {
            "task_text": "记账",
            "cost_time": 10, "step_results": [{"result": "完成" * 50}],
            "status": "success", "logs": [],
        }
        score = score_life(result)
        assert 0 <= score <= 100


class TestDimensionWeights:
    """测试权重定义。"""

    def test_weights_sum_to_one(self):
        """各类型权重之和应为 1。"""
        for task_type, weights in _DIMENSION_WEIGHTS.items():
            total = sum(weights.values())
            assert abs(total - 1.0) < 0.01

    def test_all_types_have_weights(self):
        """所有任务类型应有权重。"""
        assert "work" in _DIMENSION_WEIGHTS
        assert "life" in _DIMENSION_WEIGHTS
        assert "mix" in _DIMENSION_WEIGHTS


class TestAnalyzeScoreTrend:
    """测试分数趋势分析。"""

    def test_no_data_returns_insufficient(self):
        """无数据时返回 insufficient_data。"""
        trend = analyze_score_trend("nonexistent", window=5)
        assert trend["trend"] == "insufficient_data"
