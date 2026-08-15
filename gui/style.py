"""全局样式：极简。"""
from PyQt6.QtGui import QFont

# ── 配色 ──
BG = "#ffffff"
BG_ALT = "#fafafa"
TEXT = "#1a1a1a"
TEXT_SEC = "#666666"
TEXT_MUTED = "#999999"
ACCENT = "#333333"
BORDER = "#eaeaea"
BORDER_LIGHT = "#f0f0f0"
SUCCESS = "#16a34a"
DANGER = "#dc2626"

FONT = "Microsoft YaHei"


def font(size: int = 13, bold: bool = False) -> QFont:
    f = QFont(FONT, size)
    f.setBold(bold)
    return f


QSS = """
* { font-family: "Microsoft YaHei", system-ui; font-size: 13px; color: #1a1a1a; }
QMainWindow, QWidget { background: #ffffff; }

QScrollBar:vertical { width: 4px; background: transparent; }
QScrollBar::handle:vertical { background: #ddd; border-radius: 2px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QLineEdit, QTextEdit {
    border: 1px solid #eaeaea; border-radius: 6px; padding: 10px 14px;
    background: #fafafa; selection-background-color: #333;
}
QLineEdit:focus, QTextEdit:focus { border-color: #333; background: #fff; }

QPushButton {
    background: #1a1a1a; color: white; border: none;
    border-radius: 6px; padding: 10px 22px; font-weight: 500;
}
QPushButton:hover { background: #333; }
QPushButton:disabled { background: #ccc; }

QPushButton[text="次级"] {
    background: #fff; color: #333; border: 1px solid #eaeaea;
}
QPushButton[text="次级"]:hover { background: #fafafa; }

QListWidget {
    border: 1px solid #eaeaea; border-radius: 8px;
    padding: 8px; outline: none;
}
QListWidget::item { padding: 10px 12px; border-radius: 4px; }
QListWidget::item:hover { background: #fafafa; }
QListWidget::item:selected { background: #f0f0f0; color: #1a1a1a; font-weight: 500; }

QProgressBar {
    background: #f0f0f0; border: none; border-radius: 3px;
    height: 6px; text-align: center;
}
QProgressBar::chunk { background: #333; border-radius: 3px; }

QComboBox {
    border: 1px solid #eaeaea; border-radius: 6px; padding: 8px 14px;
    background: #fafafa;
}
QComboBox:hover { border-color: #ccc; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background: #fff; border: 1px solid #eaeaea;
    selection-background: #f0f0f0; selection-color: #1a1a1a;
}

QToolTip { background: #333; color: #fff; border: none; padding: 6px 10px; }
"""

GLOBAL_QSS = QSS
