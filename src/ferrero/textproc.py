"""Text normalisation for bilingual (English / Arabic) keyword search.

English terms are stemmed later by SQLite FTS5's porter tokenizer. Arabic terms are folded
(diacritics, tatweel, alef/ya/ta-marbuta variants, Arabic-Indic digits) and lightly stemmed
here (a light10-style prefix/suffix stripper), so العلامة / العلامات / علامة meet in one form.
Index and query text go through the same functions, so the stems only need to be consistent,
not linguistically perfect. A production index would use Azure AI Search's Arabic analyzer.
"""
from __future__ import annotations

import re
import unicodedata

# Not \b: file names use "_" (a word character) as a separator, e.g. "TM-2024-403_judgment.pdf".
CASE_ID_RE = re.compile(r"(?<![A-Za-z0-9])TM-\d{4}-\d{3}(?!\d)", re.IGNORECASE)
_PRESENTATION_FORMS = re.compile("[ﭐ-﷿ﹰ-﻿]")

_AR_MARKS = re.compile("[ؐ-ًؚ-ٰٟۖ-ۜ۟-۪ۨ-ۭـ]")
_FOLD = str.maketrans(
    {
        "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",  # alef forms -> ا
        "ى": "ي",  # ى -> ي
        "ة": "ه",  # ة -> ه
        "ؤ": "و",  # ؤ -> و
        "ئ": "ي",  # ئ -> ي
        **{chr(0x0660 + i): str(i) for i in range(10)},  # Arabic-Indic digits
        **{chr(0x06F0 + i): str(i) for i in range(10)},  # Extended Arabic-Indic digits
    }
)
_TOKEN = re.compile(r"[0-9a-zß-ɏ]+|[ء-يٱ-ۓ]+")
_ARABIC_LETTER = re.compile(r"[ء-يٱ-ۓ]")

_AR_PREFIXES = ("وال", "بال", "كال", "فال", "لل", "ال")
_AR_SUFFIXES = ("ها", "ان", "ات", "ون", "ين", "يه", "ه", "ي")

_STOP_EN = set(
    """a an the of in on at to for by with from and or not no is are was were be been being am do does did done
    what which who whom whose when where why how this that these those it its there their they them we our us you
    your i me my he she his her any all some about into over under than then so as if case cases please tell show
    give list me can could would should will shall may might must has have had""".split()
)
_STOP_AR = {
    "في", "من", "على", "الى", "عن", "ما", "ماذا", "هل", "التي", "الذي", "الذين", "هذا", "هذه", "ذلك", "تلك",
    "كان", "كانت", "مع", "او", "ثم", "قد", "لم", "لن", "ان", "كم", "اي", "هو", "هي", "هم", "بين", "كل", "بعد",
    "قبل", "عند", "حتى", "لا", "و", "تم", "فى", "له", "لها", "به", "بها", "منه", "منها", "فيه", "فيها", "عليه",
    "عليها", "القضيه", "قضيه", "قضايا", "القضايا",
}


def fold(text: str) -> str:
    """Unicode-normalise, lower-case and fold Arabic variants; keeps word boundaries intact."""
    text = unicodedata.normalize("NFKC", text)
    return _AR_MARKS.sub("", text).translate(_FOLD).lower()


def has_presentation_forms(text: str) -> bool:
    """True when Arabic text is stored as shaped glyphs (typical of some PDF text layers)."""
    return bool(_PRESENTATION_FORMS.search(text))


def contains(haystack_folded: str, needle: str) -> bool:
    """Case-, diacritic- and letter-variant-insensitive substring test (haystack already folded)."""
    needle = " ".join(fold(needle).split())
    return bool(needle) and needle in haystack_folded


def is_arabic(text: str, threshold: float = 0.5) -> bool:
    """True when most letters are Arabic (an English text quoting an Arabic name stays English)."""
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return False
    return sum(1 for ch in letters if _ARABIC_LETTER.match(ch)) / len(letters) >= threshold


def stem_ar(token: str) -> str:
    for prefix in _AR_PREFIXES:
        if token.startswith(prefix) and len(token) - len(prefix) >= 2:
            token = token[len(prefix):]
            break
    else:
        if token.startswith("و") and len(token) >= 4:  # conjunction wa-
            token = token[1:]
        elif token[0] in "بلكف" and len(token) >= 5:  # bi-/li-/ka-/fa- (بتعويض -> تعويض)
            token = token[1:]
    if token.endswith("ا") and len(token) >= 4:  # accusative tanween alef (تعويضاً -> تعويض)
        token = token[:-1]
    for suffix in _AR_SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 2:
            token = token[: -len(suffix)]
    return token


def _raw_tokens(text: str) -> list[str]:
    return _TOKEN.findall(fold(text))


def _stem(token: str) -> str:
    return stem_ar(token) if _ARABIC_LETTER.match(token) else token


def index_text(text: str) -> str:
    """The form stored in the full-text index."""
    return " ".join(_stem(t) for t in _raw_tokens(text))


def query_terms(text: str) -> list[str]:
    """Search terms for a free-text query: case numbers and stop words removed, stemmed, de-duplicated."""
    text = CASE_ID_RE.sub(" ", text)
    seen: dict[str, None] = {}
    for tok in _raw_tokens(text):
        if tok in _STOP_EN or tok in _STOP_AR or len(tok) < 2:
            continue
        seen.setdefault(_stem(tok), None)
    return list(seen)


def case_ids_in(text: str) -> list[str]:
    return list(dict.fromkeys(m.upper() for m in CASE_ID_RE.findall(text)))
