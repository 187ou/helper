"""配置管理：OmegaConf 结构化加载，对外保持兼容接口。"""
import logging
from pathlib import Path
from typing import Any

from omegaconf import OmegaConf

from config.conf_schema import AppConfig
from config.path_config import USER_CONFIG_PATH, ensure_dirs

logger = logging.getLogger(__name__)

# ── YAML 配置路径 ──
YAML_PATH = Path(__file__).parent.parent / "conf" / "app_config.yaml"

# 全局配置实例
_config: AppConfig | None = None


def load_config() -> AppConfig:
    """加载配置：schema 默认值 + YAML 覆盖 + JSON 用户配置覆盖。"""
    global _config
    if _config is not None:
        return _config

    # 1. schema 提供默认值
    schema = OmegaConf.structured(AppConfig)

    # 2. YAML 文件覆盖
    if YAML_PATH.exists():
        yaml_cfg = OmegaConf.load(str(YAML_PATH))
        schema = OmegaConf.merge(schema, yaml_cfg)

    # 3. JSON 用户配置覆盖（向后兼容）
    if USER_CONFIG_PATH.exists():
        try:
            import json
            with open(USER_CONFIG_PATH, "r", encoding="utf-8") as f:
                json_cfg = json.load(f)
            # 扁平 key → 嵌套结构
            nested = _flat_to_nested(json_cfg)
            schema = OmegaConf.merge(schema, nested)
        except Exception as e:
            logger.warning("JSON 配置读取失败: %s", e)

    _config = OmegaConf.to_object(schema)
    logger.info("配置加载完成: run_mode=%s, model=%s", _config.run_mode, _config.llm.model_name)
    return _config


def _flat_to_nested(flat: dict) -> dict:
    """将扁平 key 转为嵌套结构（向后兼容）。"""
    nested = {}
    for k, v in flat.items():
        if k == "api_base_url":
            nested.setdefault("llm", {})["base_url"] = v
        elif k == "api_key":
            nested.setdefault("llm", {})["api_key"] = v
        elif k == "model_name":
            nested.setdefault("llm", {})["model_name"] = v
        elif k == "run_mode":
            nested["run_mode"] = v
        elif k == "auto_start":
            nested["auto_start"] = v
        elif k in ("remind_sedentary", "remind_drink_water"):
            nested.setdefault("reminder", {})[k] = v
        elif k in ("sedentary_interval_min", "drink_water_interval_min"):
            nested.setdefault("reminder", {})[k] = v
    return nested


def reload_config() -> AppConfig:
    """强制重新加载配置。"""
    global _config
    _config = None
    return load_config()


# ── 兼容接口（保持原有调用方式不变） ──

def get(key: str, default: Any = None) -> Any:
    """读取配置项（支持点号路径，如 "llm.model_name"）。"""
    cfg = load_config()
    parts = key.split(".")
    obj = cfg
    for p in parts:
        if isinstance(obj, dict):
            obj = obj.get(p, default)
        else:
            obj = getattr(obj, p, default)
        if obj is None:
            return default
    return obj


def set(key: str, value: Any) -> None:
    """写入配置项到 JSON（向后兼容）。"""
    ensure_dirs()
    import json
    if USER_CONFIG_PATH.exists():
        with open(USER_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}
    data[key] = value
    with open(USER_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    reload_config()


def get_run_mode() -> str:
    return get("run_mode", "online")


def set_run_mode(mode: str) -> None:
    set("run_mode", mode)


def get_api_base_url() -> str:
    return get("llm.base_url", "https://api.longcat.chat/openai/v1")


def get_api_key() -> str:
    return get("llm.api_key", "")


def get_model_name() -> str:
    return get("llm.model_name", "LongCat-2.0")


def is_llm_configured() -> bool:
    return bool(get_api_key()) and bool(get_api_base_url())


def get_kb_config() -> dict:
    """获取知识库配置。"""
    cfg = load_config()
    return {
        "chunk_size": cfg.kb.chunk_size,
        "chunk_overlap": cfg.kb.chunk_overlap,
        "top_k": cfg.kb.top_k,
        "hybrid_alpha": cfg.kb.hybrid_alpha,
    }
