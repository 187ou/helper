"""FastAPI 应用入口。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import chat, schedule, evolution, knowledge, settings, task, search, behavior, evo_config, work, life, note, ai, system, tool, feedback

app = FastAPI(title="桌面智能助手 API", version="1.0.0")

# CORS - 允许前端 dev server 访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(schedule.router, prefix="/api/schedule", tags=["schedule"])
app.include_router(evolution.router, prefix="/api/evolution", tags=["evolution"])
app.include_router(knowledge.router, prefix="/api/kb", tags=["knowledge"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(task.router, prefix="/api/task", tags=["task"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(behavior.router, prefix="/api/behavior", tags=["behavior"])
app.include_router(evo_config.router, prefix="/api/evo-config", tags=["evo-config"])
app.include_router(work.router, prefix="/api/work", tags=["work"])
app.include_router(life.router, prefix="/api/life", tags=["life"])
app.include_router(note.router, prefix="/api/note", tags=["note"])
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])
app.include_router(system.router, prefix="/api/system", tags=["system"])
app.include_router(tool.router, prefix="/api/tool", tags=["tool"])
app.include_router(feedback.router, prefix="/api/feedback", tags=["feedback"])


@app.get("/api/health")
def health():
    return {"status": "ok"}
