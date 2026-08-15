"""多目标优化：平衡竞争目标。

核心能力：
1. Pareto 最优：找到非支配解集
2. 加权求和：将多目标转化为单目标
3. 目标归一化：统一不同量纲的目标
4. 约束处理：满足硬约束条件
5. 动态权重：根据上下文调整目标权重

优化目标：
- 质量（quality）：任务完成质量
- 效率（efficiency）：执行速度
- 满意度（satisfaction）：用户反馈
- 一致性（consistency）：与历史模式一致
"""
import logging
import math
from typing import Any

from evolution_core.safe_ops import clamp_value, safe_divide

logger = logging.getLogger(__name__)

# ── 目标定义 ──

OBJECTIVES = {
    "quality": {"weight": 0.30, "direction": "max", "target": 90},
    "efficiency": {"weight": 0.25, "direction": "max", "target": 80},
    "satisfaction": {"weight": 0.25, "direction": "max", "target": 85},
    "consistency": {"weight": 0.20, "direction": "max", "target": 75},
}


class ObjectiveValue:
    """目标值。"""

    def __init__(self, name: str, value: float, weight: float = 1.0, direction: str = "max"):
        self.name = name
        self.value = value
        self.weight = weight
        self.direction = direction

    def normalized(self, min_val: float, max_val: float) -> float:
        """归一化到 [0, 1]。"""
        if max_val == min_val:
            return 0.5
        norm = (self.value - min_val) / (max_val - min_val)
        if self.direction == "min":
            norm = 1 - norm
        return clamp_value(norm, 0, 1)


class ParetoOptimizer:
    """Pareto 最优解查找。"""

    @staticmethod
    def find_pareto_front(solutions: list[dict[str, float]]) -> list[int]:
        """找到 Pareto 前沿（非支配解索引）。

        解 A 支配解 B 当且仅当：
        - A 在所有目标上都不差于 B
        - A 至少在一个目标上严格优于 B
        """
        if not solutions:
            return []

        pareto_indices = []
        for i, sol_a in enumerate(solutions):
            dominated = False
            for j, sol_b in enumerate(solutions):
                if i == j:
                    continue
                if ParetoOptimizer._dominates(sol_b, sol_a):
                    dominated = True
                    break
            if not dominated:
                pareto_indices.append(i)

        return pareto_indices

    @staticmethod
    def _dominates(a: dict, b: dict) -> bool:
        """判断 a 是否支配 b。"""
        at_least_one_better = False
        for key in b:
            if key not in a:
                continue
            if a[key] < b[key]:
                return False
            if a[key] > b[key]:
                at_least_one_better = True
        return at_least_one_better


class WeightedSumOptimizer:
    """加权求和优化器。"""

    def __init__(self, weights: dict[str, float] | None = None):
        self.weights = weights or {obj: cfg["weight"] for obj, cfg in OBJECTIVES.items()}

    def evaluate(self, objectives: dict[str, float]) -> float:
        """评估综合得分。"""
        total = 0.0
        total_weight = 0.0

        for name, value in objectives.items():
            weight = self.weights.get(name, 0)
            total += value * weight
            total_weight += weight

        return safe_divide(total, total_weight, default=0)

    def optimize_weights(self, history: list[dict]) -> dict[str, float]:
        """基于历史数据优化权重。

        策略：如果某目标持续不达标，增加其权重。
        """
        if not history:
            return self.weights

        # 计算各目标的平均达成率
        achievement = {}
        for obj_name, obj_cfg in OBJECTIVES.items():
            target = obj_cfg["target"]
            values = [h.get(obj_name, 0) for h in history if obj_name in h]
            if values:
                avg = sum(values) / len(values)
                achievement[obj_name] = safe_divide(avg, target, default=0)
            else:
                achievement[obj_name] = 0.5

        # 调整权重：达成率越低，权重越高
        new_weights = {}
        total_inv_achievement = 0
        for obj_name, ach in achievement.items():
            # 达成率的倒数（未达标的目标获得更高权重）
            inv = 1.0 / max(ach, 0.1)
            new_weights[obj_name] = inv
            total_inv_achievement += inv

        # 归一化
        for obj_name in new_weights:
            new_weights[obj_name] = clamp_value(new_weights[obj_name] / total_inv_achievement, 0.05, 0.8)

        self.weights = new_weights
        return new_weights


