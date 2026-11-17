"""Indicative similarity between a registered word mark and the sign used on an infringing product.

These are aids for the person assessing the case, not a legal finding: how many letters differ, whether the two
would sound alike, and whether one contains the other. Latin and Arabic signs are both handled; a sign written in
Arabic is compared with the mark's registered Arabic name.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

_ARABIC = re.compile(r"[؀-ۿ]")
_ARABIC_DIACRITICS = re.compile(r"[ً-ٰٟۖ-ۭـ]")  # harakat, superscript alef, tatweel
_ARABIC_FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ة": "ه", "ى": "ي", "ؤ": "و", "ئ": "ي"})
_LATIN_DIGRAPHS = (("PH", "F"), ("GH", "G"), ("CK", "K"), ("QU", "K"), ("SCH", "SK"), ("X", "KS"))
_LATIN_SOUNDS = str.maketrans({"Q": "K", "Z": "S", "W": "V", "J": "G"})
_LATIN_VOWELS = set("AEIOUY")
_ARABIC_VOWELS = set("اوي")


def is_arabic(text: str) -> bool:
    return bool(_ARABIC.search(text or ""))


def normalise(text: str) -> str:
    """Letters and digits only, upper case, accents and Arabic diacritics removed, Arabic letter forms folded."""
    text = _ARABIC_DIACRITICS.sub("", text or "").translate(_ARABIC_FOLD)
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    return "".join(c for c in text.upper() if c.isalnum())


def levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def _collapse(text: str) -> str:
    return re.sub(r"(.)\1+", r"\1", text)


def phonetic_key(text: str) -> str:
    """A rough sound key: similar-sounding letters merged, doubled letters collapsed, vowels after the first dropped."""
    word = normalise(text)
    if not word:
        return ""
    if is_arabic(word):
        word = _collapse(word)
        return word[0] + "".join(c for c in word[1:] if c not in _ARABIC_VOWELS)
    word = "".join(c for c in word if c.isalpha())
    for old, new in _LATIN_DIGRAPHS:
        word = word.replace(old, new)
    word = re.sub(r"C(?=[EIY])", "S", word).replace("C", "K").translate(_LATIN_SOUNDS)
    word = _collapse(word)
    return word[:1] + "".join(c for c in word[1:] if c not in _LATIN_VOWELS) if word else ""


def compare(mark_name: str, mark_name_ar: str | None, sign: str) -> dict[str, Any]:
    """How close the sign is to the registered mark, with a one-word indication (High, Medium or Low)."""
    arabic = is_arabic(sign)
    reference = mark_name_ar if arabic and mark_name_ar else mark_name
    a, b = normalise(reference), normalise(sign)
    if not a or not b:
        return {"compared_with": reference, "word_similarity": None, "letters_different": None, "sounds_alike": False,
                "contains_mark": False, "indication": None}
    distance = levenshtein(a, b)
    similarity = 1 - distance / max(len(a), len(b))
    sounds = phonetic_key(reference) == phonetic_key(sign)
    contains = len(a) >= 3 and len(b) >= 3 and (a in b or b in a)
    if similarity >= 0.8 or sounds or contains:
        indication = "High"
    elif similarity >= 0.6:
        indication = "Medium"
    else:
        indication = "Low"
    return {"compared_with": reference, "word_similarity": round(similarity, 2), "letters_different": distance,
            "sounds_alike": sounds, "contains_mark": contains, "identical": a == b, "indication": indication}
