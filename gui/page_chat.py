"""对话页面。"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QLabel, QProgressBar, QFrame
)
from PyQt6.QtCore import QThread, pyqtSignal

from agent_core.task_scheduler import run as run_task
from config.settings import is_llm_configured
from gui.style import (
    BG, BG_INPUT, BG_SIDEBAR, ACCENT, SUCCESS, DANGER,
    TEXT, TEXT_SEC, TEXT_MUTED, BORDER, title_font, mono_font
)


class TaskWorker(QThread):
    finished = pyqtSignal(object)

    def __init__(self, task_text: str):
        super().__init__()
        self.task_text = task_text

    def run(self):
        result = run_task(self.task_text)
        self.finished.emit(result)


class PageChat(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: TaskWorker | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        header = QLabel("💬 智能对话")
        header.setFont(title_font(17))
        layout.addWidget(header)

        sub = QLabel("输入自然语言指令，AI 自动拆解并执行")
        sub.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; margin-bottom: 4px;")
        layout.addWidget(sub)

        # DAG
        dag = QFrame()
        dag.setStyleSheet(f"background: {BG_SIDEBAR}; border: 1px solid {BORDER}; border-radius: 10px;")
        dl = QVBoxLayout(dag)
        dl.setContentsMargins(14, 12, 14, 12)
        dh = QLabel("📊 任务流程")
        dh.setStyleSheet(f"color: {TEXT_SEC}; font-weight: 500; font-size: 12px;")
        dl.addWidget(dh)

        self.dag_label = QLabel("等待任务输入...")
        self.dag_label.setWordWrap(True)
        self.dag_label.setFont(mono_font(11))
        self.dag_label.setStyleSheet(f"color: {TEXT_MUTED}; padding: 4px 0; line-height: 1.6;")
        dl.addWidget(self.dag_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        dl.addWidget(self.progress)
        layout.addWidget(dag)

        # 日志
        log = QFrame()
        log.setStyleSheet(f"background: {BG_SIDEBAR}; border: 1px solid {BORDER}; border-radius: 10px;")
        ll = QVBoxLayout(log)
        ll.setContentsMargins(14, 12, 14, 12)
        lh = QLabel("📋 执行日志")
        lh.setStyleSheet(f"color: {TEXT_SEC}; font-weight: 500; font-size: 12px;")
        ll.addWidget(lh)

        self.history = QTextEdit()
        self.history.setReadOnly(True)
        self.history.setPlaceholderText("执行日志...")
        self.history.setMinimumHeight(150)
        self.history.setStyleSheet(f"""
            QTextEdit {{
                background: {BG}; border: 1px solid {BORDER};
                border-radius: 8px; padding: 10px;
            }}
        """)
        ll.addWidget(self.history)
        layout.addWidget(log, stretch=1)

        # 输入
        inp = QFrame()
        inp.setStyleSheet(f"background: {BG_SIDEBAR}; border: 1px solid {BORDER}; border-radius: 10px;")
        il = QHBoxLayout(inp)
        il.setContentsMargins(10, 10, 10, 10)

        self.input_box = QTextEdit()
        self.input_box.setPlaceholderText("输入指令...")
        self.input_box.setMaximumHeight(60)
        il.addWidget(self.input_box)

        btns = QVBoxLayout()
        self.send_btn = QPushButton("发送")
        self.send_btn.setFixedSize(60, 36)
        self.send_btn.clicked.connect(self._on_send)
        btns.addWidget(self.send_btn)

        clr = QPushButton("清空")
        clr.setProperty("class", "ghost")
        clr.setFixedSize(60, 26)
        clr.clicked.connect(lambda: (self.history.clear(), self.dag_label.setText("等待任务输入..."), self.progress.setValue(0)))
        btns.addWidget(clr)
        btns.addStretch()
        il.addLayout(btns)
        layout.addWidget(inp)

    def _on_send(self):
        text = self.input_box.toPlainText().strip()
        if not text:
            return
        if not is_llm_configured():
            self.history.append(f'<span style="color: {DANGER};">⚠️ 请先在「设置」页面配置 API Key</span>')
            return
        self.input_box.clear()
        self.history.append(f'<b style="color: {ACCENT};">👤 {text}</b>')
        self.send_btn.setEnabled(False)
        self.send_btn.setText("执行中")
        self.progress.setValue(0)
        self.dag_label.setText("⏳ 正在拆解任务...")
        self._worker = TaskWorker(text)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_finished(self, result: dict):
        self.send_btn.setEnabled(True)
        self.send_btn.setText("发送")
        steps = result.get("steps", [])
        lines = []
        for i, s in enumerate(steps):
            icon = "✅" if i < len(steps) - 1 else "🔄"
            lines.append(f"  {icon} 步骤 {s['index']}: {s['name']}")
        self.dag_label.setText("\n".join(lines) if lines else "无步骤")

        for log in result.get("logs", []):
            self.history.append(f"  <span style='color: {TEXT_SEC};'>{log}</span>")
        sc = SUCCESS if result.get("status") == "success" else DANGER
        self.history.append(
            f"<b style='color: {sc};'>🤖 {result.get('status')} | 耗时 {result.get('cost_time', 0):.1f}s</b>"
        )
        self.progress.setValue(100)

    def set_input_and_send(self, text: str):
        self.input_box.setPlainText(text)
        self._on_send()
