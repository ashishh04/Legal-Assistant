"""Choose the text-recognition engine from the settings."""
from __future__ import annotations

from ..config import Settings
from .reader import OcrEngine, OcrReader
from .results import OcrCache


def make_engine(settings: Settings, kind: str | None = None, **local_options) -> OcrEngine:
    """``kind``: "server" (FERRERO_OCR_URL) or "local" (this process); default from FERRERO_OCR_ENGINE."""
    kind = kind or settings.ocr_engine
    if kind == "auto":
        kind = "server" if settings.ocr_url else "local"
    if kind == "server":
        if not settings.ocr_url:
            raise SystemExit("The OCR server engine needs FERRERO_OCR_URL (an OpenAI-compatible endpoint serving "
                             "baidu/Unlimited-OCR-2, e.g. http://gpu-host:10000/v1)")
        from .server import UnlimitedOcrServer

        return UnlimitedOcrServer(settings.ocr_url)
    if kind == "local":
        try:
            from .local import UnlimitedOcrLocal
        except ImportError as e:
            raise SystemExit(f"The local OCR engine needs the OCR environment ({e.name} is missing): "
                             'pip install -e ".[ocr]"  (see README, "Text recognition")') from None
        options = {"mode": settings.ocr_mode, "experts": settings.ocr_experts, **local_options}
        return UnlimitedOcrLocal(settings.ocr_model_dir, **options)
    raise SystemExit(f"Unknown OCR engine {kind!r}")


def sync_reader(settings: Settings) -> OcrReader | None:
    """What the document sync uses for scans: the OCR cache, plus the OCR server when one is configured.

    The in-process model is slow on a CPU (minutes per page), so the sync only uses it when FERRERO_OCR_ENGINE=local
    is set explicitly; otherwise run ``python -m ferrero.ocr`` once and the sync reads its results from the cache.
    """
    if settings.ocr_engine == "off":
        return None
    engine = None
    if settings.ocr_engine == "server" or (settings.ocr_engine == "auto" and settings.ocr_url):
        engine = make_engine(settings, "server")
    elif settings.ocr_engine == "local":
        engine = make_engine(settings, "local")
    return OcrReader(OcrCache(settings.ocr_dir), engine, min_confidence=settings.ocr_min_confidence,
                     review_confidence=settings.ocr_review_confidence)
