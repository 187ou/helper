"""对话页：极简。"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QLabel, QProgressBar
from PyQt6.QtCore import QThread, pyqtSignal
from agent_core.task_scheduler import run as run_task
from config.settings import is_llm_configured
from gui.style import BG, TEXT, TEXT_SEC, TEXT_MUTED, BORDER, ACCENT


class Worker(QThread):
    done = pyqtSignal(object)
    def __init__(self, text): super().__init__(); self.text = text
    def run(self): self.done.emit(run_task(self.text))


class PageChat(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.w = None
        l = QVBoxLayout(self)
        l.setContentsMargins(28, 24, 28, 24); l.setSpacing(14)

        h = QLabel("对话")
        h.setStyleSheet(f"font-size:18px; font-weight:bold; color:{TEXT};")
        l.addWidget(h)

        s = QLabel("输入指令，AI 自动执行")
        s.setStyleSheet(f"color:{TEXT_MUTED}; font-size:12px; margin-bottom:8px;")
        l.addWidget(s)

        # 日志
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("执行日志...")
        self.log.setMinimumHeight(200)
        self.log.setStyleSheet(f"""
            QTextEdit {{
                background:#fafafa; border:1px solid {BORDER};
                border-radius:8px; padding:12px; line-height:1.6;
            }}
        """)
        l.addWidget(self.log, 1)

        # 进度
        self.prog = QProgressBar()
        self.prog.setRange(0, 100); self.prog.setValue(0)
        self.prog.setTextVisible(False)
        l.addWidget(self.prog)

        # 输入
        inp = QHBoxLayout()
        self.input = QTextEdit()
        self.input.setPlaceholderText("输入指令...")
        self.input.setMaximumHeight(56)
        self.input.setStyleSheet(f"""
            QTextEdit {{
                background:#fafafa; border:1px solid {BORDER};
                border-radius:6px; padding:8px 12px;
            }}
            QTextEdit:focus {{ border-color:{ACCENT}; background:#fff; }}
        """)
        inp.addWidget(self.input)

        btns = QVBoxLayout()
        self.send_btn = QPushButton("发送")
        self.send_btn.setFixedSize(64, 34)
        self.send_btn.clicked.connect(self._send)
        btns.addWidget(self.send_btn)
        inp.addLayout(btns)
        l.addLayout(inp)

    def _send(self):
        t = self.input.toPlainText().strip()
        if not t: return
        if not is_llm_configured():
            self.log.append('<span style="color:#dc2626;">⚠️ 请先在「设置」配置 API Key</span>')
            return
        self.input.clear()
        self.log.append(f"<b>{t}</b>")
        self.send_btn.setEnabled(False); self.send_btn.setText("执行中")
        self.prog.setValue(0)
        self.w = Worker(t)
        self.w.done.connect(self._done)
        self.w.start()

    def _done(self, r):
        self.send_btn.setEnabled(True); self.send_btn.setText("发送")
        for lg in r.get("logs", []):
            self.log.append(f"  <span style='color:{TEXT_SEC};'>{lg}</span>")
        self.log.append(f"<b>✓ 完成 · {r.get('cost_time', 0):.1f}s</b>")
        self.prog.setValue(100)

    def set_input_and_send(self, text):
        self.input.setPlainText(text); self._send()
