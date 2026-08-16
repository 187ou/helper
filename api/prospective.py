"""前瞻记忆 API：承诺管理 + 提醒触发。"""
import logging
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/parse")
def parse_intent(body: dict):
    """解析用户意图并存储（检测是否包含前瞻意图）。

    请求体: {"text": "记住下周三提醒我交周报"}

    返回: {"is_intent": true, "intent": {...}} 或 {"is_intent": false}
    """
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text 不能为空")

    from agent_core.prospective_memory import parse_and_store_intent

    intent = parse_and_store_intent(text)
    if intent:
        return {
            "is_intent": True,
            "id": intent.get("id"),
            "trigger_type": intent.get("trigger_type"),
            "trigger_value": intent.get("trigger_value"),
            "trigger_time": intent.get("trigger_time", ""),
            "recurrence": intent.get("recurrence", ""),
            "message": f"已记住：{intent.get('trigger_value', text)}",
        }

    return {"is_intent": False}


@router.post("/create")
def create_reminder(body: dict):
    """手动创建提醒。

    请求体: {
        "intent": "提醒内容",
        "trigger_type": "time|event|condition",
        "trigger_time": "2026-08-20 09:00:00",  // time 类型必填
        "trigger_event": "收到发票",              // event 类型必填
        "priority": 1,
        "recurrence": "daily|weekly|monthly|''"
    }
    """
    from agent_core.prospective_memory import _store_intent

    intent = {
        "trigger_type": body.get("trigger_type", "time"),
        "trigger_value": body.get("intent", ""),
        "trigger_time": body.get("trigger_time", ""),
        "trigger_event": body.get("trigger_event", ""),
        "trigger_condition": body.get("trigger_condition", ""),
        "priority": body.get("priority", 1),
        "recurrence": body.get("recurrence", ""),
        "note": body.get("intent", ""),
    }

    memory_id = _store_intent(intent)
    return {"ok": True, "id": memory_id, "message": "提醒已创建"}


@router.get("/due")
def check_due():
    """检查到期的提醒（由前端定时轮询或后端调度器调用）。"""
    from agent_core.prospective_memory import check_due_reminders

    due = check_due_reminders()
    return {"due": due, "count": len(due)}


@router.get("/list")
def list_reminders(status: str = "pending", limit: int = 20):
    """列出提醒。"""
    from agent_core.prospective_memory import list_reminders

    return list_reminders(status=status, limit=limit)


@router.post("/{memory_id}/complete")
def complete_reminder(memory_id: int):
    """标记提醒为已完成。"""
    from agent_core.prospective_memory import complete_reminder

    if complete_reminder(memory_id):
        return {"ok": True}
    raise HTTPException(status_code=500, detail="操作失败")


@router.post("/{memory_id}/dismiss")
def dismiss_reminder(memory_id: int):
    """Dismiss 提醒。"""
    from agent_core.prospective_memory import dismiss_reminder

    if dismiss_reminder(memory_id):
        return {"ok": True}
    raise HTTPException(status_code=500, detail="操作失败")


@router.delete("/{memory_id}")
def delete_reminder(memory_id: int):
    """删除提醒。"""
    from agent_core.prospective_memory import delete_reminder

    if delete_reminder(memory_id):
        return {"ok": True}
    raise HTTPException(status_code=404, detail="提醒不存在")
