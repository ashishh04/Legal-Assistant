"""Group a document's blocks into passages: one section (or a window of a long section) per passage.

A passage is the unit of search; its blocks stay separate so the assistant's citations can
point at a single paragraph, list item or table row.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .extract import Section

MAX_PASSAGE_CHARS = 1800
_SENTENCE_END = re.compile(r"(?<=[.!?؟。])\s+")


@dataclass(frozen=True)
class Passage:
    seq: int
    section: str
    blocks: tuple[str, ...]

    @property
    def text(self) -> str:
        return "\n".join(self.blocks)


def _split_long(block: str, limit: int) -> list[str]:
    if len(block) <= limit:
        return [block]
    parts, current = [], ""
    for sentence in _SENTENCE_END.split(block):
        while len(sentence) > limit:  # one enormous sentence: hard split
            if current:
                parts.append(current)
                current = ""
            parts.append(sentence[:limit])
            sentence = sentence[limit:]
        if current and len(current) + 1 + len(sentence) > limit:
            parts.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        parts.append(current)
    return parts


def passages(sections: list[Section], limit: int = MAX_PASSAGE_CHARS) -> list[Passage]:
    out: list[Passage] = []
    for section in sections:
        window: list[str] = []
        size = 0
        for block in (piece for b in section.blocks for piece in _split_long(b, limit)):
            if window and size + len(block) > limit:
                out.append(Passage(len(out), section.heading, tuple(window)))
                window, size = [], 0
            window.append(block)
            size += len(block) + 1
        if window:
            out.append(Passage(len(out), section.heading, tuple(window)))
    return out
