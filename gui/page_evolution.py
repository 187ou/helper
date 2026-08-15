"""进化中心：极简。"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QComboBox, QFrame
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
from evolution_core.evo_log import get_stats, list_logs
from evolution_core.weight_evolve import get_top_habits
from gui.style import TEXT, TEXT_SEC, TEXT_MUTED, BORDER, FONT


class PageEvolution(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        l = QVBoxLayout(self)
        l.setContentsMargins(28, 24, 28, 24); l.setSpacing(14)

        h = QLabel("进化中心"); h.setStyleSheet(f"font-size:18px; font-weight:bold;"); l.addWidget(h)

        # 统计
        s = get_stats()
        cards = QHBoxLayout(); cards.setSpacing(10)
        for title, val in [("流程优化", s.get("flow_optimizations", 0)),
                           ("工具", s.get("tool_count", 0)),
                           ("模板", s.get("template_count", 0))]:
            c = QFrame()
            c.setStyleSheet(f"background:#fafafa; border:1px solid {BORDER}; border-radius:8px;")
            cl = QVBoxLayout(c); cl.setSpacing(0)
            v = QLabel(f"<b>{val}</b>"); v.setFont(QFont(FONT, 18))
            v.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(v)
            t = QLabel(title); t.setAlignment(Qt.AlignmentFlag.AlignCenter)
            t.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11px;")
            cl.addWidget(t)
            cards.addWidget(c)
        l.addLayout(cards)

        # 筛选
        fr = QHBoxLayout()
        fr.addWidget(QLabel("筛选:"))
        self.filt = QComboBox()
        self.filt.addItems(["全部", "流程优化", "工具新增", "模板固化", "权重迭代"])
        self.filt.currentTextChanged.connect(self._filter)
        fr.addWidget(self.filt); fr.addStretch()
        l.addLayout(fr)

        # 时间轴
        self.tl = QListWidget()
        self.tl.setStyleSheet(f"border:1px solid {BORDER};")
        l.addWidget(self.tl, 2)

        # 权重
        wh = QLabel("记忆权重"); wh.setStyleSheet(f"color:{TEXT_SEC}; font-size:12px; font-weight:500;")
        l.addWidget(wh)
        self.wt = QListWidget()
        self.wt.setStyleSheet(f"border:1px solid {BORDER};")
        l.addWidget(self.wt, 1)

        self._load()

    def _load(self):
        self.tl.clear()
        m = {"flow": "优化", "tool": "工具", "template": "模板", "weight": "权重"}
        for log in list_logs():
            self.tl.addItem(f"[{log['evo_time'][:10]}] {m.get(log['evo_type'], log['evo_type'])}")
        if not list_logs():
            self.tl.addItem("暂无记录")

        self.wt.clear()
        for h in get_top_habits(8):
            self.wt.addItem(f"  {h['habit_key']:<8} {'█' * int(h['weight'])} {h['weight']:.1f}")
        if not get_top_habits(8):
            self.wt.addItem("暂无数据")

    def _filter(self, text):
        rev = {"流程优化": "flow", "工具新增": "tool", "模板固化": "template", "权重迭代": "weight"}
        et = rev.get(text, "")
        self.tl.clear()
        m = {"flow": "优化", "tool": "工具", "template": "模板", "weight": "权重"}
        for log in list_logs(evo_type=et) if et else list_logs():
            self.tl.addItem(f"[{log['evo_time'][:10]}] {m.get(log['evo_type'], log['evo_type'])}")
        if not (list_logs(evo_type=et) if et else list_logs()):
            self.tl.addItem("暂无")
