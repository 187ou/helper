"""用户反馈 API：提交修改/驳回/点赞，驱动反馈学习闭环。"""
import logging
from typing import Any

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/submit")
def submit_feedback(body: dict):
    """提交用户反馈（修改/驳回/点赞）。

    前端在用户对 AI 输出进行修改、驳回或点赞时调用。
    反馈会触发偏好学习，影响后续任务执行。

    请求体:
    {
        "feedback_type": "modify" | "reject" | "praise",
        "task_id": 123,
        "task_type": "work",
        "original": "AI 原始输出",
        "modified": "用户修改后的输出",
        "context": {"step_index": 0, "field": "content"}  // 可选
    }
    """
    from evolution_core.feedback_learner import record_feedback

    feedback_type = body.get("feedback_type", "")
    if feedback_type not in ("modify", "reject", "praise"):
        raise HTTPException(status_code=400, detail="feedback_type 必须是 modify/reject/praise 之一")

    task_id = body.get("task_id", 0)
    task_type = body.get("task_type", "")
    original = body.get("original", "")
    modified = body.get("modified", "")
    context = body.get("context", {})

    # 验证：modify/reject 需要 original 和 modified
    if feedback_type in ("modify", "reject"):
        if not original or not modified:
            raise HTTPException(status_code=400, detail="modify/reject 反馈需要提供 original 和 modified")
        if original == modified:
            raise HTTPException(status_code=400, detail="original 与 modified 相同，无需提交 modify 反馈")

    # praise 不需要 modified
    if feedback_type == "praise":
        modified = original  # 点赞表示认可原始输出

    fid = record_feedback(
        feedback_type=feedback_type,
        original=original,
        modified=modified,
        task_id=task_id,
        task_type=task_type,
        context=context,
    )

    if fid is None:
        raise HTTPException(status_code=500, detail="反馈记录失败")

    return {"ok": True, "id": fid, "message": "反馈已记录，系统将从中学习您的偏好"}


@router.get("/list")
def list_feedback(task_id: int = 0, feedback_type: str = "", limit: int = 50):
    """查询反馈记录。"""
    from evolution_core.feedback_learner import get_feedback_stats

    if task_id > 0:
        # 查询特定任务的反馈
        from memory_store.sqlite_db import get_conn
        conn = get_conn()
        try:
            rows = conn.execute(
                """SELECT * FROM user_feedback WHERE task_id = ?
                   ORDER BY create_time DESC LIMIT ?""",
                (task_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # 返回统计
    return get_feedback_stats()


@router.get("/preferences")
def list_preferences():
    """获取所有用户偏好（供前端展示）。"""
    from evolution_core.feedback_learner import get_all_preferences
    return get_all_preferences()


@router.get("/preferences/summary")
def preference_summary(task_type: str = ""):
    """获取偏好摘要（可直接注入 prompt 的文本）。"""
    from evolution_core.feedback_learner import generate_execution_guidance
    return {"guidance": generate_execution_guidance(task_type)}


@router.delete("/preferences/{pref_key}")
def delete_preference(pref_key: str):
    """删除指定偏好。"""
    from memory_store.sqlite_db import get_conn
    conn = get_conn()
    try:
        conn.execute("DELETE FROM user_preference WHERE pref_key = ?", (pref_key,))
        conn.commit()
        return {"ok": True, "deleted": pref_key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:200])
    finally:
        conn.close()
