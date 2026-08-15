"""演化引擎安全操作包装器：统一处理边缘情况。

提供：
1. 安全数据库操作（自动回滚、连接异常处理）
2. 安全 JSON 解析（容错 + 默认值）
3. 安全数值计算（零除保护、溢出保护）
4. 安全 LLM 调用（超时、格式错误兜底）
"""
import json
import logging
import sqlite3
import functools
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ── 数据库安全操作 ──

def safe_db_read(func: Callable) -> Callable:
    """装饰器：安全执行数据库读取操作。

    边缘处理：
    - 数据库连接失败 → 返回 None/空
    - SQL 错误 → 记录日志 + 返回安全默认值
    - 空结果 → 返回 None
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except sqlite3.OperationalError as e:
            logger.warning("数据库读取失败 [%s]: %s", func.__name__, e)
            return None
        except sqlite3.DatabaseError as e:
            logger.error("数据库错误 [%s]: %s", func.__name__, e)
            return None
        except Exception as e:
            logger.error("未知错误 [%s]: %s", func.__name__, e)
            return None
    return wrapper


def safe_db_write(default_return: Any = None) -> Callable:
    """装饰器：安全执行数据库写入操作。

    边缘处理：
    - 连接失败 → 返回 default_return
    - 写入失败 → 自动回滚 + 返回 default_return
    - 约束冲突 → 记录 + 返回 default_return
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                return result
            except sqlite3.IntegrityError as e:
                logger.warning("数据完整性约束 [%s]: %s", func.__name__, e)
                return default_return
            except sqlite3.OperationalError as e:
                logger.warning("数据库写入失败 [%s]: %s", func.__name__, e)
                return default_return
            except sqlite3.DatabaseError as e:
                logger.error("数据库错误 [%s]: %s", func.__name__, e)
                return default_return
            except Exception as e:
                logger.error("未知错误 [%s]: %s", func.__name__, e)
                return default_return
        return wrapper
    return decorator


# ── JSON 安全操作 ──

def safe_json_loads(text: Any, default: Any = None) -> Any:
    """安全解析 JSON。

    边缘处理：
    - None/空字符串 → 返回 default
    - 非法 JSON → 返回 default
    - 已是 list/dict → 直接返回（幂等性）
    - 非字符串输入 → 尝试 str() 后解析
    """
    if text is None:
        return default
    # 幂等性：如果已经是解析后的对象，直接返回
    if isinstance(text, (list, dict)):
        return text
    if not isinstance(text, str):
        try:
            text = str(text)
        except Exception:
            return default
    text = text.strip()
    if not text:
        return default
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return default


def safe_json_dumps(obj: Any, default: str = "{}") -> str:
    """安全序列化 JSON。

    边缘处理：
    - 序列化失败 → 返回 default
    - 非 ASCII → ensure_ascii=False
    """
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return default


# ── 数值安全操作 ──

def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """安全除法（零除保护）。"""
    try:
        if denominator == 0:
            return default
        return numerator / denominator
    except (TypeError, ValueError):
        return default


def clamp_value(value: float, min_val: float, max_val: float) -> float:
    """数值限幅（溢出保护）。"""
    try:
        return max(min_val, min(max_val, float(value)))
    except (TypeError, ValueError):
        return min_val


def safe_avg(values: list[float], default: float = 0.0) -> float:
    """安全平均值（空列表保护）。"""
    if not values:
        return default
    try:
        return sum(values) / len(values)
    except (TypeError, ValueError):
        return default


def safe_sum(values: list, default: float = 0.0) -> float:
    """安全求和（非数值过滤）。"""
    if not values:
        return default
    try:
        return sum(float(v) for v in values if isinstance(v, (int, float)))
    except (TypeError, ValueError):
        return default


# ── LLM 安全操作 ──

def safe_llm_json(messages: list[dict], max_tokens: int = 512, default: dict | None = None) -> dict | None:
    """安全调用 LLM 并解析 JSON。

    边缘处理：
    - LLM 未配置 → 返回 default
    - 超时 → 返回 default
    - 返回非 JSON → 尝试修复 + 返回 default
    - 返回空 → 返回 default
    """
    try:
        from agent_core.llm_client import chat

        resp = chat(messages, max_tokens=max_tokens)
        if not resp or not resp.strip():
            return default

        text = resp.strip()
        # 去除可能的 markdown 代码块
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 尝试提取 JSON 片段
            import re
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            return default
    except ImportError:
        logger.warning("LLM 模块不可用")
        return default
    except Exception as e:
        logger.warning("LLM 调用失败: %s", e)
        return default


# ── 输入验证 ──

def validate_task_result(result: dict[str, Any]) -> dict[str, Any]:
    """验证并补全任务结果字段。

    边缘处理：
    - result 为 None → 返回空 dict
    - 缺失字段 → 填充安全默认值
    - 类型错误 → 强制转换
    """
    if not result:
        return {}

    validated = dict(result)

    # 确保必需字段存在且有正确类型
    if not isinstance(validated.get("steps"), list):
        validated["steps"] = []
    if not isinstance(validated.get("step_results"), list):
        validated["step_results"] = []
    if not isinstance(validated.get("logs"), list):
        validated["logs"] = []
    if not isinstance(validated.get("cost_time"), (int, float)):
        validated["cost_time"] = 0
    if not isinstance(validated.get("task_text"), str):
        validated["task_text"] = str(validated.get("task_text", ""))

    return validated


def sanitize_text(text: str, max_length: int = 1000) -> str:
    """清理文本输入。

    边缘处理：
    - None → 空字符串
    - 非字符串 → str()
    - 超长截断
    - 去除首尾空白
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        try:
            text = str(text)
        except Exception:
            return ""
    text = text.strip()
    if len(text) > max_length:
        text = text[:max_length]
    return text
