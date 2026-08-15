"""任务管理服务单元测试（测试纯逻辑部分）。"""
import pytest

from service.task_service import (
    VALID_STATUSES,
    VALID_PRIORITIES,
    VALID_TYPES,
    TRANSITIONS,
    _build_dag_from_steps,
    _row_to_task,
)


class TestConstants:
    """测试常量定义完整性。"""

    def test_all_statuses_defined(self):
        """所有状态应在定义中。"""
        assert "todo" in VALID_STATUSES
        assert "doing" in VALID_STATUSES
        assert "done" in VALID_STATUSES
        assert "archived" in VALID_STATUSES
        assert "shelved" in VALID_STATUSES

    def test_all_priorities_defined(self):
        """所有优先级应在定义中。"""
        assert "high" in VALID_PRIORITIES
        assert "medium" in VALID_PRIORITIES
        assert "low" in VALID_PRIORITIES

    def test_all_types_defined(self):
        """所有类型应在定义中。"""
        assert "work" in VALID_TYPES
        assert "life" in VALID_TYPES
        assert "health" in VALID_TYPES
        assert "mix" in VALID_TYPES

    def test_transitions_defined(self):
        """所有状态应有流转定义。"""
        for status in VALID_STATUSES:
            assert status in TRANSITIONS


class TestStatusTransitions:
    """测试状态流转规则。"""

    def test_todo_can_go_to_doing(self):
        """待办可以转到进行中。"""
        assert "doing" in TRANSITIONS["todo"]

    def test_todo_cannot_go_to_archived(self):
        """待办不能直接归档。"""
        assert "archived" not in TRANSITIONS["todo"]

    def test_archived_is_terminal(self):
        """归档是终态，无任何流出。"""
        assert len(TRANSITIONS["archived"]) == 0

    def test_shelved_can_recover(self):
        """搁置后可恢复。"""
        assert "todo" in TRANSITIONS["shelved"]
        assert "doing" in TRANSITIONS["shelved"]

    def test_done_can_go_back_to_doing(self):
        """完成后可以返工。"""
        assert "doing" in TRANSITIONS["done"]


class TestBuildDagFromSteps:
    """测试 DAG 构建。"""

    def test_build_basic_dag(self):
        """应从步骤列表构建正确的 DAG。"""
        steps = [
            {"index": 0, "name": "步骤1", "desc": "描述1"},
            {"index": 1, "name": "步骤2", "desc": "描述2"},
            {"index": 2, "name": "步骤3", "desc": "描述3"},
        ]
        dag = _build_dag_from_steps(steps)
        assert len(dag["nodes"]) == 3
        assert len(dag["edges"]) == 2  # 3 步有 2 条边

    def test_edges_connect_sequentially(self):
        """边应按顺序连接。"""
        steps = [
            {"index": 0, "name": "步骤1"},
            {"index": 1, "name": "步骤2"},
        ]
        dag = _build_dag_from_steps(steps)
        assert dag["edges"][0] == {"source": "step_0", "target": "step_1"}

    def test_single_step_no_edges(self):
        """单步骤无边。"""
        steps = [{"index": 0, "name": "步骤1"}]
        dag = _build_dag_from_steps(steps)
        assert len(dag["nodes"]) == 1
        assert len(dag["edges"]) == 0

    def test_empty_steps(self):
        """空步骤返回空 DAG。"""
        dag = _build_dag_from_steps([])
        assert len(dag["nodes"]) == 0
        assert len(dag["edges"]) == 0


class TestRowToTask:
    """测试数据库行转任务字典。"""

    def test_parse_json_steps(self):
        """应解析 JSON 格式的 task_steps。"""
        row = {
            "id": 1, "task_content": "测试",
            "task_steps": '[{"name": "步骤1", "index": 0}]',
        }
        result = _row_to_task(row)
        assert isinstance(result["task_steps"], list)
        assert len(result["task_steps"]) == 1

    def test_empty_steps_defaults_to_list(self):
        """空 steps 应默认为空列表。"""
        row = {"id": 1, "task_content": "测试", "task_steps": ""}
        result = _row_to_task(row)
        assert result["task_steps"] == []

    def test_none_steps_defaults_to_list(self):
        """None steps 应默认为空列表。"""
        row = {"id": 1, "task_content": "测试", "task_steps": None}
        result = _row_to_task(row)
        assert result["task_steps"] == []
