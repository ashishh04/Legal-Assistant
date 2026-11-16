"""What text recognition produced for one scanned file, and the on-disk cache of it.

Recognition is the slow step (minutes per page on a CPU), so every result is kept in ``data/ocr`` as one JSON
file per file *content* (sha256): a scan is recognised once, however often it is renamed, copied or re-synced,
and the document index can be rebuilt from the cache in seconds.
"""
from __future__ import annotations

import json
import logging
import math
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

log = logging.getLogger(__name__)


def text_confidence(probs: list[float]) -> float | None:
    """Confidence of recognised text: the geometric mean of its tokens' probabilities.

    A plain average hides a few badly misread characters among hundreds of sure ones; the geometric mean does not.
    On a heavily degraded test scan the model wrote "POA-2625" for "POA-2025": average 0.93, geometric mean 0.89.
    """
    if not probs:
        return None
    return round(math.exp(sum(math.log(max(p, 1e-4)) for p in probs) / len(probs)), 4)


@dataclass
class OcrPage:
    number: int                     # 1-based page number in the PDF
    text: str                       # the model's output for the page, layout markup included (see ocr.output)
    confidence: float | None        # confidence the engine reported, 0-1 (None: it gives none); see ``score``
    tokens: int = 0                 # tokens generated for the page
    finish: str = "stop"            # "stop", or "length" when the page ran into the token limit
    seconds: float = 0.0
    prefill_seconds: float = 0.0    # of which reading the page image and the prompt
    text_token_probs: list[float] = field(default_factory=list)  # per text token, to recalibrate without re-running

    @property
    def score(self) -> float | None:
        """The page's confidence, recomputed from its token probabilities when they were kept."""
        return text_confidence(self.text_token_probs) if self.text_token_probs else self.confidence


@dataclass
class OcrResult:
    sha256: str
    engine: str                     # e.g. "Unlimited-OCR-2"
    model: str                      # model id and revision, e.g. "baidu/Unlimited-OCR-2@0480966"
    pages: list[OcrPage]
    mode: str = ""                  # how pages were fed to the model (e.g. "gundam": page plus detail tiles)
    file_name: str = ""             # name of the file when it was recognised (for people reading the cache)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))

    @property
    def confidence(self) -> float | None:
        """Document confidence: the mean of the page confidences, so one poor page lowers it but does not sink it."""
        scores = [p.score for p in self.pages if p.score is not None]
        return round(sum(scores) / len(scores), 4) if scores else None

    @property
    def seconds(self) -> float:
        return round(sum(p.seconds for p in self.pages), 1)

    def to_json(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict) -> OcrResult:
        pages = [OcrPage(**p) for p in data.get("pages", [])]
        return cls(**{**data, "pages": pages})


def _write_json(path: Path, data: dict) -> None:
    """Write atomically, so an interrupted run never leaves half a file behind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


class OcrCache:
    """``<folder>/<sha256>.json`` per recognised file; ``<sha256>.partial.json`` holds the pages of an unfinished one;
    ``pages/<sha256>/<n>.jpg`` keeps the page images, so people can check the recognised text against the scan."""

    def __init__(self, folder: Path):
        self.folder = Path(folder)

    @staticmethod
    def _check(sha: str) -> str:
        if len(sha) != 64 or not all(c in "0123456789abcdef" for c in sha):
            raise ValueError(f"not a sha256: {sha!r}")
        return sha

    def _path(self, sha: str, partial: bool = False) -> Path:
        return self.folder / f"{self._check(sha)}{'.partial' if partial else ''}.json"

    # ---------- page images ----------
    def save_page_images(self, sha: str, images: list[bytes]) -> None:
        folder = self.folder / "pages" / self._check(sha)
        folder.mkdir(parents=True, exist_ok=True)
        for number, image in enumerate(images, start=1):
            suffix = ".jpg" if image[:3] == b"\xff\xd8\xff" else ".png"
            target = folder / f"{number}{suffix}"
            if not target.is_file() or target.stat().st_size != len(image):
                tmp = target.with_suffix(target.suffix + ".tmp")
                tmp.write_bytes(image)
                os.replace(tmp, target)

    def page_image(self, sha: str, number: int) -> tuple[bytes, str] | None:
        """(image bytes, media type) of page ``number`` (1-based), if it was kept."""
        folder = self.folder / "pages" / self._check(sha)
        for suffix, media in ((".jpg", "image/jpeg"), (".png", "image/png")):
            path = folder / f"{int(number)}{suffix}"
            if path.is_file():
                return path.read_bytes(), media
        return None

    def get(self, sha: str) -> OcrResult | None:
        path = self._path(sha)
        try:
            return OcrResult.from_json(json.loads(path.read_text(encoding="utf-8")))
        except FileNotFoundError:
            return None
        except (ValueError, TypeError, KeyError):
            log.warning("Ignoring an unreadable OCR cache file: %s", path)
            return None

    def put(self, result: OcrResult) -> None:
        _write_json(self._path(result.sha256), result.to_json())
        self._path(result.sha256, partial=True).unlink(missing_ok=True)

    def partial(self, sha: str, model: str, mode: str) -> list[OcrPage]:
        """Pages already recognised (by the same model, the same way) in a run that stopped part-way through."""
        try:
            data = json.loads(self._path(sha, partial=True).read_text(encoding="utf-8"))
            if data.get("model") != model or data.get("mode") != mode:
                return []
            return [OcrPage(**p) for p in data.get("pages", [])]
        except FileNotFoundError:
            return []
        except (ValueError, TypeError, KeyError):
            return []

    def put_partial(self, sha: str, model: str, mode: str, pages: list[OcrPage]) -> None:
        _write_json(self._path(sha, partial=True),
                    {"sha256": sha, "model": model, "mode": mode, "pages": [asdict(p) for p in pages]})

    def remove(self, sha: str) -> None:
        self._path(sha).unlink(missing_ok=True)
        self._path(sha, partial=True).unlink(missing_ok=True)

    def __iter__(self) -> Iterator[OcrResult]:
        if not self.folder.is_dir():
            return
        for path in sorted(self.folder.glob("*.json")):
            if path.name.endswith(".partial.json"):
                continue
            result = self.get(path.stem)
            if result is not None:
                yield result
