"""请求上下文：task_id 追踪。"""
import uuid
from contextvars import ContextVar

# 每个协程独立的 task_id
task_id_ctx: ContextVar[str] = ContextVar("task_id", default="")


def new_task_id() -> str:
    """生成新的 task_id（8位短码）。"""
    return uuid.uuid4().hex[:8]


def get_task_id() -> str:
    """获取当前上下文的 task_id。"""
    return task_id_ctx.get()


def set_task_id(task_id: str) -> None:
    """设置当前上下文的 task_id。"""
    task_id_ctx.set(task_id)
