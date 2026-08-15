"""演化控制 API（2.8）。"""
import logging
from fastapi import APIRouter, HTTPException

from service.evolution_config_service import (
    get_config, get_all_configs, set_config, reset_to_default, CONFIG_SCHEMA,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
def get_all():
    """获取所有演化配置。"""
    return {
        "configs": get_all_configs(),
        "schema": {
            k: {sk: sv for sk, sv in v.items() if sk != "default"}
            for k, v in CONFIG_SCHEMA.items()
        },
    }


@router.get("/{key}")
def get_one(key: str):
    """获取单个配置。"""
    val = get_config(key)
    if val is None:
        raise HTTPException(status_code=404, detail="未知配置项")
    return {"key": key, "value": val}


@router.put("/{key}")
def update_one(key: str, body: dict):
    """更新单个配置。"""
    if key not in CONFIG_SCHEMA:
        raise HTTPException(status_code=404, detail="未知配置项")
    set_config(key, body.get("value"))
    return {"ok": True, "key": key, "value": get_config(key)}


@router.post("/reset")
def reset():
    """恢复默认配置。"""
    reset_to_default()
    return {"ok": True, "configs": get_all_configs()}
