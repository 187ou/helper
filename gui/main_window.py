"""主窗口：极简风格。"""
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
from gui.style import BG, TEXT, TEXT_SEC, TEXT_MUTED, ACCENT, BORDER, FONT

logger = logging.getLogger(__name__)

NAVS = [("对话", 0), ("看板", 1), ("进化", 2), ("知识库", 3), ("设置", 4)]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("桌面助手")
        self.resize(920, 620)
        self.setMinimumSize(760, 520)
        self._btns = []
        self.float_input = None
        self._build()

    def _build(self):
        c = QWidget(); self.setCentralWidget(c)
        l = QHBoxLayout(c); l.setContentsMargins(0, 0, 0, 0); l.setSpacing(0)

        # ── 左侧导航 ──
        nav = QFrame()
        nav.setFixedWidth(140)
        nav.setStyleSheet(f"background:#fafafa; border-right:1px solid {BORDER};")
        nl = QVBoxLayout(nav)
        nl.setContentsMargins(0, 16, 0, 0)
        nl.setSpacing(0)

        logo = QLabel("  桌面助手")
        logo.setFont(QFont(FONT, 14))
        logo.setStyleSheet(f"color:{ACCENT}; font-weight:bold; padding:8px 0 20px 16px;")
        nl.addWidget(logo)

        for text, idx in NAVS:
            b = QPushButton(text)
            b.setFixedHeight(38)
            b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            b.setStyleSheet(f"""
                QPushButton {{
                    background:transparent; color:{TEXT_SEC};
                    border:none; border-radius:6px;
                    text-align:left; padding-left:20px;
                    font-size:13px; margin:1px 8px;
                }}
                QPushButton:hover {{ background:#f0f0f0; color:{TEXT}; }}
                QPushButton[active="true"] {{
                    background:#f0f0f0; color:{ACCENT}; font-weight:500;
                }}
            """)
            b.clicked.connect(lambda _, i=idx: self._switch(i))
            self._btns.append(b)
            nl.addWidget(b)

        nl.addStretch()
        l.addWidget(nav)

        # ── 右侧内容 ──
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background:{BG};")
        self.page_chat = PageChat()
        self.page_dashboard = PageDashboard()
        self.page_evolution = PageEvolution()
        self.page_kb = PageKB()
        self.page_settings = PageSettings()
        for p in [self.page_chat, self.page_dashboard, self.page_evolution,
                  self.page_kb, self.page_settings]:
            self.stack.addWidget(p)
        l.addWidget(self.stack, 1)
        self._switch(0)

    def _switch(self, i):
        self.stack.setCurrentIndex(i)
        for idx, b in enumerate(self._btns):
            b.setProperty("active", "true" if idx == i else "false")
            b.style().unpolish(b); b.style().polish(b)

    def closeEvent(self, e):
        e.ignore(); self.hide(); logger.info("最小化到托盘")
