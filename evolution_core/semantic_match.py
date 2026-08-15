"""语义匹配：用 embedding 替代关键词字面匹配。

核心能力：
1. 文本向量化（支持多种后端：sentence-transformers / Chroma 内置 / 简单 TF-IDF）
2. 语义相似度计算（余弦相似度）
3. 语义级模式匹配（替代关键词匹配）
4. 缓存机制（避免重复计算）

边缘处理：
- embedding 模型不可用 → 降级到关键词匹配
- 空文本 → 返回空结果
- 模型加载失败 → 自动降级
"""
import logging
import math
import re
from typing import Any

from evolution_core.safe_ops import safe_divide

logger = logging.getLogger(__name__)

# ── 全局状态 ──

_embedding_model = None
_embedding_backend = None
_vector_cache: dict[str, list[float]] = {}


def _get_embedding_model():
    """获取/初始化 embedding 模型（延迟加载）。

    优先级：
    1. Chroma 内置 ONNX（无需下载）
    2. sentence-transformers
    3. 降级：TF-IDF
    """
    global _embedding_model, _embedding_backend

    if _embedding_model is not None:
        return _embedding_model, _embedding_backend

    # 尝试 Chroma 内置
    try:
        from chromadb.utils.embedding_functions import ONNXMiniLM6v2
        _embedding_model = ONNXMiniLM6v2()
        _embedding_backend = "onnx"
        logger.info("Embedding 模型初始化: ONNX")
        return _embedding_model, _embedding_backend
    except Exception as e:
        logger.debug("ONNX 不可用: %s", e)

    # 尝试 sentence-transformers
    try:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        _embedding_backend = "sentence_transformers"
        logger.info("Embedding 模型初始化: sentence-transformers")
        return _embedding_model, _embedding_backend
    except Exception as e:
        logger.debug("sentence-transformers 不可用: %s", e)

    # 降级：TF-IDF
    _embedding_model = None
    _embedding_backend = "tfidf"
    logger.info("Embedding 降级到 TF-IDF")
    return _embedding_model, _embedding_backend


def embed_text(text: str) -> list[float]:
    """将文本编码为向量。

    边缘处理：
    - 空文本 → 返回零向量
    - 模型不可用 → 使用 TF-IDF
    - 缓存命中 → 直接返回
    """
    if not text or not text.strip():
        return []

    text = text.strip()

    # 缓存命中
    if text in _vector_cache:
        return _vector_cache[text]

    model, backend = _get_embedding_model()

    try:
        if backend == "onnx":
            result = model([text])
            if hasattr(result, "tolist"):
                vector = result.tolist()[0]
            elif isinstance(result, list):
                vector = result[0]
            else:
                vector = list(result[0])
        elif backend == "sentence_transformers":
            vector = model.encode([text], show_progress_bar=False).tolist()[0]
        else:
            # TF-IDF 降级
            vector = _tfidf_encode(text)
    except Exception as e:
        logger.warning("Embedding 失败，降级 TF-IDF: %s", e)
        vector = _tfidf_encode(text)

    # 缓存（限制大小）
    if len(_vector_cache) < 1000:
        _vector_cache[text] = vector

    return vector


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """计算余弦相似度。

    边缘处理：
    - 空向量 → 返回 0
    - 维度不匹配 → 返回 0
    - 零向量 → 返回 0
    """
    if not vec_a or not vec_b:
        return 0.0
    if len(vec_a) != len(vec_b):
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)


def semantic_match(task_text: str, candidates: list[str], threshold: float = 0.5) -> list[tuple[str, float]]:
    """语义匹配：找出与任务文本最相似的候选。

    Args:
        task_text: 任务文本
        candidates: 候选文本列表
        threshold: 相似度阈值

    Returns:
        [(candidate, similarity), ...] 按相似度降序
    """
    if not task_text or not candidates:
        return []

    task_vec = embed_text(task_text)
    if not task_vec:
        return []

    results = []
    for candidate in candidates:
        cand_vec = embed_text(candidate)
        if not cand_vec:
            continue
        sim = cosine_similarity(task_vec, cand_vec)
        if sim >= threshold:
            results.append((candidate, round(sim, 3)))

    results.sort(key=lambda x: x[1], reverse=True)
    return results


