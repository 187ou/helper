"""知识库管理。"""
import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QLabel, QLineEdit, QTextEdit,
    QFileDialog, QInputDialog
)
from PyQt6.QtCore import QThread, pyqtSignal
from memory_store.chroma_kb import add_document, search, list_documents, get_stats, COLLECTIONS, delete_document
from config.app_const import KBCategory
from gui.style import (
    BG, BG_SIDEBAR, ACCENT, DANGER, TEXT_SEC, TEXT_MUTED, BORDER, title_font
)

logger = logging.getLogger(__name__)
KB_TREE = [("工作文档", KBCategory.WORK_DOC.value), ("合同票据", KBCategory.CONTRACT.value),
           ("个人资料", KBCategory.PERSONAL.value), ("笔记", KBCategory.NOTE.value), ("账单", KBCategory.BILL.value)]
SUPPORTED_EXT = {".txt", ".md", ".pdf", ".docx", ".xlsx", ".csv"}


class IndexWorker(QThread):
    finished = pyqtSignal(dict)
    def __init__(self, fp, cat):
        super().__init__(); self.fp, self.cat = fp, cat
    def run(self):
        self.finished.emit(index_file(self.fp, self.cat))


def _extract(fp):
    s = Path(fp).suffix.lower()
    try:
        if s == ".pdf":
            from tools.pdf_tools import extract_text; return extract_text(fp)
        elif s in (".txt", ".md", ".csv"):
            for e in ["utf-8", "gbk", "latin-1"]:
                try:
                    with open(fp, "r", encoding=e) as f: return f.read()
                except UnicodeDecodeError: continue
            return ""
        elif s == ".xlsx":
            from tools.excel_tools import read_excel
            return "\n".join("\t".join(str(c) for c in r) for r in read_excel(fp))
        elif s == ".docx":
            try:
                import docx; return "\n".join(p.text for p in docx.Document(fp).paragraphs)
            except ImportError: return ""
    except Exception as e:
        logger.error("提取失败 %s: %s", fp, e)
    return ""


def index_file(fp, cat):
    text = _extract(fp)
    if not text.strip(): return {"status": "empty", "file": fp}
    return add_document(fp, text, cat, file_name=Path(fp).name)


class PageKB(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers = []
        self._build_ui()
        self._load()

    def _build_ui(self):
        l = QVBoxLayout(self)
        l.setContentsMargins(24, 20, 24, 20)
        l.setSpacing(12)

        h = QLabel("📚 知识库"); h.setFont(title_font(17)); l.addWidget(h)

        tb = QHBoxLayout()
        self.up_btn = QPushButton("+ 上传"); self.up_btn.clicked.connect(self._upload)
        tb.addWidget(self.up_btn)
        ref = QPushButton("刷新"); ref.setProperty("class", "secondary")
        ref.clicked.connect(self._load); tb.addWidget(ref)
        tb.addStretch()
        self.status = QLabel(""); self.status.setStyleSheet(f"color: {TEXT_MUTED};")
        tb.addWidget(self.status)
        l.addLayout(tb)

        sr = QHBoxLayout()
        self.search_in = QLineEdit(); self.search_in.setPlaceholderText("语义检索...")
        self.search_in.returnPressed.connect(self._search)
        sr.addWidget(self.search_in)
        sb = QPushButton("检索"); sb.setProperty("class", "secondary")
        sb.clicked.connect(self._search); sr.addWidget(sb)
        l.addLayout(sr)

        self.result = QTextEdit(); self.result.setReadOnly(True)
        self.result.setPlaceholderText("检索结果..."); self.result.setMaximumHeight(100)
        self.result.setStyleSheet(f"background: {BG_SIDEBAR}; border: 1px solid {BORDER}; border-radius: 8px; padding: 8px;")
        l.addWidget(self.result)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["文件名", "分类", "切片数", "路径", "操作"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        l.addWidget(self.table)

    def _load(self):
        self.table.setRowCount(0)
        docs = list_documents()
        self.table.setRowCount(len(docs))
        for i, d in enumerate(docs):
            self.table.setItem(i, 0, QTableWidgetItem(d["file_name"]))
            self.table.setItem(i, 1, QTableWidgetItem(COLLECTIONS.get(d["category"], d["category"])))
            self.table.setItem(i, 2, QTableWidgetItem(str(d["total_chunks"])))
            self.table.setItem(i, 3, QTableWidgetItem(d["file_path"]))
            del_btn = QPushButton("删除"); del_btn.setProperty("class", "ghost")
            del_btn.setFixedHeight(24)
            del_btn.setStyleSheet(f"color: {DANGER}; font-size: 11px;")
            del_btn.clicked.connect(lambda ch, fp=d["file_path"], c=d["category"]: self._delete(fp, c))
            self.table.setCellWidget(i, 4, del_btn)
        self.status.setText(f"已索引: {sum(get_stats().values())} 个文档")

    def _upload(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择文件", "", "文件 (*.txt *.md *.pdf *.docx *.xlsx *.csv)")
        if not files: return
        cat = KBCategory.WORK_DOC.value
        item, ok = QInputDialog.getItem(self, "选择分类", "分类:", [n for n, _ in KB_TREE], 0, False)
        if ok and item:
            for n, k in KB_TREE:
                if n == item: cat = k; break
        for f in files:
            w = IndexWorker(f, cat); w.finished.connect(self._indexed)
            w.start(); self._workers.append(w)

    def _indexed(self, r):
        self._load()
        self.status.setText(f"索引完成: {r.get('chunks', 0)} 切片" if r.get("status") == "ok"
                            else "文件为空" if r.get("status") == "empty" else "索引失败")

    def _search(self):
        q = self.search_in.text().strip()
        if not q: return
        self.result.setText("检索中...")
        results = search(q, top_k=5)
        if not results: self.result.setText("未找到"); return
        self.result.setText("\n\n".join(
            f"{i+1}. [{r['file_name']}] ({r['score']:.2f})\n   {r['text'][:120]}..."
            for i, r in enumerate(results)))

    def _delete(self, fp, cat):
        delete_document(fp, cat); self._load()
