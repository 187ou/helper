"""情景记忆语义索引：历史任务的向量化存储与检索。

解决缺口：当前情景记忆用 LIKE %kw% 字符串匹配，无法捕捉语义相似。
（"写周报" vs "写周总结" 语义相同但匹配不上）

核心能力：
1. 历史任务向量化存储（复用 Chroma 嵌入函数）
2. 语义相似度检索 + 评分时间加权
3. 增量更新（新任务完成后自动入库）
4. 与字符串检索互补（语义检索为主，字符串检索为辅）
"""
import json
import logging
import threading
from datetime import datetime
from typing import Any

from config.path_config import EPISODIC_DIR

logger = logging.getLogger(__name__)

# 情景记忆集合名
_COLLECTION_NAME = "episodic_memory"

_client = None
_collection = None
_init_lock = threading.Lock()  # 线程安全锁


def _get_collection():
    """获取/初始化情景记忆集合（线程安全）。"""
    global _client, _collection

    # 快速路径：已初始化直接返回
    if _collection is not None:
        return _collection

    # 慢速路径：加锁初始化
    with _init_lock:
        # 双重检查（防止多个线程同时通过第一次检查）
        if _collection is not None:
            return _collection

        try:
            import chromadb
            from memory_store.chroma_kb import get_embedding_fn

            ensure_dirs()
            _client = chromadb.PersistentClient(path=str(EPISODIC_DIR))
            _collection = _client.get_or_create_collection(
                name=_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("情景记忆集合初始化: %s", EPISODIC_DIR)
        except Exception as e:
            logger.warning("情景记忆初始化失败: %s", e)
            return None

        return _collection


def ensure_dirs():
    """确保目录存在。"""
    EPISODIC_DIR.mkdir(parents=True, exist_ok=True)


def add_task_to_index(task_id: int, task_text: str, task_type: str = "",
                      score: float = 0, tags: str = "") -> bool:
    """将任务添加到情景记忆索引（任务完成后调用）。

    Args:
        task_id: 任务 ID
        task_text: 任务文本
        task_type: 任务类型
        score: 任务评分
        tags: 标签

    Returns:
        是否成功
    """
    try:
        from memory_store.chroma_kb import embed_texts

        coll = _get_collection()
        if coll is None:
            return False

        # 向量化
        vectors = embed_texts([task_text])
        if not vectors:
            return False

        # 生成唯一 ID
        doc_id = f"task_{task_id}"

        # 去重：先删后插
        try:
            existing = coll.get(ids=[doc_id])
            if existing.get("ids"):
                coll.delete(ids=[doc_id])
        except Exception:
            pass

        # 入库
        coll.add(
            ids=[doc_id],
            documents=[task_text],
            embeddings=vectors,
            metadatas=[{
                "task_id": task_id,
                "task_type": task_type,
                "score": score,
                "tags": tags,
                "create_time": datetime.now().isoformat(),
            }],
        )

        logger.debug("情景记忆入库: task #%d", task_id)
        return True
    except Exception as e:
        logger.debug("情景记忆入库失败: %s", e)
        return False


def search_similar_tasks(query: str, top_k: int = 3,
                         min_score: float = 0.3) -> list[dict[str, Any]]:
    """语义检索相似历史任务（评分+时间加权）。

    Args:
        query: 查询文本
        top_k: 返回数量
        min_score: 最低相似度阈值

    Returns:
        相似任务列表，按综合得分排序
    """
    try:
        from memory_store.chroma_kb import embed_texts

        coll = _get_collection()
        if coll is None:
            return []

        # 向量化查询
        query_vec = embed_texts([query])
        if not query_vec:
            return []

        # 检索（多取一些用于加权排序）
        results = coll.query(query_embeddings=query_vec, n_results=top_k * 3)
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]

        if not docs:
            return []

        # 评分+时间加权排序
        now = datetime.now()
        scored_results = []

        for doc, meta, dist in zip(docs, metas, dists):
            similarity = 1 - dist  # cosine distance → similarity
            if similarity < min_score:
                continue

            # 评分维度
            task_score = meta.get("score", 0) or 0
            score_weight = task_score / 100.0

            # 时间衰减
            try:
                task_time = datetime.strptime(meta.get("create_time", ""), "%Y-%m-%d %H:%M:%S")
                days_ago = (now - task_time).days
                time_weight = max(0, 1 - days_ago / 90)
            except (ValueError, TypeError):
                time_weight = 0.5

            # 综合得分：语义 0.4 + 评分 0.35 + 时间 0.25
            final_score = similarity * 0.4 + score_weight * 0.35 + time_weight * 0.25

            scored_results.append({
                "text": doc,
                "task_id": meta.get("task_id", 0),
                "task_type": meta.get("task_type", ""),
                "score": task_score,
                "similarity": round(similarity, 3),
                "final_score": round(final_score, 3),
                "create_time": meta.get("create_time", ""),
            })

        # 按综合得分排序
        scored_results.sort(key=lambda x: x["final_score"], reverse=True)
        return scored_results[:top_k]

    except Exception as e:
        logger.debug("情景记忆语义检索失败: %s", e)
        return []
