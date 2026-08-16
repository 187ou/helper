"""记忆模块错误处理：统一的异常处理策略。

解决缺口：111 个异常处理器吞掉了大量错误，调试困难。

策略：
1. 边界异常（输入验证）→ 返回默认值，不记录
2. 数据异常（DB 读取失败）→ 记录 warning，返回安全默认值
3. 逻辑异常（不应发生的错误）→ 记录 error，抛出
4. 外部依赖异常（Chroma/LLM 不可用）→ 记录 warning，降级处理
"""
import logging
import functools
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def safe_memory_operation(default_return: Any = None,
                          log_level: str = "warning",
                          reraise: bool = False):
    """记忆操作的安全装饰器（统一异常处理）。

    Args:
        default_return: 异常时的返回值
        log_level: 日志级别 (debug/warning/error)
        reraise: 是否重新抛出异常

    Usage:
        @safe_memory_operation(default_return=[])
        def get_related_memories(...):
            ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                msg = f"{func.__name__} 失败: {type(e).__name__}: {str(e)[:100]}"

                if log_level == "debug":
                    logger.debug(msg)
                elif log_level == "warning":
                    logger.warning(msg)
                elif log_level == "error":
                    logger.error(msg, exc_info=True)

                if reraise:
                    raise

                return default_return
        return wrapper
    return decorator


class MemoryError(Exception):
    """记忆模块基础异常。"""
    pass


class MemoryNotFoundError(MemoryError):
    """记忆不存在。"""
    pass


class MemoryConflictError(MemoryError):
    """记忆冲突。"""
    pass


class MemoryStorageError(MemoryError):
    """存储失败。"""
    pass
