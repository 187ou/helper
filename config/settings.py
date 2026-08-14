"""运行模式、开机自启、提醒配置。读写 user_data/user_config.json。"""
import json
import logging
from typing import Any

from config.path_config import USER_CONFIG_PATH, ensure_dirs
from config.app_const import RunMode

logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_CONFIG: dict[str, Any] = {
    "run_mode": RunMode.ONLINE.value,
    "auto_start": False,
    "remind_sedentary": True,
    "remind_drink_water": True,
    "sedentary_interval_min": 60,
    "drink_water_interval_min": 45,
    # LLM API 配置
    "api_base_url": "https://api.longcat.chat/openai/v1",
    "api_key": "",
    "model_name": "LongCat-2.0",
}

_config_cache: dict[str, Any] | None = None


def load_config() -> dict[str, Any]:
    """加载配置，首次使用默认值并写入文件。"""
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    ensure_dirs()
    if USER_CONFIG_PATH.exists():
        try:
            with open(USER_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 合并新增默认字段
            merged = {**DEFAULT_CONFIG, **data}
            _config_cache = merged
            return merged
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("配置文件读取失败，使用默认配置: %s", e)

    _config_cache = dict(DEFAULT_CONFIG)
    save_config(_config_cache)
    return _config_cache


def save_config(config: dict[str, Any]) -> None:
    """持久化配置到 JSON。"""
    global _config_cache
    ensure_dirs()
    with open(USER_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    _config_cache = config


def get(key: str, default: Any = None) -> Any:
    """读取单个配置项。"""
    return load_config().get(key, default)


def set(key: str, value: Any) -> None:
    """写入单个配置项并保存。"""
    cfg = load_config()
    cfg[key] = value
    save_config(cfg)


def get_run_mode() -> RunMode:
    return RunMode(get("run_mode", RunMode.ONLINE.value))


def set_run_mode(mode: RunMode) -> None:
    set("run_mode", mode.value)


# ── LLM API 配置 ──
def get_api_base_url() -> str:
    return get("api_base_url", "https://api.longcat.chat/openai/v1")


def get_api_key() -> str:
    return get("api_key", "")


def get_model_name() -> str:
    return get("model_name", "LongCat-2.0")


def is_llm_configured() -> bool:
    """检查 LLM 是否已配置好（有 key 和 base url）。"""
    return bool(get_api_key()) and bool(get_api_base_url())
