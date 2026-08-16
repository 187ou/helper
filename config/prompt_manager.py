"""Prompt 配置管理：从 YAML 加载 prompt，支持热更新。"""
import logging
from pathlib import Path
from typing import Any

from omegaconf import OmegaConf

logger = logging.getLogger(__name__)

_PROMPTS_PATH = Path(__file__).parent.parent / "conf" / "prompts.yaml"

_prompts_cache: dict[str, Any] = None


def load_prompts(force_reload: bool = False) -> dict[str, Any]:
    """加载 prompt 配置（带缓存）。"""
    global _prompts_cache
    if _prompts_cache is not None and not force_reload:
        return _prompts_cache

    if not _PROMPTS_PATH.exists():
        logger.warning("Prompt 配置文件不存在: %s", _PROMPTS_PATH)
        return {}

    try:
        cfg = OmegaConf.load(str(_PROMPTS_PATH))
        _prompts_cache = OmegaConf.to_object(cfg)
        logger.info("Prompt 配置加载完成: %d 个 prompt", len(_prompts_cache))
        return _prompts_cache
    except Exception as e:
        logger.error("Prompt 配置加载失败: %s", e)
        return {}


def get_prompt(prompt_name: str, default: str = "") -> str:
    """获取指定 prompt。"""
    prompts = load_prompts()
    return prompts.get(prompt_name, default)


def get_score_weights(task_type: str = "work") -> dict[str, float]:
    """获取打分维度权重。"""
    prompts = load_prompts()
    weights = prompts.get("score_weights", {})
    return weights.get(task_type, weights.get("work", {}))


def reload_prompts() -> dict[str, Any]:
    """强制重新加载 prompt 配置。"""
    global _prompts_cache
    _prompts_cache = None
    return load_prompts(force_reload=True)