class MultiObjectiveOptimizer:
    """多目标优化器（主入口）。"""

    def __init__(self):
        self.pareto = ParetoOptimizer()
        self.weighted = WeightedSumOptimizer()

    def evaluate_strategy(self, metrics: dict[str, float]) -> dict[str, Any]:
        """评估策略。

        Args:
            metrics: {"quality": 85, "efficiency": 70, "satisfaction": 90, "consistency": 75}

        Returns:
            评估结果
        """
        # 加权得分
        weighted_score = self.weighted.evaluate(metrics)

        # 目标达成率
        achievement = {}
        for obj_name, obj_cfg in OBJECTIVES.items():
            target = obj_cfg["target"]
            value = metrics.get(obj_name, 0)
            achievement[obj_name] = round(safe_divide(value, target, default=0) * 100, 1)

        # 找出最弱目标
        weakest = min(achievement.items(), key=lambda x: x[1])

        return {
            "weighted_score": round(weighted_score, 2),
            "achievement": achievement,
            "weakest_objective": weakest[0],
            "weakest_achievement": weakest[1],
            "balanced": all(v >= 70 for v in achievement.values()),
        }

    def select_best_strategy(self, strategies: list[dict[str, Any]]) -> dict[str, Any]:
        """从多个策略中选择最佳。

        使用 Pareto 最优 + 加权求和。
        """
        if not strategies:
            return {}

        if len(strategies) == 1:
            return strategies[0]

        # 提取目标值
        objective_keys = list(OBJECTIVES.keys())
        solutions = []
        for s in strategies:
            sol = {k: s.get(k, 0) for k in objective_keys}
            solutions.append(sol)

        # Pareto 前沿
        pareto_indices = self.pareto.find_pareto_front(solutions)

        if len(pareto_indices) == 1:
            return strategies[pareto_indices[0]]

        # 多个 Pareto 最优解，用加权求和选择
        best_idx = pareto_indices[0]
        best_score = -1

        for idx in pareto_indices:
            score = self.weighted.evaluate(solutions[idx])
            if score > best_score:
                best_score = score
                best_idx = idx

        return strategies[best_idx]

    def get_adaptive_weights(self, task_type: str = "") -> dict[str, float]:
        """获取自适应权重（根据任务类型调整）。"""
        # 基础权重
        weights = dict(self.weighted.weights)

        # 根据任务类型调整
        if task_type == "work":
            weights["quality"] = weights.get("quality", 0.3) + 0.1
            weights["efficiency"] = weights.get("efficiency", 0.25) - 0.05
        elif task_type == "life":
            weights["satisfaction"] = weights.get("satisfaction", 0.25) + 0.1
            weights["consistency"] = weights.get("consistency", 0.2) - 0.05
        elif task_type == "health":
            weights["consistency"] = weights.get("consistency", 0.2) + 0.1

        # 归一化
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}

        return weights

    def suggest_improvement(self, metrics: dict[str, float]) -> list[str]:
        """基于评估结果给出改进建议。"""
        evaluation = self.evaluate_strategy(metrics)
        suggestions = []

        # 最弱目标
        weakest = evaluation.get("weakest_objective", "")
        achievement = evaluation.get("weakest_achievement", 0)

        if achievement < 60:
            suggestions.append(f"优先提升 {weakest}（当前达成率 {achievement}%）")
        elif achievement < 80:
            suggestions.append(f"关注 {weakest} 提升空间（当前达成率 {achievement}%）")

        # 平衡性
        if not evaluation.get("balanced", False):
            suggestions.append("目标发展不均衡，建议关注弱项")

        if not suggestions:
            suggestions.append("各目标发展均衡，继续保持")

        return suggestions


# ── 全局实例 ──

_multi_objective = None


def get_multi_objective() -> MultiObjectiveOptimizer:
    """获取全局多目标优化器。"""
    global _multi_objective
    if _multi_objective is None:
        _multi_objective = MultiObjectiveOptimizer()
    return _multi_objective


def evaluate_metrics(metrics: dict[str, float]) -> dict[str, Any]:
    """评估指标（便捷函数）。"""
    optimizer = get_multi_objective()
    return optimizer.evaluate_strategy(metrics)


def select_best(strategies: list[dict[str, Any]]) -> dict[str, Any]:
    """选择最佳策略（便捷函数）。"""
    optimizer = get_multi_objective()
    return optimizer.select_best_strategy(strategies)
