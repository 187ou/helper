"""Chroma 向量知识库：切片、嵌入、分区存储、语义检索。"""
import hashlib
import logging
import time
from typing import Any

from config.path_config import CHROMA_DIR, ensure_dirs
from config.app_const import KBCategory

logger = logging.getLogger(__name__)

# 分区：key=英文 collection 名（Chroma 要求），value=中文显示名
COLLECTIONS = {
    "work_doc": "工作文档",
    "contract": "合同票据",
    "personal": "个人笔记",
    "note": "笔记",
    "bill": "账单",
}

# category key → collection 名（兼容 KBCategory 枚举）
_CATEGORY_TO_COLL = {
    KBCategory.WORK_DOC.value: "work_doc",
    KBCategory.CONTRACT.value: "contract",
    KBCategory.PERSONAL.value: "personal",
    KBCategory.NOTE.value: "note",
    KBCategory.BILL.value: "bill",
}


def _coll_name(category: str) -> str:
    """将 category key 转为英文 collection 名。"""
    return _CATEGORY_TO_COLL.get(category, category)

# 切片规则（与 request.md 一致：512字符切片、128重叠）
CHUNK_SIZE = 512
CHUNK_OVERLAP = 128

_client = None
_embedding_fn = None


def get_client():
    """获取/初始化持久化 Chroma 客户端。"""
    global _client
    if _client is None:
        try:
            import chromadb
            ensure_dirs()
            _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            logger.info("Chroma 客户端初始化: %s", CHROMA_DIR)
        except Exception as e:
            logger.error("Chroma 初始化失败: %s", e)
            return None
    return _client


def get_embedding_fn():
    """获取嵌入函数（使用 Chroma 内置 ONNX，无需下载模型）。"""
    global _embedding_fn
    if _embedding_fn is None:
        try:
            from chromadb.utils.embedding_functions import ONNXMiniLM6v2
            _embedding_fn = ONNXMiniLM6v2()
            logger.info("ONNX 嵌入函数初始化完成")
        except Exception as e:
            logger.warning("ONNX 嵌入不可用: %s，回退到 sentence-transformers", e)
            try:
                from sentence_transformers import SentenceTransformer
                model = SentenceTransformer("all-MiniLM-L6-v2")
                _embedding_fn = model
            except Exception as e2:
                logger.error("嵌入模型加载失败: %s", e2)
                return None
    return _embedding_fn


def get_collection(category: str):
    """获取指定分区 collection，不存在则创建。"""
    client = get_client()
    if client is None:
        return None
    name = _coll_name(category)
    try:
        return client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )
    except Exception as e:
        logger.warning("获取 collection %s 失败: %s", name, e)
        return None


def list_collections() -> list[str]:
    """列出所有分区 key。"""
    return list(COLLECTIONS.keys())


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """将文本切分为重叠片段。"""
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start += size - overlap
    return chunks


def embed_texts(texts: list[str]) -> list[list[float]]:
    """将文本列表编码为向量。"""
    fn = get_embedding_fn()
    if fn is None:
        return []
    # sentence-transformers 模型
    if hasattr(fn, "encode"):
        return fn.encode(texts, show_progress_bar=False).tolist()
    # 其他可调用嵌入函数
    result = fn(texts)
    if hasattr(result, "tolist"):
        return result.tolist()
    return result


def _make_doc_id(file_path: str, chunk_index: int) -> str:
    """生成唯一文档块 ID。"""
    raw = f"{file_path}::{chunk_index}"
    return hashlib.md5(raw.encode()).hexdigest()


