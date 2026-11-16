"""Recognised text for the document sync: from the cache, or from an engine when one is configured."""
from __future__ import annotations

import io
import logging
from typing import Callable, Protocol

from pypdf import PdfReader

from .results import OcrCache, OcrPage, OcrResult
from .scans import page_images

log = logging.getLogger(__name__)

# A document whose mean page confidence is below MIN is not indexed ("OCR confidence below threshold"); pages below
# REVIEW are indexed but flagged for review. Confidence is the mean probability the model gave the text it wrote.
DEFAULT_MIN_CONFIDENCE = 0.80
DEFAULT_REVIEW_CONFIDENCE = 0.90


class OcrEngine(Protocol):
    engine: str
    model: str
    mode: str

    def recognize_page(self, image: bytes, number: int = 1) -> OcrPage: ...


class Stopped(Exception):
    """A stop was requested between pages; the finished pages are saved."""


def recognize_pdf(engine: OcrEngine, data: bytes, sha: str, file_name: str, cache: OcrCache,
                  progress: Callable[[int, int, OcrPage], None] | None = None,
                  should_stop: Callable[[], bool] | None = None) -> OcrResult:
    """Recognise every page of a scanned PDF, saving after each page so an interrupted run resumes where it stopped."""
    images = page_images(PdfReader(io.BytesIO(data)))
    cache.save_page_images(sha, images)
    pages = {p.number: p for p in cache.partial(sha, engine.model, engine.mode) if p.number <= len(images)}
    for number, image in enumerate(images, start=1):
        if number in pages:
            continue
        if should_stop is not None and should_stop():
            raise Stopped(file_name)
        pages[number] = engine.recognize_page(image, number)
        cache.put_partial(sha, engine.model, engine.mode, [pages[n] for n in sorted(pages)])
        if progress is not None:
            progress(number, len(images), pages[number])
    result = OcrResult(sha256=sha, engine=engine.engine, model=engine.model, mode=engine.mode, file_name=file_name,
                       pages=[pages[n] for n in sorted(pages)])
    cache.put(result)
    return result


class OcrReader:
    def __init__(self, cache: OcrCache, engine: OcrEngine | None = None, *,
                 min_confidence: float = DEFAULT_MIN_CONFIDENCE, review_confidence: float = DEFAULT_REVIEW_CONFIDENCE):
        if not 0 <= min_confidence <= review_confidence <= 1:
            raise ValueError("OCR thresholds must satisfy 0 <= minimum <= review <= 1")
        self.cache = cache
        self.engine = engine
        self.min_confidence = min_confidence
        self.review_confidence = review_confidence

    def read(self, data: bytes, sha: str, file_name: str) -> OcrResult | None:
        """The recognised text of a scan, or None when it has not been recognised and no engine is configured."""
        cached = self.cache.get(sha)
        if cached is not None or self.engine is None:
            return cached
        log.info("Recognising %s with %s", file_name, self.engine.model)
        return recognize_pdf(self.engine, data, sha, file_name, self.cache)
