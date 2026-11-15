import logging

logger = logging.getLogger(__name__)

_engine = None
_import_failed = False

try:
    from rapidocr_onnxruntime import RapidOCR  # type: ignore

    _OCR_IMPORT_OK = True
except ImportError:  # pragma: no cover
    RapidOCR = None  # type: ignore
    _OCR_IMPORT_OK = False

MAX_CHARS = 8000


def ocr_available() -> bool:
    return _OCR_IMPORT_OK and not _import_failed


def run_ocr(png_bytes: bytes) -> str | None:
    """OCR grounding text for extraction prompts. None when unavailable."""
    global _engine, _import_failed
    if not ocr_available():
        return None
    try:
        import cv2
        import numpy as np

        if _engine is None:
            _engine = RapidOCR()
        arr = cv2.imdecode(np.frombuffer(png_bytes, np.uint8), cv2.IMREAD_COLOR)
        if arr is None:
            return None
        result, _ = _engine(arr)
        if not result:
            return ""
        lines = [str(item[1]).strip() for item in result if len(item) > 1 and str(item[1]).strip()]
        text = "\n".join(lines)
        return text[:MAX_CHARS]
    except Exception as exc:  # pragma: no cover
        logger.warning("OCR failed, continuing without grounding: %s", exc)
        return None
