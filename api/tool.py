"""自定义工具库 API（2.6 沙箱专属工具自动生成）。"""
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from evolution_core.sandbox_tool_gen import generate_tool, validate_tool
from tools.sandbox_run import run_script
from memory_store.sqlite_db import get_conn, now_str
from config.path_config import SANDBOX_TOOL_LIST_PATH

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/list")
def list_tools():
    """列出所有已入库工具。"""
    if not SANDBOX_TOOL_LIST_PATH.exists():
        return []
    try:
        with open(SANDBOX_TOOL_LIST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


@router.post("/generate")
def gen_tool(body: dict):
    """生成新工具（LLM 生成 + 安全校验）。"""
    desc = (body.get("description") or "").strip()
    if not desc:
        raise HTTPException(status_code=400, detail="请提供工具描述")

    tool = generate_tool(desc)
    if tool.get("status") == "error":
        raise HTTPException(status_code=500, detail=tool.get("error", "生成失败"))

    return tool


@router.post("/{tool_id}/run")
def run_tool(tool_id: str, body: dict):
    """在沙箱中运行指定工具。"""
    # 查找工具
    if not SANDBOX_TOOL_LIST_PATH.exists():
        raise HTTPException(status_code=404, detail="工具库为空")

    with open(SANDBOX_TOOL_LIST_PATH, "r", encoding="utf-8") as f:
        tools = json.load(f)

    tool = None
    for t in tools:
        if t.get("id") == tool_id or t.get("name") == tool_id:
            tool = t
            break

    if not tool:
        raise HTTPException(status_code=404, detail="工具不存在")

    code = tool.get("code", "")
    if not code:
        raise HTTPException(status_code=400, detail="工具代码为空")

    # 沙箱执行
    output = run_script(code, timeout=10)
    return {"output": output, "tool": tool.get("name", tool_id)}


@router.post("/{tool_id}/save")
def save_tool(tool_id: str, body: dict):
    """将生成的工具保存到工具库。"""
    desc = (body.get("description") or "").strip()
    code = (body.get("code") or "").strip()
    name = (body.get("name") or "").strip()

    if not code:
        raise HTTPException(status_code=400, detail="代码为空")

    # 安全校验
    safe, msg = validate_tool(code)
    if not safe:
        raise HTTPException(status_code=400, detail=f"安全校验未通过: {msg}")

    # 加载现有工具
    tools = []
    if SANDBOX_TOOL_LIST_PATH.exists():
        with open(SANDBOX_TOOL_LIST_PATH, "r", encoding="utf-8") as f:
            tools = json.load(f)

    # 检查是否已存在
    tool_key = name or f"tool_{tool_id}"
    for t in tools:
        if t.get("name") == tool_key:
            # 更新
            t["code"] = code
            t["description"] = desc
            t["updated_at"] = now_str()
            break
    else:
        # 新增
        tools.append({
            "id": tool_id,
            "name": tool_key,
            "description": desc,
            "code": code,
            "status": "active",
            "created_at": now_str(),
        })

    # 持久化
    SANDBOX_TOOL_LIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SANDBOX_TOOL_LIST_PATH, "w", encoding="utf-8") as f:
        json.dump(tools, f, ensure_ascii=False, indent=2)

    return {"ok": True, "name": tool_key, "total": len(tools)}


@router.delete("/{tool_id}")
def delete_tool(tool_id: str):
    """删除工具。"""
    if not SANDBOX_TOOL_LIST_PATH.exists():
        raise HTTPException(status_code=404, detail="工具库为空")

    with open(SANDBOX_TOOL_LIST_PATH, "r", encoding="utf-8") as f:
        tools = json.load(f)

    filtered = [t for t in tools if t.get("id") != tool_id and t.get("name") != tool_id]
    if len(filtered) == len(tools):
        raise HTTPException(status_code=404, detail="工具不存在")

    with open(SANDBOX_TOOL_LIST_PATH, "w", encoding="utf-8") as f:
        json.dump(filtered, f, ensure_ascii=False, indent=2)

    return {"ok": True, "remaining": len(filtered)}
