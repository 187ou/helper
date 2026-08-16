"""BM25 全文索引：基于 rank_bm25 实现关键词精确检索（支持增量更新）。"""
import json
import logging
import os
import pickle
import threading
from pathlib import Path
from typing import Any

from config.path_config import CHROMA_DIR
from memory_store.chroma_kb import COLLECTIONS, list_documents, search as vec_search

logger = logging.getLogger(__name__)

_INDEX_PATH = Path(CHROMA_DIR) / "bm25_index.pkl"
_bm25 = None
_doc_list: list[dict[str, Any]] | None = None  # 与 BM25 索引对应的文档列表
_index_lock = threading.Lock()  # 保护索引的线程安全


def _tokenize(text: str) -> list[str]:
    """简单分词：按非字母数字中文切分。"""
    import re
    return [t.lower() for t in re.findall(r'[一-鿿]+|[a-z0-9]+', text) if len(t) > 1]


def build_index():
    """从 Chroma 已有文档构建 BM25 索引。"""
    global _bm25, _doc_list
    try:
        from rank_bm25 import BM25Okapi
    except ImportError:
        logger.warning("rank_bm25 未安装，BM25 检索不可用")
        return

    docs = []
    _doc_list = []
    for cat in COLLECTIONS:
        cat_docs = list_documents(category=cat)
        for d in cat_docs:
            # 从 Chroma 获取切片文本
            from memory_store.chroma_kb import get_collection
            coll = get_collection(cat)
            if coll:
                try:
                    all_data = coll.get(where={"file_path": d["file_path"]})
                    for doc_text in all_data.get("documents", []):
                        tokens = _tokenize(doc_text)
                        if tokens:
                            docs.append(tokens)
                            _doc_list.append({
                                "text": doc_text,
                                "file_name": d["file_name"],
                                "file_path": d["file_path"],
                                "category": cat,
                            })
                except Exception:
                    pass

    if docs:
        _bm25 = BM25Okapi(docs)
        _save_index()
        logger.info("BM25 索引构建完成: %d 个文档", len(docs))
    else:
        logger.info("BM25 索引为空（知识库无文档）")


def _save_index():
    """持久化索引。"""
    if _bm25 is None:
        return
    try:
        _INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_INDEX_PATH, "wb") as f:
            pickle.dump({"bm25": _bm25, "docs": _doc_list}, f)
    except Exception as e:
        logger.warning("BM25 索引保存失败: %s", e)


def _rebuild_and_save() -> None:
    """用当前 _doc_list 重建 BM25 模型并持久化。"""
    global _bm25
    if not _doc_list:
        _bm25 = None
        return
    try:
        from rank_bm25 import BM25Okapi
        tokenized = [_tokenize(d["text"]) for d in _doc_list]
        _bm25 = BM25Okapi(tokenized)
        _save_index()
    except ImportError:
        pass


# ── 增量更新 API ──

def add_chunks_to_index(file_path: str, file_name: str, category: str,
                        chunks: list[str], replace: bool = True) -> int:
    """增量添加文档切片到 BM25 索引。

    在 Chroma 向量库新增文档后调用，保持 BM25 与向量库同步。

    Args:
        file_path: 文件路径（唯一标识）
        file_name: 显示名
        category: 分区 key
        chunks: 文档切片文本列表
        replace: 若为 True，先移除同文件旧切片（更新场景）

    Returns:
        新增的切片数量
    """
    global _doc_list

    with _index_lock:
        # 确保索引已初始化
        ensure_index_locked()

        if _doc_list is None:
            _doc_list = []

        # 如果是更新场景，先移除旧切片
        if replace:
            removed = sum(1 for d in _doc_list if d.get("file_path") == file_path)
            if removed > 0:
                _doc_list = [d for d in _doc_list if d.get("file_path") != file_path]
                logger.info("BM25 移除旧切片: %s (%d 条)", file_path, removed)

        # 添加新切片
        added = 0
        for chunk_text in chunks:
            tokens = _tokenize(chunk_text)
            if tokens:  # 只索引有意义的切片
                _doc_list.append({
                    "text": chunk_text,
                    "file_name": file_name or file_path,
                    "file_path": file_path,
                    "category": category,
                })
                added += 1

        if added > 0:
            _rebuild_and_save()
            logger.info("BM25 增量更新: +%d 切片（总计 %d）", added, len(_doc_list))

        return added


