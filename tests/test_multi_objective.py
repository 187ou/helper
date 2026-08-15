"""多目标优化单元测试。"""
import pytest
from evolution_core.multi_objective import (
    ObjectiveValue,
    ParetoOptimizer,
    WeightedSumOptimizer,
    MultiObjectiveOptimizer,
    OBJECTIVES,
    evaluate_metrics,
    select_best,
)


class TestObjectiveValue:
    """测试目标值。"""

    def test_normalize_max(self):
        """最大化目标归一化。"""
        obj = ObjectiveValue("quality", 80, direction="max")
        assert obj.normalized(0, 100) == 0.8

    def test_normalize_min(self):
        """最小化目标归一化。"""
        obj = ObjectiveValue("time", 30, direction="min")
        assert obj.normalized(0, 60) == 0.5

    def test_normalize_same_min_max(self):
        """最小值等于最大值时返回 0.5。"""
        obj = ObjectiveValue("test", 50)
        assert obj.normalized(50, 50) == 0.5


class TestParetoOptimizer:
    """测试 Pareto 最优。"""

    def test_find_pareto_front(self):
        """应找到 Pareto 前沿。"""
        solutions = [
            {"quality": 80, "efficiency": 70},
            {"quality": 90, "efficiency": 80},  # 支配第一个
            {"quality": 85, "efficiency": 75},
        ]
        pareto = ParetoOptimizer.find_pareto_front(solutions)
        # 第二个解支配第一个，所以第一个不在 Pareto 前沿
        assert 1 in pareto  # 最优解在 Pareto 前沿

    def test_single_solution(self):
        """单解返回自身。"""
        solutions = [{"quality": 80}]
        pareto = ParetoOptimizer.find_pareto_front(solutions)
        assert pareto == [0]

    def test_empty_solutions(self):
        """空列表返回空。"""
        assert ParetoOptimizer.find_pareto_front([]) == []

    def test_no_domination(self):
        """互不支配时所有解都在前沿。"""
        solutions = [
            {"quality": 90, "efficiency": 60},
            {"quality": 60, "efficiency": 90},
        ]
        pareto = ParetoOptimizer.find_pareto_front(solutions)
        assert len(pareto) == 2


class TestWeightedSumOptimizer:
    """测试加权求和优化器。"""

    def test_evaluate(self):
        """评估应返回加权平均值。"""
        optimizer = WeightedSumOptimizer({"a": 0.5, "b": 0.5})
        score = optimizer.evaluate({"a": 80, "b": 60})
        assert score == 70.0

    def test_evaluate_with_weights(self):
        """不同权重应产生不同结果。"""
        optimizer = WeightedSumOptimizer({"a": 0.8, "b": 0.2})
        score = optimizer.evaluate({"a": 100, "b": 0})
        assert score > 50  # 偏向 a


class TestMultiObjectiveOptimizer:
    """测试多目标优化器。"""

    def test_evaluate_strategy(self):
        """评估策略应返回完整结果。"""
        optimizer = MultiObjectiveOptimizer()
        result = optimizer.evaluate_strategy({
            "quality": 85,
            "efficiency": 70,
            "satisfaction": 90,
            "consistency": 75,
        })
        assert "weighted_score" in result
        assert "achievement" in result
        assert "weakest_objective" in result

    def test_select_best_strategy(self):
        """应选择最佳策略。"""
        optimizer = MultiObjectiveOptimizer()
        strategies = [
            {"quality": 60, "efficiency": 60, "satisfaction": 60, "consistency": 60, "name": "bad"},
            {"quality": 90, "efficiency": 90, "satisfaction": 90, "consistency": 90, "name": "good"},
        ]
        best = optimizer.select_best_strategy(strategies)
        assert best["name"] == "good"

    def test_suggest_improvement(self):
        """应给出改进建议。"""
        optimizer = MultiObjectiveOptimizer()
        suggestions = optimizer.suggest_improvement({
            "quality": 50,  # 弱项
            "efficiency": 90,
            "satisfaction": 90,
            "consistency": 90,
        })
        assert len(suggestions) > 0
        assert any("quality" in s for s in suggestions)

    def test_get_adaptive_weights(self):
        """应返回自适应权重。"""
        optimizer = MultiObjectiveOptimizer()
        weights = optimizer.get_adaptive_weights("work")
        assert abs(sum(weights.values()) - 1.0) < 0.01  # 权重和为 1

    def test_balanced_metrics(self):
        """均衡指标应返回 balanced=True。"""
        optimizer = MultiObjectiveOptimizer()
        result = optimizer.evaluate_strategy({
            "quality": 90,
            "efficiency": 85,
            "satisfaction": 88,
            "consistency": 80,
        })
        assert result["balanced"] is True


class TestObjectives:
    """测试目标定义。"""

    def test_weights_sum_to_one(self):
        """权重之和应为 1。"""
        total = sum(obj["weight"] for obj in OBJECTIVES.values())
        assert abs(total - 1.0) < 0.01

    def test_all_directions_are_max(self):
        """所有目标应都是最大化。"""
        for obj in OBJECTIVES.values():
            assert obj["direction"] == "max"
