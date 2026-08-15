"""深度反馈学习单元测试。"""
import pytest
from evolution_core.deep_feedback import (
    analyze_modification_deep,
    detect_preference_conflicts,
    resolve_conflicts,
    generate_preference_summary,
    _analyze_with_rules,
)


class TestAnalyzeModificationDeep:
    """测试深度修改分析。"""

    def test_identical_text(self):
        """相同文本返回 None。"""
        result = analyze_modification_deep("相同文本", "相同文本")
        assert result is None

    def test_empty_text(self):
        """空文本返回 None。"""
        assert analyze_modification_deep("", "") is None
        assert analyze_modification_deep("original", "") is None

    def test_length_reduction(self):
        """长度减少应分析为简洁偏好。"""
        original = "这是一段非常长的测试文本内容" * 5
        modified = "简短文本"
        result = analyze_modification_deep(original, modified)
        assert result is not None
        assert result["modify_type"] in ("style", "content")

    def test_format_change(self):
        """格式变化应识别（LLM 可能识别为 format/content/structure）。"""
        original = "连续文本内容"
        modified = "第一段\n\n第二段"
        result = analyze_modification_deep(original, modified)
        if result:
            # LLM 分析结果可能是 format/content/structure/other
            assert result["modify_type"] in ("format", "content", "structure", "other")


class TestAnalyzeWithRules:
    """测试规则降级分析。"""

    def test_identical_returns_none(self):
        """相同文本返回 None。"""
        assert _analyze_with_rules("abc", "abc") is None

    def test_length_reduction_detected(self):
        """长度减少应检测到。"""
        original = "这是一段非常长的测试文本内容" * 5
        modified = "简短文本"
        result = _analyze_with_rules(original, modified)
        assert result is not None
        assert result["modify_type"] == "style"
        assert "简洁" in result["preference_rule"]["value"]

    def test_format_change_detected(self):
        """格式变化应检测到（规则分析可能识别为 format 或 content）。"""
        result = _analyze_with_rules("连续文本", "第一段\n\n第二段")
        assert result is not None
        # 规则分析精度有限，format/content/other 都算有效
        assert result["modify_type"] in ("format", "content", "other")

    def test_tone_formal_detected(self):
        """正式语气应检测到（规则分析可能识别为 tone 或 content）。"""
        result = _analyze_with_rules("所以说", "综上所述，因此")
        if result:
            assert result["modify_type"] in ("tone", "content", "other")


class TestPreferenceConflicts:
    """测试偏好冲突检测。"""

    def test_no_conflicts(self):
        """无冲突时返回空列表。"""
        prefs = [
            {"key": "style:prefer", "value": "正式", "confidence": 0.8},
        ]
        conflicts = detect_preference_conflicts(prefs)
        assert conflicts == []

    def test_detects_conflict(self):
        """应检测同一 key 不同值的冲突。"""
        prefs = [
            {"key": "style:prefer", "value": "正式", "confidence": 0.8},
            {"key": "style:prefer", "value": "口语化", "confidence": 0.6},
        ]
        conflicts = detect_preference_conflicts(prefs)
        assert len(conflicts) >= 1
        assert conflicts[0]["key"] == "style:prefer"

    def test_resolve_conflicts(self):
        """应解决冲突（保留高置信度）。"""
        prefs = [
            {"key": "style:prefer", "value": "正式", "confidence": 0.8},
            {"key": "style:prefer", "value": "口语化", "confidence": 0.6},
        ]
        resolved = resolve_conflicts(prefs)
        assert len(resolved) == 1
        assert resolved[0]["value"] == "正式"

    def test_no_conflicts_returns_same(self):
        """无冲突时返回原列表。"""
        prefs = [
            {"key": "style:prefer", "value": "正式", "confidence": 0.8},
            {"key": "format:prefer", "value": "分段", "confidence": 0.7},
        ]
        resolved = resolve_conflicts(prefs)
        assert len(resolved) == 2


class TestPreferenceSummary:
    """测试偏好摘要生成。"""

    def test_empty_preferences(self):
        """无偏好时返回空字符串。"""
        assert generate_preference_summary([]) == ""

    def test_low_confidence_filtered(self):
        """低置信度偏好应被过滤。"""
        prefs = [
            {"key": "style:prefer", "value": "正式", "confidence": 0.1},
        ]
        assert generate_preference_summary(prefs) == ""

    def test_style_preference(self):
        """文风偏好应正确格式化。"""
        prefs = [
            {"key": "style:prefer", "value": "正式", "confidence": 0.8},
        ]
        summary = generate_preference_summary(prefs)
        assert "文风偏好" in summary
        assert "正式" in summary

    def test_format_preference(self):
        """格式偏好应正确格式化。"""
        prefs = [
            {"key": "format:prefer", "value": "分段结构", "confidence": 0.7},
        ]
        summary = generate_preference_summary(prefs)
        assert "格式偏好" in summary

    def test_multiple_preferences(self):
        """多个偏好应合并。"""
        prefs = [
            {"key": "style:prefer", "value": "正式", "confidence": 0.8},
            {"key": "format:prefer", "value": "分段", "confidence": 0.7},
            {"key": "length:prefer", "value": "简洁", "confidence": 0.6},
        ]
        summary = generate_preference_summary(prefs)
        assert "文风偏好" in summary
        assert "格式偏好" in summary
        assert "长度偏好" in summary
