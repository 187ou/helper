"""悬浮输入框：极简。"""
import logging
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton
from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtGui import QCursor
from gui.style import BG, ACCENT, TEXT, BORDER

logger = logging.getLogger(__name__)


class FloatInput(QWidget):
    submitted = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(260, 42)
        self._drag = None
        self._build()

    def _build(self):
        self.setStyleSheet(f"background:{BG}; border:1px solid {BORDER}; border-radius:21px;")
        l = QHBoxLayout(self); l.setContentsMargins(14, 3, 6, 3)
        self.input = QLineEdit(); self.input.setPlaceholderText("输入指令...")
        self.input.setStyleSheet(f"border:none; background:transparent; color:{TEXT};")
        self.input.returnPressed.connect(self._submit)
        l.addWidget(self.input)
        b = QPushButton("→"); b.setFixedSize(26, 26)
        b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        b.setStyleSheet(f"background:{ACCENT}; color:#fff; border-radius:13px; font-weight:bold;")
        b.clicked.connect(self._submit)
        l.addWidget(b)

    def _submit(self):
        t = self.input.text().strip()
        if t: self.submitted.emit(t); self.input.clear()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag and e.buttons() == Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None
