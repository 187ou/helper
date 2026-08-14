"""看板页面。"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
    QLabel, QPushButton, QFrame, QInputDialog
)
from service.schedule_service import get_today_schedule, add_schedule
from service.health_service import get_health_reminders
from gui.style import (
    BG, BG_SIDEBAR, ACCENT, TEXT, TEXT_SEC, TEXT_MUTED, BORDER, title_font
)


class PageDashboard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        header = QLabel("📋 今日看板")
        header.setFont(title_font(17))
        layout.addWidget(header)

        row = QHBoxLayout()
        row.setSpacing(12)

        work = QFrame()
        work.setStyleSheet(f"background: {BG_SIDEBAR}; border: 1px solid {BORDER}; border-radius: 10px;")
        wl = QVBoxLayout(work)
        wl.setContentsMargins(14, 12, 14, 12)
        wh = QLabel("💼 工作清单")
        wh.setStyleSheet(f"color: {TEXT_SEC}; font-weight: 500; font-size: 12px;")
        wl.addWidget(wh)
        self.work_list = QListWidget()
        self.work_list.setStyleSheet("border: none; background: transparent;")
        wl.addWidget(self.work_list)
        btns = QHBoxLayout()
        wa = QPushButton("+ 添加")
        wa.setFixedHeight(28)
        wa.clicked.connect(self._add_work)
        wd = QPushButton("✓ 完成")
        wd.setProperty("class", "secondary")
        wd.setFixedHeight(28)
        wd.clicked.connect(self._done)
        btns.addWidget(wa)
        btns.addWidget(wd)
        wl.addLayout(btns)
        row.addWidget(work)

        life = QFrame()
        life.setStyleSheet(f"background: {BG_SIDEBAR}; border: 1px solid {BORDER}; border-radius: 10px;")
        ll = QVBoxLayout(life)
        ll.setContentsMargins(14, 12, 14, 12)
        lh = QLabel("🏠 生活待办")
        lh.setStyleSheet(f"color: {TEXT_SEC}; font-weight: 500; font-size: 12px;")
        ll.addWidget(lh)
        self.life_list = QListWidget()
        self.life_list.setStyleSheet("border: none; background: transparent;")
        ll.addWidget(self.life_list)
        la = QPushButton("+ 添加")
        la.setProperty("class", "secondary")
        la.setFixedHeight(28)
        la.clicked.connect(self._add_life)
        ll.addWidget(la)
        row.addWidget(life)

        layout.addLayout(row, stretch=2)

        health = QFrame()
        health.setStyleSheet(f"background: {BG_SIDEBAR}; border: 1px solid {BORDER}; border-radius: 10px;")
        hl = QVBoxLayout(health)
        hl.setContentsMargins(14, 12, 14, 12)
        hh = QLabel("💪 健康提醒")
        hh.setStyleSheet(f"color: {TEXT_SEC}; font-weight: 500; font-size: 12px;")
        hl.addWidget(hh)
        hr = QHBoxLayout()
        for r in get_health_reminders():
            c = QFrame()
            c.setStyleSheet(f"background: #eff6ff; border: 1px solid #dbeafe; border-radius: 8px; padding: 8px;")
            cl = QVBoxLayout(c)
            cl.setSpacing(2)
            t = QLabel(f"<b>{r['title']}</b>")
            t.setStyleSheet(f"color: {ACCENT};")
            cl.addWidget(t)
            d = QLabel(f"{r['interval_min']} 分钟" if r['interval_min'] else "每日")
            d.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
            cl.addWidget(d)
            hr.addWidget(c)
        hr.addStretch()
        hl.addLayout(hr)
        layout.addWidget(health, stretch=1)

    def _load_data(self):
        self.work_list.clear()
        self.life_list.clear()
        for item in get_today_schedule():
            t = f"[{item['schedule_time'] or '全天'}] {item['title']}"
            (self.work_list if item.get("category") == "work" else self.life_list).addItem(t)

    def _add_work(self):
        t, ok = QInputDialog.getText(self, "添加工作事项", "内容:")
        if ok and t.strip():
            add_schedule(t.strip(), schedule_time="", category="work")
            self._load_data()

    def _add_life(self):
        t, ok = QInputDialog.getText(self, "添加生活待办", "内容:")
        if ok and t.strip():
            add_schedule(t.strip(), schedule_time="", category="life")
            self._load_data()

    def _done(self):
        r = self.work_list.currentRow()
        if r >= 0:
            self.work_list.takeItem(r)
