"""DAG 动态任务图构建（LangGraph 真实 DAG，支持并行节点）+ 可视化 DAG 生成。"""
import logging
from typing import Any

from agent_core.task_parser import TaskStep

logger = logging.getLogger(__name__)


def build_dag(steps: list[dict]) -> dict[str, Any]:
    """为可视化构建完整 DAG（节点 + 边），正确处理并行节点的 fan-out/fan-in。

    与 LangGraph 执行图逻辑一致：
    - 连续的 parallel 节点作为一组，从共同前驱 fan-out
    - 并行组结束后 fan-in 到下一个串行节点

    Args:
        steps: 步骤列表，每项需含 index/name，可选 desc/description/step_type/type/status

    Returns:
        {"nodes": [{"id", "label", "desc", "status", "step_type"}, ...],
         "edges": [{"source", "target"}, ...]}

    示例:
        >>> build_dag([
        ...     {"index": 0, "name": "理解需求", "step_type": "action"},
        ...     {"index": 1, "name": "收集数据", "step_type": "parallel"},
        ...     {"index": 2, "name": "读取文件", "step_type": "parallel"},
        ...     {"index": 3, "name": "汇总输出", "step_type": "action"},
        ... ])
        # edges: 0→1, 0→2, 1→3, 2→3
    """
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []

    for step in steps:
        nodes.append({
            "id": f"step_{step['index']}",
            "label": step.get("name", f"步骤{step['index']}"),
            "desc": step.get("description", step.get("desc", "")),
            "status": step.get("status", "pending"),
            "step_type": step.get("step_type", step.get("type", "action")),
        })

    # 边生成：分组处理，parallel 组 fan-out/fan-in
    prev_sources: list[str] = []  # 上一组发出连接的节点 id 列表
    i = 0
    n = len(steps)

    while i < n:
        if steps[i].get("step_type", steps[i].get("type", "action")) == "parallel":
            # 收集连续 parallel 节点
            parallel_group: list[str] = []
            while i < n and steps[i].get("step_type", steps[i].get("type", "action")) == "parallel":
                parallel_group.append(f"step_{steps[i]['index']}")
                i += 1

            # Fan-out: 前驱 → 每个并行节点
            for src in prev_sources:
                for nid in parallel_group:
                    edges.append({"source": src, "target": nid})

            # Fan-in: 每个并行节点 → 后继
            if i < n:
                next_node = f"step_{steps[i]['index']}"
                for nid in parallel_group:
                    edges.append({"source": nid, "target": next_node})
                # 后继已被连接，下一轮从它继续（跳过重复处理）
                prev_sources = [next_node]
                i += 1
            else:
                # parallel 在末尾，无后继
                prev_sources = parallel_group
        else:
            # action 节点：串行连接
            node_name = f"step_{steps[i]['index']}"
            for src in prev_sources:
                edges.append({"source": src, "target": node_name})
            prev_sources = [node_name]
            i += 1

    return {"nodes": nodes, "edges": edges}


def build_graph(steps: list[TaskStep]):
    """根据步骤列表构建 LangGraph StateGraph。

    - 无依赖的 parallel 节点从同一分叉点并行出发
    - action 节点线性串行
    """
    try:
        from langgraph.graph import StateGraph, START, END
    except ImportError:
        logger.warning("LangGraph 未安装，返回 None")
        return None

    from typing import TypedDict, Annotated
    import operator

    def _sum_float(a: float, b: float) -> float:
        return a + b

    def _max_int(a: int, b: int) -> int:
        return max(a, b)

    class AgentState(TypedDict):
        task_text: str
        logs: Annotated[list[str], operator.add]
        completed_steps: Annotated[list[int], operator.add]
        step_results: Annotated[list[dict], operator.add]
        cost_time: Annotated[float, _sum_float]
        current_step: Annotated[int, _max_int]

    def make_node(step: TaskStep):
        def node_fn(state: AgentState) -> AgentState:
            # 防死循环：如果本节点已执行过，直接返回空更新
            if step.index in state.get("completed_steps", []):
                logger.warning("[节点 %d] %s 已执行过，跳过（防死循环）", step.index, step.name)
                return {}
            from agent_core.node_executor import execute_node
            result = execute_node(step, dict(state))
            return {
                "logs": result.get("logs", []),
                "completed_steps": result.get("completed_steps", []),
                "step_results": result.get("step_results", []),
                "cost_time": result.get("cost_time", 0),
                "current_step": step.index,
            }
        node_fn.__name__ = f"step_{step.index}_{step.name}"
        return node_fn

    graph = StateGraph(AgentState)

    # 添加所有节点
    for step in steps:
        graph.add_node(f"step_{step.index}", make_node(step))

    # 构建边：parallel 节点并行，action 节点串行
    # 简化策略：第一个节点从 START 出发，后续节点根据 step_type 决定
    if not steps:
        graph.add_edge(START, END)
        return graph.compile()

    # 分组：连续的 parallel 节点为一组，action 节点单独串行
    prev_end = START
    i = 0
    while i < len(steps):
        step = steps[i]
        if step.step_type == "parallel":
            # 收集连续 parallel 节点，全部从 prev_end 并行出发
            parallel_group = []
            while i < len(steps) and steps[i].step_type == "parallel":
                parallel_group.append(f"step_{steps[i].index}")
                i += 1
            for node_name in parallel_group:
                graph.add_edge(prev_end, node_name)
            # 并行节点汇聚到 END 或下一个串行节点
            # LangGraph 多入边自动汇聚（需 LangGraph 支持，这里简化为汇聚到 END 前的虚拟汇聚）
            # 实际：parallel 节点后接下一个 action 或 END
            if i < len(steps):
                next_node = f"step_{steps[i].index}"
                for node_name in parallel_group:
                    graph.add_edge(node_name, next_node)
                prev_end = next_node
            else:
                for node_name in parallel_group:
                    graph.add_edge(node_name, END)
        else:
            node_name = f"step_{step.index}"
            graph.add_edge(prev_end, node_name)
            prev_end = node_name
            i += 1

    graph.add_edge(prev_end, END)

    logger.info("DAG 构建完成，共 %d 个节点", len(steps))
    return graph.compile()
