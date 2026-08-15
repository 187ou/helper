"""系统能力 API：数据备份/恢复/重置、存储信息、配置管理。"""
import json
import logging
import os
import shutil
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from config.path_config import (
    USER_DATA_DIR, DB_DIR, CHROMA_DIR, TEMPLATES_DIR,
    LOGS_DIR, ARCHIVE_DIR, DB_PATH, APP_LOG_PATH,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ═══════════════════════════════════════════
# 7.1 存储信息
# ═══════════════════════════════════════════

@router.get("/storage-info")
def storage_info():
    """获取存储目录信息。"""
    def dir_size(path: Path) -> int:
        """计算目录大小。"""
        if not path.exists():
            return 0
        total = 0
        for p in path.rglob("*"):
            if p.is_file():
                total += p.stat().st_size
        return total

    def format_size(size: int) -> str:
        """格式化文件大小。"""
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        if size < 1024 * 1024 * 1024:
            return f"{size / 1024 / 1024:.1f} MB"
        return f"{size / 1024 / 1024 / 1024:.2f} GB"

    dirs = {
        "db": DB_DIR,
        "chroma": CHROMA_DIR,
        "templates": TEMPLATES_DIR,
        "logs": LOGS_DIR,
        "archive": ARCHIVE_DIR,
    }

    dir_info = {}
    total_size = 0
    for name, path in dirs.items():
        size = dir_size(path)
        total_size += size
        dir_info[name] = {
            "path": str(path),
            "size": size,
            "size_formatted": format_size(size),
            "exists": path.exists(),
        }

    # 数据库文件
    db_size = DB_PATH.stat().st_size if DB_PATH.exists() else 0

    return {
        "user_data_root": str(USER_DATA_DIR),
        "total_size": total_size + db_size,
        "total_size_formatted": format_size(total_size + db_size),
        "database": {
            "path": str(DB_PATH),
            "size": db_size,
            "size_formatted": format_size(db_size),
        },
        "directories": dir_info,
        "privacy_note": "所有数据仅本地存储，无任何云端上传",
    }


# ═══════════════════════════════════════════
# 7.2 数据备份/恢复/重置
# ═══════════════════════════════════════════

@router.post("/backup")
def create_backup(body: dict):
    """创建数据备份（压缩包）。"""
    out_path = body.get("out_path", "")
    if not out_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = str(USER_DATA_DIR.parent / f"backup_{timestamp}.zip")

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            # 打包数据库
            if DB_PATH.exists():
                zf.write(DB_PATH, f"user_data/db/{DB_PATH.name}")

            # 打包各目录
            for dir_name, dir_path in [
                ("chroma", CHROMA_DIR),
                ("templates", TEMPLATES_DIR),
                ("logs", LOGS_DIR),
                ("archive", ARCHIVE_DIR),
            ]:
                if dir_path.exists():
                    for f in dir_path.rglob("*"):
                        if f.is_file():
                            arcname = f"user_data/{dir_name}/{f.relative_to(dir_path)}"
                            zf.write(f, arcname)

        size = out.stat().st_size
        logger.info("备份创建: %s (%d bytes)", out, size)
        return {
            "ok": True,
            "path": str(out),
            "size": size,
            "size_formatted": format_size(size),
        }
    except Exception as e:
        logger.error("备份失败: %s", e)
        raise HTTPException(status_code=500, detail=f"备份失败: {e}")


@router.post("/restore")
def restore_backup(body: dict):
    """从备份恢复数据。"""
    backup_path = body.get("backup_path", "")
    if not backup_path or not Path(backup_path).exists():
        raise HTTPException(status_code=400, detail="备份文件不存在")

    try:
        # 先备份当前数据（安全机制）
        safety_dir = USER_DATA_DIR.parent / f"_safety_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        safety_dir.mkdir(parents=True, exist_ok=True)
        if DB_PATH.exists():
            shutil.copy2(DB_PATH, safety_dir)

        # 解压恢复
        with zipfile.ZipFile(backup_path, "r") as zf:
            zf.extractall(USER_DATA_DIR.parent)

        logger.info("数据恢复: %s", backup_path)
        return {"ok": True, "message": "数据已恢复，请重启应用", "safety_backup": str(safety_dir)}
    except Exception as e:
        logger.error("恢复失败: %s", e)
        raise HTTPException(status_code=500, detail=f"恢复失败: {e}")


@router.delete("/reset/{target}")
def reset_data(target: str):
    """重置指定数据。"""
    valid_targets = {
        "evolution": "演化记忆（权重、模板、日志）",
        "bills": "记账数据",
        "knowledge": "知识库",
        "behavior": "行为日志",
        "tasks": "任务数据",
        "schedules": "日程数据",
        "habits": "习惯打卡",
        "notes": "笔记",
        "all": "全部数据（保留配置）",
    }

    if target not in valid_targets:
        raise HTTPException(status_code=400, detail=f"无效目标: {target}")

    conn = get_conn()
    try:
        if target == "evolution":
            conn.execute("DELETE FROM user_habit_weight")
            conn.execute("DELETE FROM custom_template")
            conn.execute("DELETE FROM evolution_log")
        elif target == "bills":
            conn.execute("DELETE FROM bill_record")
        elif target == "behavior":
            conn.execute("DELETE FROM behavior_log")
        elif target == "tasks":
            conn.execute("DELETE FROM task_list")
        elif target == "schedules":
            conn.execute("DELETE FROM daily_schedule")
        elif target == "habits":
            conn.execute("DELETE FROM habit_checkin")
            conn.execute("DELETE FROM habit")
        elif target == "notes":
            conn.execute("DELETE FROM note")
        elif target == "knowledge":
            # 清除知识库向量
            try:
                from memory_store.chroma_kb import get_client, COLLECTIONS
                client = get_client()
                if client:
                    for coll_name in COLLECTIONS:
                        try:
                            collection = client.get_collection(coll_name)
                            all_data = collection.get()
                            if all_data["ids"]:
                                collection.delete(ids=all_data["ids"])
                        except Exception:
                            pass
            except Exception as e:
                logger.warning("清除知识库失败: %s", e)
        elif target == "all":
            conn.execute("DELETE FROM user_habit_weight")
            conn.execute("DELETE FROM custom_template")
            conn.execute("DELETE FROM evolution_log")
            conn.execute("DELETE FROM bill_record")
            conn.execute("DELETE FROM behavior_log")
            conn.execute("DELETE FROM task_list")
            conn.execute("DELETE FROM daily_schedule")
            conn.execute("DELETE FROM habit_checkin")
            conn.execute("DELETE FROM habit")
            conn.execute("DELETE FROM note")
            conn.execute("DELETE FROM personal_archive")
            conn.execute("DELETE FROM health_record")
            conn.execute("DELETE FROM project")

        conn.commit()
        logger.info("数据重置: %s", target)
        return {"ok": True, "target": target, "description": valid_targets[target]}
    except Exception as e:
        logger.error("重置失败: %s", e)
        raise HTTPException(status_code=500, detail=f"重置失败: {e}")
    finally:
        conn.close()


def format_size(size: int) -> str:
    """格式化文件大小。"""
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    if size < 1024 * 1024 * 1024:
        return f"{size / 1024 / 1024:.1f} MB"
    return f"{size / 1024 / 1024 / 1024:.2f} GB"


def get_conn():
    """获取数据库连接。"""
    from memory_store.sqlite_db import get_conn as _get_conn
    return _get_conn()
