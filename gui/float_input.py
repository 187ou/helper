"""悬浮输入框。"""
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
        self.setFixedSize(280, 44)
        self._drag = None
        self._build()

    def _build(self):
        self.setStyleSheet(f"background: {BG}; border: 1px solid {ACCENT}; border-radius: 22px;")
        l = QHBoxLayout(self); l.setContentsMargins(14, 4, 8, 4)
        self.input = QLineEdit(); self.input.setPlaceholderText("输入指令，回车提交...")
        self.input.setStyleSheet(f"border: none; font-size: 13px; color: {TEXT}; background: transparent;")
        self.input.returnPressed.connect(self._submit)
        l.addWidget(self.input)
        self.btn = QPushButton("→"); self.btn.setFixedSize(28, 28)
        self.btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn.setStyleSheet(f"background: {ACCENT}; color: white; border-radius: 14px; font-weight: bold;")
        self.btn.clicked.connect(self._submit)
        l.addWidget(self.btn)

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
