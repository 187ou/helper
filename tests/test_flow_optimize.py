"""流程优化模块单元测试。"""
import pytest
from evolution_core.flow_optimize import (
    optimize,
    detect_duplicate,
    _merge_synonym_steps,
    _detect_parallelizable,
    _remove_redundant_steps,
    _canonicalize,
)


class TestCanonicalize:
    """测试步骤名规范化。"""

    def test_synonym_normalization(self):
        """同义词应归一化为同一规范形式。"""
        assert _canonicalize("收集数据") == "收集"
        assert _canonicalize("采集信息") == "收集"
        assert _canonicalize("获取资料") == "收集"

    def test_same_canonical_form(self):
        """不同同义词应产生相同的规范形式。"""
        assert _canonicalize("生成报告") == _canonicalize("创建文档")
        assert _canonicalize("检查数据") == _canonicalize("验证结果")

    def test_unknown_word_unchanged(self):
        """未知词保持不变（取前2字符）。"""
        result = _canonicalize("xyz步骤")
        assert result == "xyz步骤"[:2]


class TestMergeSynonymSteps:
    """测试语义合并。"""

    def test_merge_synonym_steps(self):
        """同义步骤应合并。"""
        steps = [
            {"name": "收集数据", "description": "获取数据"},
            {"name": "采集信息", "description": "从数据库采集"},
        ]
        result = _merge_synonym_steps(steps)
        assert len(result) == 1
        assert result[0]["name"] == "收集数据"

    def test_keep_different_steps(self):
        """不同步骤应保留。"""
        steps = [
            {"name": "理解需求", "description": "分析需求"},
            {"name": "生成报告", "description": "输出结果"},
        ]
        result = _merge_synonym_steps(steps)
        assert len(result) == 2

    def test_merge_descriptions(self):
        """合并时描述应拼接。"""
        steps = [
            {"name": "收集数据", "description": "获取数据"},
            {"name": "采集信息", "description": "从数据库采集"},
        ]
        result = _merge_synonym_steps(steps)
        assert "获取数据" in result[0]["description"]
        assert "从数据库采集" in result[0]["description"]


class TestDetectParallelizable:
    """测试并行检测。"""

    def test_parallel_keyword_detection(self):
        """含并行关键词的步骤应标记为 parallel。"""
        steps = [
            {"name": "理解需求", "description": "分析需求", "step_type": "action"},
            {"name": "统计数据", "description": "统计", "step_type": "action"},
            {"name": "汇总输出", "description": "输出", "step_type": "action"},
        ]
        result = _detect_parallelizable(steps)
        assert result[1]["step_type"] == "parallel"

    def test_first_last_unchanged(self):
        """首尾步骤不应被标记为并行。"""
        steps = [
            {"name": "收集信息", "description": "采集", "step_type": "action"},
            {"name": "汇总输出", "description": "输出", "step_type": "action"},
        ]
        result = _detect_parallelizable(steps)
        assert result[0]["step_type"] == "action"
        assert result[1]["step_type"] == "action"


class TestRemoveRedundantSteps:
    """测试冗余步骤移除。"""

    def test_remove_waiting_steps(self):
        """等待确认类步骤应被移除。"""
        steps = [
            {"name": "理解需求", "description": "分析"},
            {"name": "等待确认", "description": "等确认"},
            {"name": "生成报告", "description": "输出"},
        ]
        result = _remove_redundant_steps(steps)
        assert len(result) == 2
        assert all(s["name"] != "等待确认" for s in result)

    def test_keep_valid_steps(self):
        """有效步骤应保留。"""
        steps = [
            {"name": "理解需求", "description": "分析"},
            {"name": "生成报告", "description": "输出"},
        ]
        result = _remove_redundant_steps(steps)
        assert len(result) == 2


class TestDetectDuplicate:
    """测试重复检测。"""

    def test_detect_synonym_duplicates(self):
        """同义词步骤应被检测为重复。"""
        steps = [
            {"name": "收集数据"},
            {"name": "采集信息"},  # 与第一步同义
            {"name": "生成报告"},
        ]
        duplicates = detect_duplicate(steps)
        assert 1 in duplicates

    def test_no_duplicates(self):
        """无重复时返回空列表。"""
        steps = [
            {"name": "理解需求"},
            {"name": "生成报告"},
            {"name": "汇总输出"},
        ]
        assert detect_duplicate(steps) == []


class TestOptimize:
    """测试完整优化流程。"""

    def test_short_steps_unchanged(self):
        """步骤数 <= 2 时直接返回。"""
        steps = [{"name": "理解"}, {"name": "输出"}]
        assert optimize(steps) == steps

    def test_rule_optimization_reduces_steps(self):
        """规则优化应减少步骤数。"""
        steps = [
            {"name": "理解需求", "description": "分析", "step_type": "action"},
            {"name": "收集数据", "description": "获取", "step_type": "action"},
            {"name": "采集信息", "description": "从数据库采集", "step_type": "action"},
            {"name": "生成报告", "description": "输出", "step_type": "action"},
            {"name": "等待确认", "description": "等确认", "step_type": "action"},
        ]
        result = optimize(steps)
        # 合并同义词 + 移除冗余后应少于 5 步
        assert len(result) < 5
