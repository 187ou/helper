"""OCR 图片文字识别工具（基于 PaddleOCR / easyocr，可选依赖）。"""
import logging
from typing import Any

logger = logging.getLogger(__name__)


def extract_text(path: str) -> str:
    """从图片中提取文字（自动选择可用 OCR 引擎）。

    优先级：PaddleOCR > easyocr > tesseract
    """
    # 尝试 PaddleOCR
    text = _try_paddleocr(path)
    if text:
        return text

    # 尝试 easyocr
    text = _try_easyocr(path)
    if text:
        return text

    # 尝试 tesseract
    text = _try_tesseract(path)
    if text:
        return text

    logger.warning("无可用 OCR 引擎，请安装 paddleocr / easyocr / pytesseract")
    return ""


def _try_paddleocr(path: str) -> str:
    """尝试 PaddleOCR。"""
    try:
        from paddleocr import PaddleOCR
        ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
        result = ocr.ocr(path, cls=True)
        texts = []
        for line in result:
            if line:
                for word_info in line:
                    if word_info and len(word_info) >= 2:
                        texts.append(word_info[1][0])
        text = "\n".join(texts)
        if text.strip():
            logger.info("PaddleOCR 识别: %s (%d 字符)", path, len(text))
            return text
    except ImportError:
        pass
    except Exception as e:
        logger.debug("PaddleOCR 失败: %s", e)
    return ""


def _try_easyocr(path: str) -> str:
    """尝试 easyocr。"""
    try:
        import easyocr
        reader = easyocr.Reader(['ch_sim', 'en'])
        results = reader.readtext(path)
        texts = [r[1] for r in results if r]
        text = "\n".join(texts)
        if text.strip():
            logger.info("easyocr 识别: %s (%d 字符)", path, len(text))
            return text
    except ImportError:
        pass
    except Exception as e:
        logger.debug("easyocr 失败: %s", e)
    return ""


def _try_tesseract(path: str) -> str:
    """尝试 tesseract。"""
    try:
        import pytesseract
        from PIL import Image
        img = Image.open(path)
        text = pytesseract.image_to_string(img, lang="chi_sim+eng")
        if text.strip():
            logger.info("tesseract 识别: %s (%d 字符)", path, len(text))
            return text
    except ImportError:
        pass
    except Exception as e:
        logger.debug("tesseract 失败: %s", e)
    return ""


def is_ocr_available() -> bool:
    """检查是否有可用 OCR 引擎。"""
    try:
        import paddleocr  # noqa: F401
        return True
    except ImportError:
        pass
    try:
        import easyocr  # noqa: F401
        return True
    except ImportError:
        pass
    try:
        import pytesseract  # noqa: F401
        return True
    except ImportError:
        pass
    return False
