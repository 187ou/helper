"""任务管理 API：全生命周期 CRUD + 状态流转 + DAG + 断点续跑。"""
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from service.task_service import (
    list_tasks, get_task, create_task, update_task,
    change_status, delete_task, get_statistics, get_dag, save_dag,
    get_failed_steps, get_first_failed_step_index,
    VALID_STATUSES, VALID_PRIORITIES, VALID_TYPES,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/stats")
def stats():
    """看板统计数据。"""
    return get_statistics()


@router.get("/list")
def list_(
    status: str = "",
    task_type: str = "",
    priority: str = "",
    keyword: str = "",
    limit: int = 100,
):
    """列出任务（多维过滤）。"""
    return list_tasks(status=status, task_type=task_type, priority=priority, keyword=keyword, limit=limit)


@router.get("/{task_id}")
def get(task_id: int):
    """获取单个任务。"""
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.post("/create")
def create(body: dict):
    """创建任务。"""
    content = (body.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="任务内容不能为空")
    return create_task(
        content=content,
        task_type=body.get("task_type", "work"),
        priority=body.get("priority", "medium"),
        tags=body.get("tags", ""),
        deadline=body.get("deadline", ""),
        related_doc=body.get("related_doc", ""),
        steps=body.get("steps"),
        source=body.get("source", "manual"),
    )


@router.put("/{task_id}")
def update(task_id: int, body: dict):
    """更新任务。"""
    task = update_task(task_id, **body)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.post("/{task_id}/status")
def status(task_id: int, body: dict):
    """状态流转。"""
    new_status = body.get("status", "")
    if new_status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"无效状态，可选: {VALID_STATUSES}")
    try:
        task = change_status(task_id, new_status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.delete("/{task_id}")
def delete(task_id: int):
    """删除任务。"""
    delete_task(task_id)
    return {"ok": True}


@router.get("/{task_id}/dag")
def dag(task_id: int):
    """获取任务 DAG 数据。"""
    dag_data = get_dag(task_id)
    if not dag_data:
        raise HTTPException(status_code=404, detail="无可用的 DAG 数据")
    return dag_data


# ── 断点续跑 / 失败重试 ──


@router.get("/{task_id}/failed-steps")
def failed_steps(task_id: int):
    """获取失败/未执行的步骤列表。"""
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {
        "task_id": task_id,
        "task_status": task.get("status"),
        "failed_steps": get_failed_steps(task_id),
        "resume_from": get_first_failed_step_index(task_id),
    }


@router.post("/{task_id}/retry")
def retry(task_id: int, body: dict):
    """从失败步骤重试任务（断点续跑）。"""
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    current_status = task.get("status", "")
    if current_status not in ("failed", "doing"):
        raise HTTPException(status_code=400, detail=f"只能重试失败的任务，当前状态: {current_status}")

    # 确定续跑起点
    resume_from = body.get("resume_from")
    if resume_from is None:
        resume_from = get_first_failed_step_index(task_id)

    if resume_from is None:
        raise HTTPException(status_code=400, detail="没有可重试的步骤")

    # 重置任务状态为 doing
    change_status(task_id, "doing")

    # 触发流式续跑
    from agent_core.task_scheduler import run_stream
    from fastapi.responses import StreamingResponse

    task_text = task.get("task_content", "")
    task_data = {
        "task_id": task_id,
        "task_text": task_text,
        "steps": task.get("task_steps", []),
    }

    def event_stream():
        try:
            yield f"event: retry_start\ndata: {json.dumps({'task_id': task_id, 'resume_from': resume_from}, ensure_ascii=False)}\n\n"
            for event in run_stream(task_text, task_id=task_id, resume_from=resume_from):
                yield f"event: {event['type']}\ndata: {json.dumps(event.get('data', {}), ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'message': str(e)[:200]}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{task_id}/dag")
def save_dag_route(task_id: int, body: dict):
    """保存 DAG 数据。"""
    save_dag(task_id, body)
    return {"ok": True}


# ── 元数据 ──
@router.get("/meta/options")
def options():
    """返回状态、优先级、类型可选值。"""
    return {
        "statuses": list(VALID_STATUSES),
        "priorities": list(VALID_PRIORITIES),
        "types": list(VALID_TYPES),
    }
