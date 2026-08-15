"""FastAPI 应用入口。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import chat, schedule, evolution, knowledge, settings

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


@app.get("/api/health")
def health():
    return {"status": "ok"}
