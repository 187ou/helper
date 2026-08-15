"""看板页：极简。"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QLabel, QPushButton, QInputDialog
from service.schedule_service import get_today_schedule, add_schedule
from gui.style import BG, TEXT, TEXT_SEC, TEXT_MUTED, BORDER


class PageDashboard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        l = QVBoxLayout(self)
        l.setContentsMargins(28, 24, 28, 24); l.setSpacing(14)

        h = QLabel("看板"); h.setStyleSheet(f"font-size:18px; font-weight:bold;"); l.addWidget(h)

        row = QHBoxLayout(); row.setSpacing(14)

        # 工作
        w = QVBoxLayout()
        wh = QLabel("工作清单"); wh.setStyleSheet(f"color:{TEXT_SEC}; font-size:12px; font-weight:500;")
        w.addWidget(wh)
        self.wl = QListWidget()
        self.wl.setStyleSheet(f"border:1px solid {BORDER};")
        w.addWidget(self.wl, 1)
        wa = QPushButton("添加"); wa.setFixedHeight(28)
        wa.clicked.connect(lambda: self._add("work"))
        w.addWidget(wa)
        row.addLayout(w)

        # 生活
        lf = QVBoxLayout()
        lh = QLabel("生活待办"); lh.setStyleSheet(f"color:{TEXT_SEC}; font-size:12px; font-weight:500;")
        lf.addWidget(lh)
        self.ll = QListWidget()
        self.ll.setStyleSheet(f"border:1px solid {BORDER};")
        lf.addWidget(self.ll, 1)
        la = QPushButton("添加"); la.setFixedHeight(28)
        la.clicked.connect(lambda: self._add("life"))
        lf.addWidget(la)
        row.addLayout(lf)

        l.addLayout(row, 1)
        self._load()

    def _load(self):
        self.wl.clear(); self.ll.clear()
        for i in get_today_schedule():
            t = f"[{i['schedule_time'] or '全天'}] {i['title']}"
            (self.wl if i.get("category") == "work" else self.ll).addItem(t)

    def _add(self, cat):
        t, ok = QInputDialog.getText(self, "添加", "内容:")
        if ok and t.strip():
            add_schedule(t.strip(), schedule_time="", category=cat)
            self._load()
