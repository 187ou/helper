"""演化自定义控制服务（2.8）。"""
import logging
from datetime import datetime
from typing import Any

from memory_store.sqlite_db import get_conn

logger = logging.getLogger(__name__)

# 配置项定义：key -> {default, type, label}
CONFIG_SCHEMA: dict[str, dict[str, Any]] = {
    "enable_evolution": {"default": True, "type": "bool", "label": "启用自演化"},
    "enable_behavior_track": {"default": True, "type": "bool", "label": "行为采集"},
    "enable_auto_optimize": {"default": True, "type": "bool", "label": "自动流程优化"},
    "enable_template_save": {"default": True, "type": "bool", "label": "模板自动固化"},
    "enable_tool_gen": {"default": True, "type": "bool", "label": "工具自动生成"},
    "evolution_threshold": {"default": 60, "type": "int", "label": "演化阈值", "min": 0, "max": 100},
}


def get_config(key: str) -> Any:
    """获取单个配置值。"""
    schema = CONFIG_SCHEMA.get(key)
    if not schema:
        return None

    conn = get_conn()
    row = conn.execute("SELECT value FROM evolution_config WHERE key = ?", (key,)).fetchone()
    conn.close()

    if not row:
        return schema["default"]

    val = row["value"]
    if schema["type"] == "bool":
        return val == "1"
    if schema["type"] == "int":
        try:
            return int(val)
        except ValueError:
            return schema["default"]
    return val


def get_all_configs() -> dict[str, Any]:
    """获取所有配置。"""
    conn = get_conn()
    rows = conn.execute("SELECT key, value FROM evolution_config").fetchall()
    conn.close()

    stored = {r["key"]: r["value"] for r in rows}
    result = {}
    for key, schema in CONFIG_SCHEMA.items():
        val = stored.get(key)
        if val is None:
            result[key] = schema["default"]
        elif schema["type"] == "bool":
            result[key] = val == "1"
        elif schema["type"] == "int":
            try:
                result[key] = int(val)
            except ValueError:
                result[key] = schema["default"]
        else:
            result[key] = val
    return result


def set_config(key: str, value: Any) -> None:
    """设置单个配置。"""
    schema = CONFIG_SCHEMA.get(key)
    if not schema:
        raise ValueError(f"未知配置项: {key}")

    if schema["type"] == "bool":
        stored = "1" if value else "0"
    elif schema["type"] == "int":
        stored = str(int(value))
    else:
        stored = str(value)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    conn.execute(
        """INSERT INTO evolution_config (key, value, update_time) VALUES (?, ?, ?)
           ON CONFLICT(key) DO UPDATE SET value = excluded.value, update_time = excluded.update_time""",
        (key, stored, now),
    )
    conn.commit()
    conn.close()


def reset_to_default() -> None:
    """恢复默认配置。"""
    conn = get_conn()
    conn.execute("DELETE FROM evolution_config")
    conn.commit()
    conn.close()


def is_tracking_enabled() -> bool:
    """行为采集是否开启。"""
    return get_config("enable_behavior_track")


def is_evolution_enabled() -> bool:
    """自演化是否开启。"""
    return get_config("enable_evolution")
