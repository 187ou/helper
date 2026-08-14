"""通用 UI 组件。"""
from PyQt6.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from gui.style import BG, TEXT


def info_popup(parent, title, msg):
    QMessageBox.information(parent, title, msg)


def error_popup(parent, title, msg, retry_cb=None):
    d = QDialog(parent); d.setWindowTitle(title); d.setMinimumWidth(340)
    d.setStyleSheet(f"background: {BG};")
    l = QVBoxLayout(d)
    ml = QLabel(msg); ml.setWordWrap(True); ml.setStyleSheet(f"color: {TEXT}; padding: 8px 0;")
    l.addWidget(ml)
    r = QHBoxLayout(); r.addStretch()
    if retry_cb:
        rb = QPushButton("重试"); rb.clicked.connect(lambda: (retry_cb(), d.accept()))
        r.addWidget(rb)
    ok = QPushButton("确定"); ok.clicked.connect(d.accept); r.addWidget(ok)
    l.addLayout(r); d.exec()


def remind_popup(parent, title, msg, postpone_sec=300):
    b = QMessageBox(parent); b.setWindowTitle(title); b.setText(msg)
    b.setIcon(QMessageBox.Icon.Information)
    b.setStyleSheet(f"QMessageBox {{ background: {BG}; }} QLabel {{ color: {TEXT}; }}")
    later = b.addButton("延后", QMessageBox.ButtonRole.RejectRole)
    close = b.addButton("关闭", QMessageBox.ButtonRole.AcceptRole)
    b.setDefaultButton(later); b.exec()
    return postpone_sec if b.clickedButton() == later else 0
