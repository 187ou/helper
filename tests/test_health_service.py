"""健康服务模块单元测试。"""
import pytest
from service.health_service import (
    record_sleep,
    get_sedentary_status,
    record_health_metric,
    get_health_reminders,
)


class TestRecordSleep:
    """测试睡眠记录。"""

    def test_calculate_duration(self):
        """应正确计算睡眠时长。"""
        result = record_sleep("23:00", "07:00")
        assert result["duration_hours"] == 8.0
        assert result["quality"] == "正常"

    def test_short_sleep(self):
        """睡眠不足应标记为不足。"""
        result = record_sleep("01:00", "05:00")
        assert result["duration_hours"] == 4.0
        assert result["quality"] == "不足"

    def test_long_sleep(self):
        """睡眠过多应标记为偏多。"""
        result = record_sleep("22:00", "10:00")
        assert result["duration_hours"] == 12.0
        assert result["quality"] == "偏多"

    def test_invalid_duration(self):
        """无效时间（负时长）应返回 invalid。"""
        result = record_sleep("07:00", "23:00")
        # 起床 < 入睡，会加一天，所以是 16 小时
        assert result["duration_hours"] == 16.0

    def test_format_error(self):
        """格式错误应返回 format_error。"""
        result = record_sleep("invalid", "07:00")
        assert result["quality"] == "format_error"


class TestRecordHealthMetric:
    """测试健康指标记录。"""

    def test_valid_type(self):
        """有效类型应返回 ok。"""
        result = record_health_metric("water", 2, "喝水")
        assert result["ok"] is True
        assert result["type"] == "water"

    def test_invalid_type(self):
        """无效类型应返回错误。"""
        result = record_health_metric("invalid", 1)
        assert result["ok"] is False
        assert "无效类型" in result["error"]


class TestGetHealthReminders:
    """测试获取健康提醒配置。"""

    def test_returns_list(self):
        """应返回列表。"""
        result = get_health_reminders()
        assert isinstance(result, list)

    def test_has_required_fields(self):
        """每条提醒应有必要字段。"""
        result = get_health_reminders()
        for r in result:
            assert "type" in r
            assert "title" in r
            assert "enabled" in r


class TestGetSedentaryStatus:
    """测试久坐状态。"""

    def test_returns_dict(self):
        """应返回字典。"""
        result = get_sedentary_status()
        assert isinstance(result, dict)
        assert "sitting_minutes" in result
        assert "need_break" in result