def add_document(file_path: str, text: str, category: str, file_name: str = "") -> dict[str, Any]:
    """将文档切片、向量化后入库。

    Args:
        file_path: 文件路径（作为标识）
        text: 文档全文
        category: 分区 key
        file_name: 显示名
    """
    if not text.strip():
        return {"status": "empty", "chunks": 0}

    collection = get_collection(category)
    if collection is None:
        return {"status": "error", "message": "Chroma 未就绪"}

    # 文本降噪 + 切片
    from memory_store.text_cleaner import clean_chunks
    chunks = clean_chunks(chunk_text(text))
    if not chunks:
        return {"status": "empty", "chunks": 0}

    # 嵌入
    vectors = embed_texts(chunks)
    if not vectors:
        return {"status": "error", "message": "嵌入失败"}

    # 生成 IDs 和元数据
    ids = [_make_doc_id(file_path, i) for i in range(len(chunks))]
    metadatas = [
        {
            "file_path": file_path,
            "file_name": file_name or file_path,
            "category": category,
            "chunk_index": i,
            "total_chunks": len(chunks),
        }
        for i in range(len(chunks))
    ]

    # 入库（去重：先删后插）
    try:
        existing = collection.get(where={"file_path": file_path})
        if existing["ids"]:
            collection.delete(ids=existing["ids"])
    except Exception:
        pass

    collection.add(ids=ids, documents=chunks, embeddings=vectors, metadatas=metadatas)

    # 增量更新 BM25 索引（保持与向量库同步）
    try:
        from memory_store.bm25_index import add_chunks_to_index
        add_chunks_to_index(file_path, file_name or file_path, category, chunks, replace=True)
    except Exception as e:
        logger.warning("BM25 增量更新失败（不影响向量检索）: %s", e)

    logger.info("入库: %s (%d 切片) → %s", file_name or file_path, len(chunks), category)
    return {"status": "ok", "chunks": len(chunks), "category": category}


def search(query: str, category: str = "", top_k: int = 5, hybrid: bool = True) -> list[dict[str, Any]]:
    """检索（支持混合检索 + 引用溯源）。

    Args:
        query: 查询文本
        category: 分区 key，空则全库搜索
        top_k: 返回条数
        hybrid: 是否启用 BM25 + 向量混合检索

    Returns:
        结果列表，每项含 text/score/source/highlight 等字段
    """
    if not query.strip():
        return []

    if hybrid:
        try:
            from memory_store.bm25_index import hybrid_search
            from config.settings import get_kb_config
            kb_cfg = get_kb_config()
            results = hybrid_search(query, category=category, top_k=top_k, alpha=kb_cfg.get("hybrid_alpha", 0.5))
            # 为混合检索结果添加引用溯源
            return _add_citations(results, query)
        except Exception as e:
            logger.warning("混合检索失败，回退到纯向量: %s", e)

    # 纯向量检索
    query_vec = embed_texts([query])
    if not query_vec:
        return []

    results = []
    if category:
        collections = [(category, get_collection(category))]
    else:
        collections = [(k, get_collection(k)) for k in COLLECTIONS]

    for cat_key, coll in collections:
        if coll is None:
            continue
        try:
            res = coll.query(query_embeddings=query_vec, n_results=top_k)
            docs = res.get("documents", [[]])[0]
            metas = res.get("metadatas", [[]])[0]
            dists = res.get("distances", [[]])[0]
            for doc, meta, dist in zip(docs, metas, dists):
                results.append({
                    "text": doc,
                    "category": cat_key,
                    "file_name": meta.get("file_name", ""),
                    "file_path": meta.get("file_path", ""),
                    "chunk_index": meta.get("chunk_index", 0),
                    "score": 1 - dist,  # cosine distance → similarity
                })
        except Exception as e:
            logger.warning("检索 %s 失败: %s", cat_key, e)

    results.sort(key=lambda x: x["score"], reverse=True)
    return _add_citations(results[:top_k], query)


