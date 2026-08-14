"""主窗口：左侧导航 + 右侧页面，亮色精简。"""
import logging

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QPushButton, QLabel, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QCursor

from gui.page_chat import PageChat
from gui.page_dashboard import PageDashboard
from gui.page_evolution import PageEvolution
from gui.page_kb import PageKB
from gui.page_settings import PageSettings
from gui.float_input import FloatInput
from gui.style import (
    BG, BG_SIDEBAR, BG_HOVER, ACCENT, TEXT, TEXT_SEC, TEXT_MUTED, BORDER, FONT
)

logger = logging.getLogger(__name__)

NAV_ITEMS = [
    ("💬 对话", 0),
    ("📋 看板", 1),
    ("🧬 进化", 2),
    ("📚 知识库", 3),
    ("⚙️ 设置", 4),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("桌面智能助手")
        self.resize(980, 660)
        self.setMinimumSize(820, 560)
        self._nav_buttons: list[QPushButton] = []
        self.float_input: FloatInput | None = None
        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 左侧导航 ──
        nav = QFrame()
        nav.setFixedWidth(172)
        nav.setStyleSheet(f"background-color: {BG_SIDEBAR}; border-right: 1px solid {BORDER};")
        nav_layout = QVBoxLayout(nav)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(0)

        # Logo
        logo_w = QWidget()
        logo_w.setFixedHeight(64)
        logo_l = QVBoxLayout(logo_w)
        logo_l.setContentsMargins(18, 0, 0, 0)
        logo = QLabel("桌面助手")
        logo.setFont(QFont(FONT, 14))
        logo.setStyleSheet(f"color: {ACCENT}; font-weight: bold; padding-top: 14px;")
        logo_l.addWidget(logo)
        sub = QLabel("智能 · 简洁")
        sub.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
        logo_l.addWidget(sub)
        nav_layout.addWidget(logo_w)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {BORDER}; margin: 0 14px;")
        nav_layout.addWidget(sep)
        nav_layout.addSpacing(10)

        # 导航按钮
        for text, idx in NAV_ITEMS:
            btn = QPushButton(text)
            btn.setFixedHeight(40)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {TEXT_SEC};
                    border: none;
                    border-radius: 8px;
                    text-align: left;
                    padding-left: 18px;
                    font-size: 13px;
                    margin: 2px 10px;
                }}
                QPushButton:hover {{
                    background-color: {BG_HOVER};
                    color: {TEXT};
                }}
                QPushButton[class="active"] {{
                    background-color: #eff6ff;
                    color: {ACCENT};
                    font-weight: 500;
                }}
            """)
            btn.clicked.connect(lambda checked, i=idx: self._switch_page(i))
            self._nav_buttons.append(btn)
            nav_layout.addWidget(btn)

        nav_layout.addStretch()

        float_btn = QPushButton("🗔 悬浮输入")
        float_btn.setFixedHeight(34)
        float_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        float_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {TEXT_MUTED};
                border: 1px solid {BORDER};
                border-radius: 7px;
                margin: 6px 12px 14px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {BG_HOVER};
                color: {TEXT_SEC};
            }}
        """)
        float_btn.clicked.connect(self._toggle_float_input)
        nav_layout.addWidget(float_btn)

        layout.addWidget(nav)

        # ── 右侧内容 ──
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background-color: {BG};")

        self.page_chat = PageChat()
        self.page_dashboard = PageDashboard()
        self.page_evolution = PageEvolution()
        self.page_kb = PageKB()
        self.page_settings = PageSettings()

        for p in [self.page_chat, self.page_dashboard, self.page_evolution,
                  self.page_kb, self.page_settings]:
            self.stack.addWidget(p)

        layout.addWidget(self.stack, stretch=1)
        self._switch_page(0)

    def _switch_page(self, index: int):
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self._nav_buttons):
            btn.setProperty("class", "active" if i == index else "")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _toggle_float_input(self):
        if self.float_input is None:
            self.float_input = FloatInput()
            self.float_input.submitted.connect(self._on_float_submitted)
        if self.float_input.isVisible():
            self.float_input.hide()
        else:
            self.float_input.show()

    def _on_float_submitted(self, text: str):
        self._switch_page(0)
        self.page_chat.set_input_and_send(text)

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        logger.info("主窗口最小化到托盘")
