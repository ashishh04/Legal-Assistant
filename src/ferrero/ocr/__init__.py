"""Text recognition for image-only scans, with Baidu's Unlimited-OCR-2 (https://github.com/baidu/Unlimited-OCR).

Scanned PDFs carry no text layer. Each page image goes to Unlimited-OCR-2, a 3.3B-parameter vision-language
model that reads a page into text with its layout (titles, paragraphs, tables). Results are cached per file
content under ``data/ocr``; the document sync turns them into citable sections like any other document.

Engines:
- ``local``: the model in this process (Transformers; NVIDIA GPU if present, otherwise CPU). See ``ocr.local``.
- ``server``: an OpenAI-compatible endpoint serving the model (Baidu's SGLang build on a GPU). See ``ocr.server``.
"""
from .results import OcrCache, OcrPage, OcrResult

__all__ = ["OcrCache", "OcrPage", "OcrResult"]