def _add_citations(results: list[dict], query: str) -> list[dict[str, Any]]:
    """为检索结果添加引用溯源信息（来源 + 高亮片段）。

    前端可据此展示：
    - source_label: "来自《xxx.pdf》第 N 段"
    - highlight: 匹配关键词的高亮文本
    """
    if not results or not query:
        return results

    # 提取查询关键词（用于高亮）
    query_keywords = _extract_keywords(query)

    for r in results:
        # 来源信息
        file_name = r.get("file_name", "")
        chunk_idx = r.get("chunk_index", 0)
        r["source_label"] = f"《{file_name}》第 {chunk_idx + 1} 段" if file_name else f"第 {chunk_idx + 1} 段"

        # 高亮匹配片段
        text = r.get("text", "")
        r["highlight"] = _extract_relevant_snippet(text, query_keywords)

    return results


def _extract_keywords(query: str) -> list[str]:
    """从查询中提取关键词（用于高亮）。"""
    import re
    # 提取中文词组（2-8 字）和英文单词
    keywords = []

    # 中文：按常见词长提取
    for length in range(min(8, len(query)), 1, -1):
        for i in range(len(query) - length + 1):
            word = query[i:i + length]
            if '一' <= word[0] <= '鿿':  # 以中文开头
                keywords.append(word)

    # 英文单词
    keywords.extend(re.findall(r'[a-zA-Z]+', query))

    # 去重保持顺序
    seen = set()
    unique = []
    for kw in keywords:
        if kw not in seen and len(kw) > 1:
            seen.add(kw)
            unique.append(kw)

    return unique[:10]  # 最多 10 个关键词


def _extract_relevant_snippet(text: str, keywords: list[str], snippet_len: int = 100) -> str:
    """从文本中提取包含关键词的相关片段（用于高亮展示）。"""
    if not text or not keywords:
        return text[:snippet_len]

    # 找到第一个关键词出现的位置
    best_pos = -1
    best_kw = ""
    for kw in keywords:
        pos = text.find(kw)
        if pos >= 0 and (best_pos < 0 or pos < best_pos):
            best_pos = pos
            best_kw = kw

    if best_pos < 0:
        # 没找到关键词，返回开头
        return text[:snippet_len]

    # 从关键词位置前后扩展
    start = max(0, best_pos - snippet_len // 4)
    end = min(len(text), best_pos + len(best_kw) + snippet_len * 3 // 4)

    snippet = text[start:end]

    # 添加省略号
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."

    return snippet


def delete_document(file_path: str, category: str = "") -> int:
    """删除文档的所有切片（同步 BM25 索引）。"""
    count = 0
    if category:
        coll = get_collection(category)
        if coll:
            existing = coll.get(where={"file_path": file_path})
            if existing["ids"]:
                coll.delete(ids=existing["ids"])
                count = len(existing["ids"])
    else:
        for k in COLLECTIONS:
            coll = get_collection(k)
            if coll:
                existing = coll.get(where={"file_path": file_path})
                if existing["ids"]:
                    coll.delete(ids=existing["ids"])
                    count += len(existing["ids"])

    # 同步移除 BM25 索引
    if count > 0:
        try:
            from memory_store.bm25_index import remove_document_from_index
            remove_document_from_index(file_path)
        except Exception as e:
            logger.warning("BM25 索引移除失败: %s", e)

    return count


def list_documents(category: str = "") -> list[dict[str, Any]]:
    """列出已索引文档（去重，每个文件只显示一条）。"""
    docs = []
    categories = [category] if category else list(COLLECTIONS.keys())
    for cat in categories:
        coll = get_collection(cat)
        if coll is None:
            continue
        try:
            all_data = coll.get()
            seen = set()
            for meta in all_data.get("metadatas", []):
                fp = meta.get("file_path", "")
                if fp and fp not in seen:
                    seen.add(fp)
                    docs.append({
                        "file_name": meta.get("file_name", fp),
                        "file_path": fp,
                        "category": cat,
                        "total_chunks": meta.get("total_chunks", 0),
                    })
        except Exception:
            pass
    return docs


def get_stats() -> dict[str, int]:
    """获取各分区文档数。"""
    stats = {}
    for k, name in COLLECTIONS.items():
        coll = get_collection(k)
        if coll:
            stats[k] = coll.count()
        else:
            stats[k] = 0
    return stats