def remove_document_from_index(file_path: str) -> int:
    """从 BM25 索引移除指定文档的所有切片。

    在 Chroma 向量库删除文档后调用。

    Args:
        file_path: 文件路径

    Returns:
        移除的切片数量
    """
    global _doc_list

    with _index_lock:
        ensure_index_locked()

        if not _doc_list:
            return 0

        new_list = [d for d in _doc_list if d.get("file_path") != file_path]
        removed = len(_doc_list) - len(new_list)

        if removed > 0:
            _doc_list = new_list
            _rebuild_and_save()
            logger.info("BM25 移除文档: %s (%d 切片，剩余 %d）",
                        file_path, removed, len(_doc_list))

        return removed


def ensure_index_locked() -> None:
    """确保索引已初始化（调用者必须持有 _index_lock）。"""
    global _bm25, _doc_list
    if _bm25 is not None:
        return
    if not _load_index():
        build_index()


def _load_index():
    """加载索引。"""
    global _bm25, _doc_list
    if not _INDEX_PATH.exists():
        return False
    try:
        with open(_INDEX_PATH, "rb") as f:
            data = pickle.load(f)
        _bm25 = data["bm25"]
        _doc_list = data["docs"]
        return True
    except Exception as e:
        logger.warning("BM25 索引加载失败: %s", e)
        return False


def ensure_index():
    """确保索引可用（线程安全）。"""
    global _bm25
    if _bm25 is not None:
        return
    with _index_lock:
        ensure_index_locked()


def search_bm25(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """BM25 全文检索（线程安全）。"""
    import numpy as np

    with _index_lock:
        ensure_index_locked()
        if _bm25 is None or not _doc_list:
            return []

        tokens = _tokenize(query)
        if not tokens:
            return []

        scores = _bm25.get_scores(tokens)
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            if scores[idx] <= 0:
                continue
            doc = _doc_list[idx]
            results.append({
                "text": doc["text"],
                "file_name": doc["file_name"],
                "file_path": doc["file_path"],
                "category": doc["category"],
                "score": float(scores[idx]),
            })
        return results


def hybrid_search(query: str, category: str = "", top_k: int = 5, alpha: float = 0.5) -> list[dict[str, Any]]:
    """混合检索：向量 + BM25，RRF 融合排序。

    Args:
        query: 查询文本
        category: 分区过滤
        top_k: 返回数量
        alpha: 向量权重（0=纯BM25, 1=纯向量）
    """
    # 向量检索
    vec_results = vec_search(query, category=category, top_k=top_k * 2)

    # BM25 检索
    bm25_results = search_bm25(query, top_k=top_k * 2)
    if category:
        bm25_results = [r for r in bm25_results if r.get("category") == category]

    # RRF 融合
    return _reciprocal_rank_fusion(vec_results, bm25_results, top_k, alpha)


def _reciprocal_rank_fusion(vec_results: list[dict], bm25_results: list[dict],
                            top_k: int, alpha: float, k: int = 60) -> list[dict]:
    """RRF（Reciprocal Rank Fusion）融合多路结果。"""
    scores: dict[str, float] = {}
    texts: dict[str, dict] = {}

    # 向量结果排名
    for rank, r in enumerate(vec_results):
        key = r.get("text", "")[:100]  # 用文本前缀做去重 key
        scores[key] = scores.get(key, 0) + alpha * (1.0 / (k + rank + 1))
        texts[key] = r

    # BM25 结果排名
    for rank, r in enumerate(bm25_results):
        key = r.get("text", "")[:100]
        scores[key] = scores.get(key, 0) + (1 - alpha) * (1.0 / (k + rank + 1))
        if key not in texts:
            texts[key] = r

    # 排序
    sorted_keys = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)[:top_k]
    return [texts[k] for k in sorted_keys if k in texts]


# 启动时尝试加载索引
try:
    ensure_index()
except Exception:
    pass
