"""所有本地存储路径统一管理，自动创建目录。"""
import sys
from pathlib import Path


def _get_base_dir() -> Path:
    """获取基础目录。

    - 开发环境：项目根目录
    - PyInstaller 单文件 EXE：EXE 所在目录下的 user_data
    - 其他打包：用户 AppData
    """
    if getattr(sys, "frozen", False):
        # PyInstaller 打包后，sys._MEIPASS 是临时解压目录
        # 数据应放在 EXE 所在目录，避免每次启动被清理
        exe_dir = Path(sys.executable).parent
        return exe_dir
    # 开发环境：config/ 的上一级
    return Path(__file__).resolve().parent.parent


ROOT_DIR = _get_base_dir()

# 用户数据根目录
USER_DATA_DIR = ROOT_DIR / "user_data"

# 各子目录
DB_DIR = USER_DATA_DIR / "db"
CHROMA_DIR = USER_DATA_DIR / "chroma"
EPISODIC_DIR = USER_DATA_DIR / "episodic"  # 情景记忆向量索引
TEMPLATES_DIR = USER_DATA_DIR / "templates"
LOGS_DIR = USER_DATA_DIR / "logs"
ARCHIVE_DIR = USER_DATA_DIR / "archive"

# 关键文件路径
DB_PATH = DB_DIR / "app.db"
USER_CONFIG_PATH = USER_DATA_DIR / "user_config.json"
USER_STYLE_PATH = USER_DATA_DIR / "user_style.json"
SANDBOX_TOOL_LIST_PATH = USER_DATA_DIR / "sandbox_tool_list.json"
APP_LOG_PATH = LOGS_DIR / "app.log"


def ensure_dirs() -> None:
    """确保所有必要目录存在。"""
    for d in [DB_DIR, CHROMA_DIR, EPISODIC_DIR, TEMPLATES_DIR, LOGS_DIR, ARCHIVE_DIR]:
        d.mkdir(parents=True, exist_ok=True)
