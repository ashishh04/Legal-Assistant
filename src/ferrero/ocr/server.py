"""Unlimited-OCR-2 behind an OpenAI-compatible endpoint.

For production, Baidu recommends serving the model with their SGLang build on a GPU (seconds per page); llama.cpp's
``llama-server`` with the GGUF build also speaks this protocol. One page per request, temperature 0, and token
log-probabilities give the same confidence measure as the in-process engine.
"""
from __future__ import annotations

import base64
import math
import re
import time

import httpx

from .results import OcrPage, text_confidence

MODEL_ID = "baidu/Unlimited-OCR-2"
PROMPT = "Multi page parsing."
_LAYOUT = re.compile(r"<BLOCK>.*?<FORK>|<\|(det|ref)\|>.*?<\|/\1\|>", re.S)  # block type and box: not text


class OcrServerError(RuntimeError):
    pass


def _mime(image: bytes) -> str:
    if image[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if image[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    return "application/octet-stream"


def confidence_from_logprobs(tokens: list[dict]) -> float | None:
    """Confidence of the recognised text (results.text_confidence), leaving out layout markup (block labels and boxes)."""
    return text_confidence(text_token_probs(tokens))


def text_token_probs(tokens: list[dict]) -> list[float]:
    """Probabilities of the recognised-text tokens in an OpenAI-style logprobs list."""
    text, spans = "", []
    for t in tokens:
        spans.append((len(text), len(text) + len(t.get("token", ""))))
        text += t.get("token", "")
    layout = [(m.start(), m.end()) for m in _LAYOUT.finditer(text)]
    probs = []
    for (start, end), t in zip(spans, tokens):
        if any(a <= start and end <= b for a, b in layout) or t.get("logprob") is None:
            continue
        if t.get("token", "").startswith(("<|", "<｜")) or t.get("token") in ("<PAGE>", "<CHILD>"):
            continue
        probs.append(math.exp(t["logprob"]))
    return probs


class UnlimitedOcrServer:
    engine = "Unlimited-OCR-2"
    mode = "server"

    def __init__(self, base_url: str, *, model: str = MODEL_ID, api_key: str | None = None, timeout: float = 900,
                 max_tokens: int = 8000, transport: httpx.BaseTransport | None = None):
        url = base_url.rstrip("/")
        self.base_url = url if url.endswith("/v1") else f"{url}/v1"
        self.model = model
        self.max_tokens = max_tokens
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.Client(base_url=self.base_url, headers=headers, timeout=timeout, transport=transport)

    def check(self) -> None:
        try:
            self._client.get("/models").raise_for_status()
        except httpx.HTTPError as e:
            raise OcrServerError(f"The OCR server at {self.base_url} is not reachable ({type(e).__name__})") from None

    def recognize_page(self, image: bytes, number: int = 1) -> OcrPage:
        data_url = f"data:{_mime(image)};base64,{base64.b64encode(image).decode()}"
        body = {
            "model": self.model, "temperature": 0, "max_tokens": self.max_tokens, "logprobs": True, "stream": False,
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": data_url}},
                {"type": "text", "text": PROMPT},
            ]}],
        }
        started = time.perf_counter()
        try:
            response = self._client.post("/chat/completions", json=body)
            response.raise_for_status()
            choice = response.json()["choices"][0]
        except httpx.HTTPStatusError as e:
            raise OcrServerError(f"The OCR server answered {e.response.status_code} for page {number}") from None
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
            raise OcrServerError(f"The OCR server failed on page {number} ({type(e).__name__})") from None
        text = (choice.get("message") or {}).get("content") or ""
        tokens = (choice.get("logprobs") or {}).get("content") or []
        probs = text_token_probs(tokens)
        return OcrPage(number=number, text=text, confidence=text_confidence(probs), tokens=len(tokens),
                       finish="stop" if choice.get("finish_reason") == "stop" else "length",
                       seconds=round(time.perf_counter() - started, 1), text_token_probs=[round(p, 3) for p in probs])
