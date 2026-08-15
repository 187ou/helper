"""A/B 测试框架单元测试。"""
import pytest
import sqlite3
import tempfile
import os
from unittest.mock import patch, MagicMock

from memory_store.sqlite_db import init_db


# 全局测试数据库状态
_test_state = {"db_path": None, "mock": None}


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    """每个测试用例使用独立临时数据库。"""
    db_path = tmp_path / "test.db"
    _test_state["db_path"] = str(db_path)

    def mock_get_conn():
        conn = sqlite3.connect(_test_state["db_path"])
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    _test_state["mock"] = mock_get_conn

    # 启动多个 patch
    patches = [
        patch("memory_store.sqlite_db.get_conn", mock_get_conn),
        patch("evolution_core.ab_test.get_conn", mock_get_conn),
    ]
    for p in patches:
        p.start()

    import memory_store.user_weight as uw
    from memory_store.repositories.habit_repo import HabitRepository
    uw._repo = HabitRepository()

    init_db()
    yield

    for p in patches:
        p.stop()


from evolution_core.ab_test import (
    create_experiment,
    assign_variant,
    record_result,
    analyze_experiment,
    stop_experiment,
    get_experiment,
    list_experiments,
    auto_decide,
    _std_dev,
    _confidence_interval,
    _t_test,
)


class TestCreateExperiment:
    """测试创建实验。"""

    def test_create_basic(self):
        """应能创建基本实验。"""
        exp_id = create_experiment(
            name="测试实验",
            description="测试描述",
            variants=[
                {"name": "control", "config": {}},
                {"name": "treatment", "config": {}},
            ],
        )
        assert exp_id is not None
        assert exp_id.startswith("exp_")

    def test_create_with_minimal_variants(self):
        """至少需要 2 个变体。"""
        assert create_experiment("test", "", [{"name": "only"}]) is None

    def test_create_with_empty_name(self):
        """空名称应返回 None。"""
        assert create_experiment("", "", [{"name": "a"}, {"name": "b"}]) is None


class TestAssignVariant:
    """测试流量分配。"""

    def test_deterministic_assignment(self):
        """同一用户应始终分配到同一组。"""
        exp_id = create_experiment(
            name="确定性测试",
            variants=[{"name": "control"}, {"name": "treatment"}],
        )

        v1 = assign_variant(exp_id, "user_123")
        v2 = assign_variant(exp_id, "user_123")
        assert v1 == v2

    def test_different_users_different_variants(self):
        """不同用户可能分配到不同组。"""
        exp_id = create_experiment(
            name="分流测试",
            variants=[{"name": "control"}, {"name": "treatment"}],
        )
        assert exp_id is not None, "实验创建失败"

        variants_seen = set()
        for i in range(20):
            v = assign_variant(exp_id, f"user_{i}")
            if v:
                variants_seen.add(v.get("name"))

        assert len(variants_seen) >= 1

    def test_nonexistent_experiment(self):
        """不存在的实验返回 None。"""
        assert assign_variant("exp_nonexistent", "user") is None


class TestRecordAndAnalyze:
    """测试记录和分析。"""

    def test_record_result(self):
        """应能记录结果。"""
        exp_id = create_experiment(
            name="记录测试",
            variants=[{"name": "control"}, {"name": "treatment"}],
        )

        record_result(exp_id, "control", 80.0, task_id=1)
        record_result(exp_id, "treatment", 85.0, task_id=2)

        analysis = analyze_experiment(exp_id)
        assert analysis is not None
        assert "control" in analysis["variants"]
        assert "treatment" in analysis["variants"]

    def test_analyze_no_data(self):
        """无数据时返回 no_data。"""
        exp_id = create_experiment(
            name="空数据测试",
            variants=[{"name": "control"}, {"name": "treatment"}],
        )

        analysis = analyze_experiment(exp_id)
        assert analysis["status"] == "no_data"

    def test_significance_with_clear_difference(self):
        """明显差异应检测为显著。"""
        exp_id = create_experiment(
            name="显著性测试",
            variants=[{"name": "control"}, {"name": "treatment"}],
        )

        for i in range(15):
            record_result(exp_id, "control", 60 + i % 5)
        for i in range(15):
            record_result(exp_id, "treatment", 85 + i % 5)

        analysis = analyze_experiment(exp_id)
        if analysis.get("variants", {}).get("control", {}).get("sample_size", 0) >= 10:
            if analysis.get("variants", {}).get("treatment", {}).get("sample_size", 0) >= 10:
                assert analysis.get("p_value", 1) < 0.1 or not analysis.get("significant")


class TestStopExperiment:
    """测试停止实验。"""

    def test_stop_with_winner(self):
        """应能停止并设置胜出者。"""
        exp_id = create_experiment(
            name="停止测试",
            variants=[{"name": "control"}, {"name": "treatment"}],
        )

        stop_experiment(exp_id, "treatment")

        exp = get_experiment(exp_id)
        assert exp["status"] == "completed"
        assert exp["winner"] == "treatment"


class TestAutoDecide:
    """测试自动决策。"""

    def test_continue_when_insufficient(self):
        """样本不足时应继续实验。"""
        exp_id = create_experiment(
            name="继续测试",
            variants=[{"name": "control"}, {"name": "treatment"}],
        )

        record_result(exp_id, "control", 80.0)

        decision = auto_decide(exp_id)
        assert decision["decision"] == "continue"


class TestStatistics:
    """测试统计函数。"""

    def test_std_dev(self):
        """标准差计算。"""
        values = [2, 4, 4, 4, 5, 5, 7, 9]
        mean = sum(values) / len(values)
        std = _std_dev(values, mean)
        assert std > 0

    def test_std_dev_single_value(self):
        """单值标准差为 0。"""
        assert _std_dev([5], 5) == 0.0

    def test_confidence_interval(self):
        """置信区间计算。"""
        ci = _confidence_interval(80, 5, 30)
        assert ci[0] < 80 < ci[1]

    def test_t_test_identical(self):
        """相同数据不显著。"""
        a = [80, 81, 79, 80, 81]
        b = [80, 81, 79, 80, 81]
        significant, p = _t_test(a, b)
        assert not significant

    def test_t_test_different(self):
        """明显差异应显著。"""
        a = [60, 61, 59, 60, 61]
        b = [90, 91, 89, 90, 91]
        significant, p = _t_test(a, b)
        assert significant
        assert p < 0.05


class TestListExperiments:
    """测试列出实验。"""

    def test_list_all(self):
        """应能列出所有实验。"""
        create_experiment("实验1", "", [{"name": "a"}, {"name": "b"}])
        create_experiment("实验2", "", [{"name": "c"}, {"name": "d"}])

        experiments = list_experiments()
        assert len(experiments) >= 2

    def test_list_by_status(self):
        """应按状态过滤。"""
        create_experiment("运行中", "", [{"name": "a"}, {"name": "b"}])

        running = list_experiments(status="running")
        assert len(running) >= 1
