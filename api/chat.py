"""对话 API（含流式 SSE + 反馈）。"""
import json
import logging
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from agent_core.task_scheduler import run_stream
from config.settings import is_llm_configured

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/configured")
def check_configured():
    return {"configured": is_llm_configured()}


@router.post("/send")
def send_message(body: dict):
    """非流式接口（兼容旧版），返回简单确认。"""
    text = (body.get("text") or "").strip()
    if not text:
        return {"ok": False, "error": "empty"}
    if not is_llm_configured():
        return {"ok": False, "error": "llm_not_configured"}

    # 触发任务执行（不等待结果，结果通过 stream 接口获取）
    from agent_core.task_scheduler import run
    try:
        result = run(text)
        return {"ok": True, "status": result.get("status", "done"), "steps_count": len(result.get("steps", []))}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


@router.post("/stream")
def stream_message(body: dict):
    """SSE 流式输出：拆解步骤 → 执行进度 → 完成."""
    text = (body.get("text") or "").strip()
    if not text:
        return {"ok": False, "error": "empty"}
    if not is_llm_configured():
        def err_stream():
            data = json.dumps({"message": "llm_not_configured"}, ensure_ascii=False)
            yield f"event: error\ndata: {data}\n\n"
        return StreamingResponse(err_stream(), media_type="text/event-stream")

    def event_stream():
        try:
            for event in run_stream(text):
                # 为 steps 事件附加反馈 URL（前端可据此展示反馈按钮）
                if event.get("type") == "steps":
                    event["data"]["feedback_url"] = "/api/feedback/submit"
                yield f"event: {event['type']}\ndata: {json.dumps(event.get('data', {}), ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'message': str(e)[:200]}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
