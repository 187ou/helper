"""知识库：极简。"""
import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QLabel, QLineEdit, QTextEdit, QFileDialog, QInputDialog
)
from PyQt6.QtCore import QThread, pyqtSignal
from memory_store.chroma_kb import add_document, search, list_documents, get_stats, COLLECTIONS, delete_document
from config.app_const import KBCategory
from gui.style import TEXT, TEXT_SEC, TEXT_MUTED, BORDER, ACCENT, DANGER

logger = logging.getLogger(__name__)
KB = [("工作文档", KBCategory.WORK_DOC.value), ("合同", KBCategory.CONTRACT.value),
      ("个人", KBCategory.PERSONAL.value), ("笔记", KBCategory.NOTE.value), ("账单", KBCategory.BILL.value)]


class IndexWorker(QThread):
    done = pyqtSignal(dict)
    def __init__(self, fp, cat): super().__init__(); self.fp, self.cat = fp, cat
    def run(self):
        text = self._extract(self.fp)
        if not text.strip(): self.done.emit({"status": "empty"}); return
        r = add_document(self.fp, text, self.cat, file_name=Path(self.fp).name)
        self.done.emit(r)

    def _extract(self, fp):
        s = Path(fp).suffix.lower()
        try:
            if s == ".pdf":
                from tools.pdf_tools import extract_text; return extract_text(fp)
            elif s in (".txt", ".md", ".csv"):
                for e in ["utf-8", "gbk"]:
                    try:
                        with open(fp, "r", encoding=e) as f: return f.read()
                    except UnicodeDecodeError: continue
            elif s == ".xlsx":
                from tools.excel_tools import read_excel
                return "\n".join("\t".join(str(c) for c in r) for r in read_excel(fp))
        except Exception: pass
        return ""


class PageKB(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.workers = []
        l = QVBoxLayout(self)
        l.setContentsMargins(28, 24, 28, 24); l.setSpacing(12)

        h = QLabel("知识库"); h.setStyleSheet("font-size:18px; font-weight:bold;"); l.addWidget(h)

        tb = QHBoxLayout()
        up = QPushButton("+ 上传"); up.clicked.connect(self._upload); tb.addWidget(up)
        ref = QPushButton("刷新"); ref.setProperty("text", "次级")
        ref.clicked.connect(self._load); tb.addWidget(ref)
        tb.addStretch()
        self.status = QLabel(""); self.status.setStyleSheet(f"color:{TEXT_MUTED};")
        tb.addWidget(self.status)
        l.addLayout(tb)

        sr = QHBoxLayout()
        self.si = QLineEdit(); self.si.setPlaceholderText("检索...")
        self.si.returnPressed.connect(self._search); sr.addWidget(self.si)
        sb = QPushButton("搜索"); sb.setProperty("text", "次级"); sb.clicked.connect(self._search)
        sr.addWidget(sb); l.addLayout(sr)

        self.res = QTextEdit(); self.res.setReadOnly(True)
        self.res.setPlaceholderText("结果..."); self.res.setMaximumHeight(80)
        self.res.setStyleSheet(f"background:#fafafa; border:1px solid {BORDER}; border-radius:6px; padding:8px;")
        l.addWidget(self.res)

        self.tbl = QTableWidget(0, 4)
        self.tbl.setHorizontalHeaderLabels(["文件", "分类", "切片", "操作"])
        self.tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        l.addWidget(self.tbl)
        self._load()

    def _load(self):
        self.tbl.setRowCount(0)
        docs = list_documents()
        self.tbl.setRowCount(len(docs))
        for i, d in enumerate(docs):
            self.tbl.setItem(i, 0, QTableWidgetItem(d["file_name"]))
            self.tbl.setItem(i, 1, QTableWidgetItem(COLLECTIONS.get(d["category"], d["category"])))
            self.tbl.setItem(i, 2, QTableWidgetItem(str(d["total_chunks"])))
            b = QPushButton("删除"); b.setProperty("text", "次级")
            b.setFixedHeight(22); b.setStyleSheet("font-size:11px; color:#dc2626;")
            b.clicked.connect(lambda ch, fp=d["file_path"], c=d["category"]: self._del(fp, c))
            self.tbl.setCellWidget(i, 3, b)
        self.status.setText(f"共 {len(docs)} 个文档")

    def _upload(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择", "", "文件 (*.txt *.md *.pdf *.docx *.xlsx)")
        if not files: return
        cat = KBCategory.WORK_DOC.value
        item, ok = QInputDialog.getItem(self, "分类", "分类:", [n for n, _ in KB], 0, False)
        if ok and item:
            for n, k in KB:
                if n == item: cat = k; break
        for f in files:
            w = IndexWorker(f, cat); w.done.connect(lambda r: self._load())
            w.start(); self.workers.append(w)

    def _search(self):
        q = self.si.text().strip()
        if not q: return
        self.res.setText("搜索中...")
        r = search(q, top_k=5)
        if not r: self.res.setText("无结果"); return
        self.res.setText("\n".join(f"• [{x['file_name']}] {x['text'][:80]}..." for x in r))

    def _del(self, fp, cat): delete_document(fp, cat); self._load()