def semantic_match_patterns(task_text: str, patterns: list[dict], threshold: float = 0.5) -> list[dict]:
    """语义级模式匹配。

    对模式的关键词和步骤名进行语义匹配，替代字面匹配。

    Args:
        task_text: 任务文本
        patterns: 模式列表
        threshold: 相似度阈值

    Returns:
        匹配的模式列表（按相似度排序）
    """
    if not task_text or not patterns:
        return []

    task_vec = embed_text(task_text)
    if not task_vec:
        return []

    matched = []
    for pattern in patterns:
        # 匹配关键词
        keywords = pattern.get("task_keywords", [])
        if isinstance(keywords, str):
            import json
            try:
                keywords = json.loads(keywords)
            except Exception:
                keywords = []

        max_sim = 0.0
        for kw in keywords:
            kw_vec = embed_text(kw)
            if kw_vec:
                sim = cosine_similarity(task_vec, kw_vec)
                max_sim = max(max_sim, sim)

        # 也匹配步骤名
        step_template = pattern.get("step_template", [])
        if isinstance(step_template, str):
            import json
            try:
                step_template = json.loads(step_template)
            except Exception:
                step_template = []

        for step_name in step_template:
            step_vec = embed_text(step_name)
            if step_vec:
                sim = cosine_similarity(task_vec, step_vec)
                max_sim = max(max_sim, sim)

        if max_sim >= threshold:
            matched.append({**pattern, "semantic_score": round(max_sim, 3)})

    matched.sort(key=lambda x: x.get("semantic_score", 0), reverse=True)
    return matched


def find_similar_tasks(task_text: str, top_k: int = 5) -> list[dict]:
    """查找历史中最相似的任务。

    用于：为新任务推荐历史最优步骤模板。
    """
    if not task_text:
        return []

    from memory_store.sqlite_db import get_conn
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT id, task_content, task_type, work_score, task_steps FROM task_list WHERE status = 'success' ORDER BY create_time DESC LIMIT 100"
        ).fetchall()
    except Exception:
        return []
    finally:
        conn.close()

    if not rows:
        return []

    task_vec = embed_text(task_text)
    if not task_vec:
        return []

    similarities = []
    for row in rows:
        content = row["task_content"]
        content_vec = embed_text(content)
        if not content_vec:
            continue
        sim = cosine_similarity(task_vec, content_vec)
        similarities.append({
            "id": row["id"],
            "content": content,
            "type": row["task_type"],
            "score": row["work_score"],
            "steps": row["task_steps"],
            "similarity": round(sim, 3),
        })

    similarities.sort(key=lambda x: x["similarity"], reverse=True)
    return similarities[:top_k]


def clear_cache() -> None:
    """清除向量缓存。"""
    global _vector_cache
    _vector_cache.clear()
    logger.info("Embedding 缓存已清除")


def get_backend_info() -> dict[str, Any]:
    """获取当前后端信息。"""
    _, backend = _get_embedding_model()
    return {
        "backend": backend,
        "cache_size": len(_vector_cache),
    }


# ── TF-IDF 降级实现 ──

_tfidf_vocab: dict[str, int] = {}
_trained = False


def _tokenize(text: str) -> list[str]:
    """简单分词：中文 2-gram + 英文单词。"""
    words = []
    # 英文单词
    words.extend(re.findall(r'[a-z]+', text.lower()))
    # 中文 2-gram
    for i in range(len(text) - 1):
        if '一' <= text[i] <= '鿿' and '一' <= text[i+1] <= '鿿':
            words.append(text[i:i+2])
    return words


def _tfidf_encode(text: str) -> list[float]:
    """TF-IDF 编码（轻量级降级方案）。

    基于词频的简单向量表示。
    """
    global _trained

    words = _tokenize(text)
    if not words:
        return []

    # 构建词表（延迟）
    vocab = {}
    idx = 0
    for w in set(words):
        if w not in vocab:
            vocab[w] = idx
            idx += 1

    # TF 向量
    vector = [0.0] * len(vocab)
    word_count = {}
    for w in words:
        word_count[w] = word_count.get(w, 0) + 1

    for w, count in word_count.items():
        if w in vocab:
            vector[vocab[w]] = count / len(words)

    return vector
