"""API 配置页面。"""
import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QComboBox, QPushButton, QLabel, QGroupBox, QFrame, QMessageBox, QCheckBox
)
from PyQt6.QtCore import QThread, pyqtSignal
from config.settings import get, set, load_config
from gui.style import (
    BG, BG_SIDEBAR, ACCENT, SUCCESS, DANGER, TEXT_SEC, TEXT_MUTED, BORDER, title_font
)

logger = logging.getLogger(__name__)

PRESETS = {
    "自定义": {"url": "", "model": "", "note": "手动填写"},
    "LongCat": {"url": "https://api.longcat.chat/openai/v1", "model": "LongCat-2.0", "note": "默认"},
    "OpenAI": {"url": "https://api.openai.com/v1", "model": "gpt-4o-mini", "note": "需海外网络"},
    "DeepSeek": {"url": "https://api.deepseek.com/v1", "model": "deepseek-chat", "note": "性价比高"},
    "Moonshot": {"url": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k", "note": "Kimi"},
    "通义千问": {"url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-turbo", "note": "阿里云"},
    "智谱": {"url": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-4-flash", "note": "智谱AI"},
    "Ollama": {"url": "http://localhost:11434/v1", "model": "llama3.2", "note": "本地"},
}


class TestThread(QThread):
    done = pyqtSignal(bool, str)
    def __init__(self, url, key, model):
        super().__init__(); self.url, self.key, self.model = url, key, model
    def run(self):
        try:
            from openai import OpenAI
            c = OpenAI(base_url=self.url, api_key=self.key, timeout=15, max_retries=0)
            r = c.chat.completions.create(model=self.model, messages=[{"role": "user", "content": "hi"}], max_tokens=8)
            self.done.emit(True, f"成功: {(r.choices[0].message.content or '')[:40]}")
        except Exception as e:
            self.done.emit(False, str(e))


class PageSettings(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = None
        self._build()
        self._load()

    def _build(self):
        l = QVBoxLayout(self); l.setContentsMargins(24, 20, 24, 20); l.setSpacing(12)

        h = QLabel("⚙️ API 配置"); h.setFont(title_font(17)); l.addWidget(h)
        s = QLabel("配置 LLM API，支持多家厂商 OpenAI 兼容接口")
        s.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;"); l.addWidget(s)

        vb = QGroupBox("选择厂商"); vl = QFormLayout(vb)
        self.combo = QComboBox(); self.combo.addItems(list(PRESETS.keys()))
        self.combo.currentTextChanged.connect(self._vendor_changed)
        vl.addRow("厂商:", self.combo)
        self.note = QLabel(); self.note.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        vl.addRow("", self.note)
        l.addWidget(vb)

        ab = QGroupBox("API 参数"); al = QFormLayout(ab)
        self.url_edit = QLineEdit(); self.url_edit.setPlaceholderText("https://api.example.com/v1")
        al.addRow("Base URL:", self.url_edit)
        self.key_edit = QLineEdit(); self.key_edit.setPlaceholderText("sk-...")
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        al.addRow("API Key:", self.key_edit)
        kr = QHBoxLayout()
        self.show_key = QCheckBox("显示 Key"); self.show_key.toggled.connect(self._toggle_key)
        kr.addWidget(self.show_key); kr.addStretch()
        al.addRow("", kr)
        self.model_edit = QLineEdit(); self.model_edit.setPlaceholderText("model-name")
        al.addRow("模型:", self.model_edit)
        l.addWidget(ab)

        br = QHBoxLayout()
        self.test_btn = QPushButton("🔌 测试"); self.test_btn.setProperty("class", "secondary")
        self.test_btn.clicked.connect(self._test)
        br.addWidget(self.test_btn)
        self.save_btn = QPushButton("💾 保存"); self.save_btn.clicked.connect(self._save)
        br.addWidget(self.save_btn); br.addStretch()
        l.addLayout(br)

        self.result = QLabel(); self.result.setWordWrap(True)
        self.result.setStyleSheet(f"padding: 10px; border-radius: 8px; background: {BG_SIDEBAR};")
        self.result.setVisible(False)
        l.addWidget(self.result)
        l.addStretch()

    def _load(self):
        cfg = load_config(); url = cfg.get("api_base_url", ""); model = cfg.get("model_name", "")
        matched = False
        for name, p in PRESETS.items():
            if name == "自定义": continue
            if p["url"] == url and p["model"] == model:
                self.combo.setCurrentText(name); matched = True; break
        if not matched: self.combo.setCurrentText("自定义")
        self.url_edit.setText(url); self.key_edit.setText(cfg.get("api_key", "")); self.model_edit.setText(model)

    def _vendor_changed(self, name):
        p = PRESETS.get(name)
        if not p: return
        self.note.setText(p.get("note", ""))
        if p["url"]: self.url_edit.setText(p["url"])
        if p["model"]: self.model_edit.setText(p["model"])

    def _toggle_key(self, checked):
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)

    def _test(self):
        url, key, model = self.url_edit.text().strip(), self.key_edit.text().strip(), self.model_edit.text().strip()
        if not all([url, key, model]):
            QMessageBox.warning(self, "提示", "请填写完整"); return
        self.test_btn.setEnabled(False); self.test_btn.setText("测试中...")
        self.result.setText("连接中..."); self.result.setStyleSheet(f"padding:10px;border-radius:8px;background:{BG_SIDEBAR};")
        self.result.setVisible(True)
        self._thread = TestThread(url, key, model)
        self._thread.done.connect(self._test_done)
        self._thread.start()

    def _test_done(self, ok, msg):
        self.test_btn.setEnabled(True); self.test_btn.setText("🔌 测试")
        if ok:
            self.result.setText(f"✅ {msg}")
            self.result.setStyleSheet(f"padding:10px;border-radius:8px;background:#16a34a18;color:{SUCCESS};")
        else:
            self.result.setText(f"❌ {msg}")
            self.result.setStyleSheet(f"padding:10px;border-radius:8px;background:#dc262618;color:{DANGER};")

    def _save(self):
        url, key, model = self.url_edit.text().strip(), self.key_edit.text().strip(), self.model_edit.text().strip()
        if not all([url, key, model]):
            QMessageBox.warning(self, "提示", "请填写完整"); return
        set("api_base_url", url); set("api_key", key); set("model_name", model)
        from agent_core.llm_client import reset_client; reset_client()
        QMessageBox.information(self, "成功", "配置已保存")
