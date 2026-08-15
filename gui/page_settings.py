"""设置页：极简。"""
import logging
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QComboBox, QPushButton, QLabel, QCheckBox, QMessageBox
from PyQt6.QtCore import QThread, pyqtSignal
from config.settings import load_config, set
from gui.style import TEXT, TEXT_SEC, TEXT_MUTED, BORDER, SUCCESS, DANGER

logger = logging.getLogger(__name__)

PRESETS = {
    "LongCat": ("https://api.longcat.chat/openai/v1", "LongCat-2.0"),
    "OpenAI": ("https://api.openai.com/v1", "gpt-4o-mini"),
    "DeepSeek": ("https://api.deepseek.com/v1", "deepseek-chat"),
    "Moonshot": ("https://api.moonshot.cn/v1", "moonshot-v1-8k"),
    "通义千问": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-turbo"),
    "Ollama": ("http://localhost:11434/v1", "llama3.2"),
}


class TestThread(QThread):
    done = pyqtSignal(bool, str)
    def __init__(self, url, key, model): super().__init__(); self.url, self.key, self.model = url, key, model
    def run(self):
        try:
            from openai import OpenAI
            c = OpenAI(base_url=self.url, api_key=self.key, timeout=12, max_retries=0)
            r = c.chat.completions.create(model=self.model, messages=[{"role":"user","content":"hi"}], max_tokens=5)
            self.done.emit(True, f"成功: {(r.choices[0].message.content or '')[:30]}")
        except Exception as e: self.done.emit(False, str(e)[:80])


class PageSettings(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.t = None
        l = QVBoxLayout(self)
        l.setContentsMargins(28, 24, 28, 24); l.setSpacing(12)

        h = QLabel("设置"); h.setStyleSheet("font-size:18px; font-weight:bold;"); l.addWidget(h)

        f = QFormLayout(); f.setSpacing(10)

        self.combo = QComboBox()
        self.combo.addItems(["自定义"] + list(PRESETS.keys()))
        self.combo.currentTextChanged.connect(self._preset)
        f.addRow("厂商", self.combo)

        self.url = QLineEdit(); self.url.setPlaceholderText("https://api.example.com/v1")
        f.addRow("Base URL", self.url)

        self.key = QLineEdit(); self.key.setPlaceholderText("sk-...")
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        f.addRow("API Key", self.key)

        sk = QCheckBox("显示 Key"); sk.toggled.connect(lambda c: self.key.setEchoMode(QLineEdit.EchoMode.Normal if c else QLineEdit.EchoMode.Password))
        f.addRow("", sk)

        self.model = QLineEdit(); self.model.setPlaceholderText("model-name")
        f.addRow("模型", self.model)

        l.addLayout(l.addLayout(f) if False else f)

        br = QHBoxLayout()
        tb = QPushButton("测试"); tb.setProperty("text", "次级"); tb.clicked.connect(self._test)
        br.addWidget(tb)
        sv = QPushButton("保存"); sv.clicked.connect(self._save)
        br.addWidget(sv); br.addStretch()
        l.addLayout(br)

        self.res = QLabel(); self.res.setWordWrap(True)
        self.res.setStyleSheet(f"padding:8px; border-radius:6px; background:#fafafa;")
        self.res.setVisible(False)
        l.addWidget(self.res)
        l.addStretch()

        self._load()

    def _load(self):
        cfg = load_config()
        url, model = cfg.llm.base_url, cfg.llm.model_name
        for name, (u, m) in PRESETS.items():
            if u == url and m == model:
                self.combo.setCurrentText(name); break
        else:
            self.combo.setCurrentText("自定义")
        self.url.setText(url); self.key.setText(cfg.llm.api_key); self.model.setText(model)

    def _preset(self, name):
        if name in PRESETS:
            u, m = PRESETS[name]
            self.url.setText(u); self.model.setText(m)

    def _test(self):
        url, key, model = self.url.text().strip(), self.key.text().strip(), self.model.text().strip()
        if not all([url, key, model]): QMessageBox.warning(self, "提示", "请填写完整"); return
        self.res.setText("测试中..."); self.res.setVisible(True)
        self.t = TestThread(url, key, model); self.t.done.connect(self._tested); self.t.start()

    def _tested(self, ok, msg):
        self.res.setText(f"{'✅' if ok else '❌'} {msg}")
        self.res.setStyleSheet(f"padding:8px; border-radius:6px; background:{'#16a34a15' if ok else '#dc262615'}; color:{SUCCESS if ok else DANGER};")

    def _save(self):
        url, key, model = self.url.text().strip(), self.key.text().strip(), self.model.text().strip()
        if not all([url, key, model]): QMessageBox.warning(self, "提示", "请填写完整"); return
        set("llm.base_url", url); set("llm.api_key", key); set("llm.model_name", model)
        from agent_core.llm_client import reset_client; reset_client()
        QMessageBox.information(self, "成功", "配置已保存")
