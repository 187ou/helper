"""冷启动策略单元测试。"""
import pytest
from evolution_core.cold_start import (
    get_default_template,
    is_fast_learn_phase,
    get_fast_learn_boost,
    get_cold_start_guidance,
    get_recommended_steps,
    get_all_default_templates,
    add_default_template,
    DEFAULT_TEMPLATES,
    FAST_LEARN_CONFIG,
)


class TestDefaultTemplates:
    """测试默认模板。"""

    def test_get_weekly_template(self):
        """应能获取周报模板。"""
        steps = get_default_template("生成本周周报")
        assert steps is not None
        assert len(steps) >= 3
        assert all("name" in s for s in steps)

    def test_get_monthly_template(self):
        """应能获取月报模板。"""
        steps = get_default_template("月度工作总结")
        assert steps is not None
        assert len(steps) >= 3

    def test_get_meeting_template(self):
        """应能获取会议纪要模板。"""
        steps = get_default_template("整理会议纪要")
        assert steps is not None
        assert len(steps) >= 3

    def test_no_match_returns_none(self):
        """无匹配时返回 None（使用无关键词的文本）。"""
        # "xyzabc" 不含任何默认模板的关键词
        steps = get_default_template("xyzabc")
        assert steps is None

    def test_empty_text_returns_none(self):
        """空文本返回 None。"""
        assert get_default_template("") is None
        assert get_default_template(None) is None

    def test_all_templates_have_required_fields(self):
        """所有默认模板应有必需字段。"""
        templates = get_all_default_templates()
        assert len(templates) > 0
        for name, template in templates.items():
            assert "keywords" in template
            assert "steps" in template
            assert len(template["keywords"]) > 0
            assert len(template["steps"]) > 0

    def test_add_custom_template(self):
        """应能添加自定义模板。"""
        add_default_template(
            "测试模板",
            ["测试", "test"],
            [{"name": "步骤1", "description": "测试"}],
            priority=10
        )
        assert "测试模板" in DEFAULT_TEMPLATES
        steps = get_default_template("这是一个测试任务")
        assert steps is not None


class TestFastLearnPhase:
    """测试快速学习期判断。"""

    def test_first_task_is_fast_learn(self):
        """首次任务应处于快速学习期。"""
        assert is_fast_learn_phase(0) is True

    def test_under_threshold_is_fast_learn(self):
        """低于阈值应处于快速学习期。"""
        assert is_fast_learn_phase(3) is True

    def test_at_threshold_is_normal(self):
        """达到阈值应进入正常期。"""
        assert is_fast_learn_phase(FAST_LEARN_CONFIG["fast_learn_threshold"]) is False

    def test_above_threshold_is_normal(self):
        """超过阈值应为正常期。"""
        assert is_fast_learn_phase(10) is False

    def test_boost_factor(self):
        """提权倍率应大于 1。"""
        assert get_fast_learn_boost() > 1.0


class TestColdStartGuidance:
    """测试冷启动引导。"""

    def test_first_time_guidance(self):
        """首次使用应给出引导。"""
        guidance = get_cold_start_guidance("测试", 0)
        assert guidance["phase"] == "first_time"
        assert guidance["use_default_template"] is True
        assert guidance["collect_feedback"] is True
        assert len(guidance["message"]) > 0

    def test_fast_learn_guidance(self):
        """快速学习期应给出引导。"""
        guidance = get_cold_start_guidance("测试", 2)
        assert guidance["phase"] == "fast_learn"
        assert guidance["use_default_template"] is True

    def test_normal_guidance(self):
        """正常期不需要引导。"""
        guidance = get_cold_start_guidance("测试", 10)
        assert guidance["phase"] == "normal"
        assert guidance["use_default_template"] is False


class TestGetRecommendedSteps:
    """测试推荐步骤（冷启动感知）。"""

    def test_first_time_uses_default(self):
        """首次使用应返回默认模板或演化推荐。"""
        steps, source = get_recommended_steps("生成周报", "work")
        assert steps is not None
        # 冷启动期优先 default，但有历史数据时可能返回 evolution
        assert source in ("default", "evolution")

    def test_empty_text_returns_none(self):
        """空文本返回 None。"""
        steps, source = get_recommended_steps("", "work")
        assert steps is None
        assert source == "none"

    def test_unknown_task_returns_default(self):
        """未知任务应返回默认模板（如果有匹配的）。"""
        steps, source = get_recommended_steps("报销整理", "work")
        # 报销有默认模板
        assert steps is not None
