"""全局样式：亮色精简主题。"""
from PyQt6.QtGui import QFont

# ── 配色 ──
BG = "#ffffff"
BG_SIDEBAR = "#f8f9fa"
BG_HOVER = "#f0f1f3"
BG_INPUT = "#f5f6f8"
ACCENT = "#2563eb"
ACCENT_HOVER = "#1d4ed8"
TEXT = "#1f2937"
TEXT_SEC = "#6b7280"
TEXT_MUTED = "#9ca3af"
BORDER = "#e5e7eb"
BORDER_FOCUS = "#d1d5db"
SUCCESS = "#16a34a"
DANGER = "#dc2626"

FONT = "Microsoft YaHei"


def title_font(size: int = 16) -> QFont:
    f = QFont(FONT, size)
    f.setBold(True)
    return f


def body_font(size: int = 13) -> QFont:
    return QFont(FONT, size)


def mono_font(size: int = 12) -> QFont:
    return QFont("Consolas", size)


GLOBAL_QSS = """
* {
    font-family: "Microsoft YaHei", "Segoe UI", system-ui;
    font-size: 13px;
    color: #1f2937;
}

QMainWindow, QWidget {
    background-color: #ffffff;
}

/* ── 滚动条 ── */
QScrollBar:vertical {
    width: 5px;
    background: transparent;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #d1d5db;
    border-radius: 3px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover {
    background: #9ca3af;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    height: 5px;
    background: transparent;
}
QScrollBar::handle:horizontal {
    background: #d1d5db;
    border-radius: 3px;
    min-width: 24px;
}

/* ── 输入框 ── */
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #f5f6f8;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 9px 12px;
    color: #1f2937;
    selection-background-color: #2563eb;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid #2563eb;
    background-color: #ffffff;
}
QLineEdit::placeholder, QTextEdit::placeholder {
    color: #9ca3af;
}

/* ── 按钮 ── */
QPushButton {
    background-color: #2563eb;
    color: white;
    border: none;
    border-radius: 7px;
    padding: 9px 20px;
    font-weight: 500;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #1d4ed8;
}
QPushButton:pressed {
    background-color: #1e40af;
}
QPushButton:disabled {
    background-color: #e5e7eb;
    color: #9ca3af;
}

QPushButton[class="secondary"] {
    background-color: #ffffff;
    border: 1px solid #e5e7eb;
    color: #1f2937;
}
QPushButton[class="secondary"]:hover {
    background-color: #f5f6f8;
    border-color: #d1d5db;
}

QPushButton[class="ghost"] {
    background: transparent;
    color: #6b7280;
    border: 1px solid #e5e7eb;
}
QPushButton[class="ghost"]:hover {
    background-color: #f5f6f8;
    color: #1f2937;
}

/* ── 组合框 ── */
QComboBox {
    background-color: #f5f6f8;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 8px 12px;
    color: #1f2937;
    min-height: 20px;
}
QComboBox:hover {
    border-color: #d1d5db;
}
QComboBox::drop-down {
    border: none;
    width: 28px;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    selection-background-color: #2563eb;
    color: #1f2937;
    padding: 4px;
}

/* ── 列表 ── */
QListWidget, QTreeWidget {
    background-color: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 6px;
    outline: none;
}
QListWidget::item, QTreeWidget::item {
    padding: 9px 12px;
    border-radius: 6px;
    margin: 2px 4px;
}
QListWidget::item:hover, QTreeWidget::item:hover {
    background-color: #f5f6f8;
}
QListWidget::item:selected, QTreeWidget::item:selected {
    background-color: #eff6ff;
    color: #2563eb;
    font-weight: 500;
}

/* ── 表格 ── */
QTableWidget {
    background-color: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    gridline-color: #f0f1f3;
}
QTableWidget::item {
    padding: 8px 10px;
    border-bottom: 1px solid #f0f1f3;
}
QTableWidget::item:selected {
    background-color: #eff6ff;
}
QHeaderView::section {
    background-color: #f8f9fa;
    color: #6b7280;
    border: none;
    border-bottom: 1px solid #e5e7eb;
    padding: 10px 8px;
    font-weight: 500;
    font-size: 12px;
}

/* ── 分组框 ── */
QGroupBox {
    background-color: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    margin-top: 14px;
    padding-top: 18px;
    font-weight: 500;
}
QGroupBox::title {
    color: #6b7280;
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    font-size: 12px;
}

/* ── 进度条 ── */
QProgressBar {
    background-color: #f0f1f3;
    border: none;
    border-radius: 5px;
    text-align: center;
    color: #9ca3af;
    height: 14px;
    font-size: 10px;
}
QProgressBar::chunk {
    background-color: #2563eb;
    border-radius: 5px;
}

/* ── 复选框 ── */
QCheckBox {
    color: #6b7280;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 2px solid #d1d5db;
    background-color: #ffffff;
}
QCheckBox::indicator:hover {
    border-color: #2563eb;
}
QCheckBox::indicator:checked {
    background-color: #2563eb;
    border-color: #2563eb;
}

/* ── 菜单 ── */
QMenu {
    background-color: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 6px;
}
QMenu::item {
    padding: 8px 24px;
    border-radius: 6px;
}
QMenu::item:selected {
    background-color: #2563eb;
    color: white;
}
QMenu::separator {
    height: 1px;
    background-color: #e5e7eb;
    margin: 4px 10px;
}

/* ── 分割器 ── */
QSplitter::handle {
    background-color: #f0f1f3;
}
QSplitter::handle:horizontal { width: 1px; }
QSplitter::handle:vertical { height: 1px; }

/* ── 对话框 ── */
QDialog { background-color: #ffffff; }

/* ── 工具提示 ── */
QToolTip {
    background-color: #1f2937;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 6px 10px;
}
"""
