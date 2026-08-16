"""文本降噪：清洗文档提取后的噪声，提升检索质量。

处理步骤：
1. 去除控制字符（除换行/制表符）
2. 合并连续空白（空格/制表符/换行）
3. 去除无意义重复行（如 "第X页" / "Page X"）
4. 修复断行连句（行尾无标点则与下行合并）
5. 去除过短行（<4 字符且无中文）
"""
import logging
import re

logger = logging.getLogger(__name__)

# ── 噪声模式 ──
_NOISE_PATTERNS = [
    # 页码行：纯 "第X页" 或 "Page X of Y"
    re.compile(r'^\s*(第\s*\d+\s*页|Page\s+\d+\s*(of\s+\d+)?)\s*$', re.IGNORECASE),
    # 纯数字行（页码/行号）
    re.compile(r'^\s*\d+\s*$'),
    # 纯分隔符行
    re.compile(r'^\s*[-_=*~]{3,}\s*$'),
    # URL/邮箱（可选降噪，默认保留，BM25 对 URL 友好）
]

# 控制字符（保留 \t \n \r）
_CONTROL_CHARS = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')

# 连续空白
_MULTI_SPACES = re.compile(r'[ \t]{2,}')
_MULTI_NEWLINES = re.compile(r'\n{3,}')

# 行尾无标点且下行以小写/中文开头 → 连句
_SENTENCE_BREAK = re.compile(r'([^\n。！？；.!?;])\n+([a-z一-鿿])')


def clean_text(text: str) -> str:
    """清洗文档文本，去除噪声。

    Args:
        text: 原始提取文本

    Returns:
        清洗后的文本
    """
    if not text or not text.strip():
        return ""

    # 1. 去除控制字符
    text = _CONTROL_CHARS.sub('', text)

    # 2. 合并连续空白
    text = _MULTI_SPACES.sub(' ', text)
    text = _MULTI_NEWLINES.sub('\n\n', text)

    # 3. 逐行过滤噪声行
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # 跳过噪声行
        if any(p.match(stripped) for p in _NOISE_PATTERNS):
            continue
        # 跳过过短且无中文的行
        if len(stripped) < 4 and not re.search(r'[一-鿿]', stripped):
            continue
        cleaned_lines.append(stripped)

    text = '\n'.join(cleaned_lines)

    # 4. 修复断行连句（行尾无标点 + 下行小写/中文开头）
    #    限制替换次数避免误伤正常换行
    text, _ = _SENTENCE_BREAK.subn(r'\1\2', text)

    # 5. 最终清理首尾空白
    text = text.strip()

    logger.debug("文本降噪: %d → %d 字符", len(text), len(text))
    return text


def clean_chunks(chunks: list[str]) -> list[str]:
    """批量清洗切片，过滤空切片。"""
    cleaned = []
    for chunk in chunks:
        c = clean_text(chunk)
        if c and len(c) >= 20:  # 过滤过短切片（<20字符无检索价值）
            cleaned.append(c)
    return cleaned
