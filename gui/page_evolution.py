"""进化中心。"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QComboBox, QFrame
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
from evolution_core.evo_log import get_stats, list_logs
from evolution_core.weight_evolve import get_top_habits
from gui.style import (
    BG, BG_SIDEBAR, ACCENT, TEXT, TEXT_SEC, TEXT_MUTED, BORDER, FONT, title_font
)


class PageEvolution(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        header = QLabel("🧬 进化中心")
        header.setFont(title_font(17))
        layout.addWidget(header)

        cards = QHBoxLayout()
        cards.setSpacing(10)
        self.s_opt = self._card("流程优化", "0")
        self.s_tool = self._card("新增工具", "0")
        self.s_tpl = self._card("固化模板", "0")
        cards.addWidget(self.s_opt)
        cards.addWidget(self.s_tool)
        cards.addWidget(self.s_tpl)
        layout.addLayout(cards)

        fr = QHBoxLayout()
        fl = QLabel("筛选:")
        fl.setStyleSheet(f"color: {TEXT_SEC};")
        fr.addWidget(fl)
        self.filter = QComboBox()
        self.filter.addItems(["全部", "流程优化", "工具新增", "模板固化", "权重迭代"])
        self.filter.currentTextChanged.connect(self._filter)
        fr.addWidget(self.filter)
        fr.addStretch()
        layout.addLayout(fr)

        tl = QFrame()
        tl.setStyleSheet(f"background: {BG_SIDEBAR}; border: 1px solid {BORDER}; border-radius: 10px;")
        tll = QVBoxLayout(tl)
        tll.setContentsMargins(14, 12, 14, 12)
        tlh = QLabel("📅 迭代时间轴")
        tlh.setStyleSheet(f"color: {TEXT_SEC}; font-weight: 500; font-size: 12px;")
        tll.addWidget(tlh)
        self.tl_list = QListWidget()
        self.tl_list.setStyleSheet("border: none; background: transparent;")
        tll.addWidget(self.tl_list)
        layout.addWidget(tl, stretch=2)

        wt = QFrame()
        wt.setStyleSheet(f"background: {BG_SIDEBAR}; border: 1px solid {BORDER}; border-radius: 10px;")
        wtl = QVBoxLayout(wt)
        wtl.setContentsMargins(14, 12, 14, 12)
        wth = QLabel("🏋️ 用户记忆权重")
        wth.setStyleSheet(f"color: {TEXT_SEC}; font-weight: 500; font-size: 12px;")
        wtl.addWidget(wth)
        self.wt_list = QListWidget()
        self.wt_list.setStyleSheet("border: none; background: transparent;")
        wtl.addWidget(self.wt_list)
        layout.addWidget(wt, stretch=1)

    def _card(self, title: str, val: str) -> QFrame:
        c = QFrame()
        c.setStyleSheet(f"background: {BG_SIDEBAR}; border: 1px solid {BORDER}; border-radius: 10px;")
        l = QVBoxLayout(c)
        v = QLabel(f"<b>{val}</b>")
        v.setFont(QFont(FONT, 22))
        v.setStyleSheet(f"color: {ACCENT};")
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(v)
        t = QLabel(title)
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        l.addWidget(t)
        setattr(self, f"_s_{title}", v)
        return c

    def _load_data(self):
        s = get_stats()
        self._s_流程优化.setText(str(s["flow_optimizations"]))
        self._s_新增工具.setText(str(s["tool_count"]))
        self._s_固化模板.setText(str(s["template_count"]))

        self.tl_list.clear()
        for log in list_logs():
            m = {"flow": "流程优化", "tool": "工具新增", "template": "模板固化", "weight": "权重迭代"}
            self.tl_list.addItem(f"[{log['evo_time']}] {m.get(log['evo_type'], log['evo_type'])}: {log['before_content'][:25]} → {log['after_content'][:25]}")
        if not list_logs():
            self.tl_list.addItem("暂无演化记录")

        self.wt_list.clear()
        for h in get_top_habits(10):
            self.wt_list.addItem(f"  {h['habit_key']:<10} {h['weight']:.1f}  {'█' * int(h['weight'])}")
        if not get_top_habits(10):
            self.wt_list.addItem("暂无数据")

    def _filter(self, text: str):
        self.tl_list.clear()
        rev = {"流程优化": "flow", "工具新增": "tool", "模板固化": "template", "权重迭代": "weight"}
        et = rev.get(text, "")
        logs = list_logs(evo_type=et) if et else list_logs()
        m = {"flow": "流程优化", "tool": "工具新增", "template": "模板固化", "weight": "权重迭代"}
        for log in logs:
            self.tl_list.addItem(f"[{log['evo_time']}] {m.get(log['evo_type'], log['evo_type'])}: {log['before_content'][:25]} → {log['after_content'][:25]}")
        if not logs:
            self.tl_list.addItem("该类型暂无记录")
