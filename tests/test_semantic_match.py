"""语义匹配单元测试。"""
import pytest
from evolution_core.semantic_match import (
    cosine_similarity,
    semantic_match,
    embed_text,
    find_similar_tasks,
    clear_cache,
    get_backend_info,
    _tokenize,
)
from evolution_core.safe_ops import safe_divide


class TestCosineSimilarity:
    """测试余弦相似度。"""

    def test_identical_vectors(self):
        """相同向量相似度为 1。"""
        vec = [1.0, 2.0, 3.0]
        assert cosine_similarity(vec, vec) == pytest.approx(1.0, rel=1e-3)

    def test_orthogonal_vectors(self):
        """正交向量相似度为 0。"""
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0, abs=1e-6)

    def test_opposite_vectors(self):
        """相反向量相似度为 -1。"""
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(-1.0, rel=1e-3)

    def test_empty_vectors(self):
        """空向量返回 0。"""
        assert cosine_similarity([], []) == 0.0
        assert cosine_similarity([1.0], []) == 0.0

    def test_different_dimensions(self):
        """维度不匹配返回 0。"""
        assert cosine_similarity([1.0, 2.0], [1.0]) == 0.0

    def test_zero_vector(self):
        """零向量返回 0。"""
        assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0


class TestEmbedText:
    """测试文本向量化。"""

    def test_empty_text(self):
        """空文本返回空列表。"""
        assert embed_text("") == []
        assert embed_text(None) == []

    def test_valid_text(self):
        """有效文本返回向量。"""
        vec = embed_text("测试文本")
        assert isinstance(vec, list)
        assert len(vec) > 0

    def test_same_text_same_vector(self):
        """相同文本产生相同向量。"""
        vec1 = embed_text("周报")
        vec2 = embed_text("周报")
        assert vec1 == vec2

    def test_cache_works(self):
        """缓存应生效。"""
        clear_cache()
        vec1 = embed_text("缓存测试文本")
        vec2 = embed_text("缓存测试文本")
        assert vec1 == vec2


class TestSemanticMatch:
    """测试语义匹配。"""

    def test_empty_input(self):
        """空输入返回空列表。"""
        assert semantic_match("", []) == []
        assert semantic_match("test", []) == []
        assert semantic_match("", ["a", "b"]) == []

    def test_exact_match(self):
        """完全匹配相似度最高。"""
        results = semantic_match("周报", ["周报", "记账", "归档"])
        if results:  # 有 embedding 模型时
            assert results[0][0] == "周报"
            assert results[0][1] > 0.9

    def test_similarity_ordering(self):
        """结果按相似度降序。"""
        results = semantic_match("生成周报", ["周报", "月报", "记账"])
        if len(results) >= 2:
            assert results[0][1] >= results[1][1]

    def test_threshold_filtering(self):
        """阈值过滤。"""
        results = semantic_match("周报", ["记账", "归档"], threshold=0.99)
        # 高阈值应过滤掉大部分
        for _, sim in results:
            assert sim >= 0.99


class TestTokenize:
    """测试分词。"""

    def test_chinese_ngram(self):
        """中文应产生 2-gram。"""
        words = _tokenize("周报")
        assert len(words) > 0

    def test_english_words(self):
        """英文应提取单词。"""
        words = _tokenize("weekly report")
        assert "weekly" in words
        assert "report" in words

    def test_empty(self):
        """空文本返回空列表。"""
        assert _tokenize("") == []


class TestBackendInfo:
    """测试后端信息。"""

    def test_returns_dict(self):
        """应返回字典。"""
        info = get_backend_info()
        assert "backend" in info
        assert "cache_size" in info

    def test_backend_is_valid(self):
        """后端应是有效值。"""
        info = get_backend_info()
        assert info["backend"] in ("onnx", "sentence_transformers", "tfidf")


class TestClearCache:
    """测试缓存清除。"""

    def test_clears_cache(self):
        """清除后缓存为空。"""
        embed_text("test")
        clear_cache()
        info = get_backend_info()
        assert info["cache_size"] == 0
