"""Evidence and supporting documents: categories, accepted file types, and the content-addressed file store.

A file is accepted only when its name has an allowed extension and its first bytes match that type, so a page or a
script cannot be passed off as a photo. Stored files are named by their SHA-256: the name proves the content (the
fingerprint is also written to the audit trail at upload), and they are never overwritten or deleted.
"""
from __future__ import annotations

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PureWindowsPath
from typing import BinaryIO, Callable

from .errors import RecordError

CATEGORIES = (
    "Product photo", "Screenshot", "Cease-and-desist letter", "Correspondence with authorities", "Invoice",
    "External counsel document", "Other evidence",
)
PHOTO_CATEGORIES = ("Product photo", "Screenshot")
EDITABLE = {"category": "Category", "title": "Title", "captured_on": "Captured or dated", "location": "Where found",
            "notes": "Notes"}
SHA256 = re.compile(r"[0-9a-f]{64}")
_HEIF_BRANDS = {b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"mif1", b"msf1"}


def _starts(*prefixes: bytes) -> Callable[[bytes], bool]:
    return lambda head: any(head.startswith(p) for p in prefixes)


_ZIP = _starts(b"PK\x03\x04")                         # Office Open XML
_OLE = _starts(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")   # legacy Office, Outlook .msg


def _text(head: bytes) -> bool:
    return b"\x00" not in head


@dataclass(frozen=True)
class FileKind:
    content_type: str
    label: str
    matches: Callable[[bytes], bool]
    image: bool = False   # browsers can show it: gallery and preview
    inline: bool = False  # opened in the browser rather than downloaded


_JPEG = FileKind("image/jpeg", "JPEG photo", _starts(b"\xff\xd8\xff"), image=True, inline=True)
_HEIF = FileKind("image/heic", "HEIC photo", lambda h: h[4:8] == b"ftyp" and h[8:12] in _HEIF_BRANDS)  # few browsers show it
KINDS: dict[str, FileKind] = {
    ".jpg": _JPEG, ".jpeg": _JPEG,
    ".png": FileKind("image/png", "PNG image", _starts(b"\x89PNG\r\n\x1a\n"), image=True, inline=True),
    ".webp": FileKind("image/webp", "WebP image", lambda h: h[:4] == b"RIFF" and h[8:12] == b"WEBP", image=True, inline=True),
    ".gif": FileKind("image/gif", "GIF image", _starts(b"GIF87a", b"GIF89a"), image=True, inline=True),
    ".heic": _HEIF, ".heif": _HEIF,
    ".pdf": FileKind("application/pdf", "PDF document", lambda h: b"%PDF-" in h[:1024], inline=True),
    ".docx": FileKind("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "Word document", _ZIP),
    ".doc": FileKind("application/msword", "Word document", _OLE),
    ".xlsx": FileKind("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "Excel workbook", _ZIP),
    ".xls": FileKind("application/vnd.ms-excel", "Excel workbook", _OLE),
    ".pptx": FileKind("application/vnd.openxmlformats-officedocument.presentationml.presentation", "PowerPoint file", _ZIP),
    ".msg": FileKind("application/vnd.ms-outlook", "Outlook message", _OLE),
    ".eml": FileKind("message/rfc822", "E-mail message", _text),
    ".txt": FileKind("text/plain", "Text file", _text),
    ".csv": FileKind("text/csv", "CSV file", _text),
}
BY_CONTENT_TYPE = {k.content_type: k for k in KINDS.values()}
ACCEPT = ",".join(KINDS)  # for the file picker
ALLOWED = "photos (JPEG, PNG, WebP, GIF, HEIC), PDF, Word, Excel, PowerPoint, e-mails (.msg, .eml), text and CSV"


def kind_for(file_name: str) -> FileKind:
    ext = Path(file_name).suffix.lower()
    kind = KINDS.get(ext)
    if kind is None:
        raise RecordError(f"{ext or 'Files without an extension'} can't be added as evidence. Allowed: {ALLOWED}.", 415,
                          "file_type")
    return kind


def kind_of(content_type: str) -> FileKind:
    return BY_CONTENT_TYPE.get(content_type) or FileKind(content_type, "File", _text)


def clean_file_name(raw: str | None) -> str:
    # The browser sends a bare name; drop any folder part (either separator) and control characters.
    name = PureWindowsPath((raw or "").replace("/", "\\")).name
    name = "".join(ch for ch in name if ch.isprintable()).strip().strip(".")
    if not name:
        raise RecordError("The file needs a name.")
    if len(name) > 255:
        stem, ext = os.path.splitext(name)
        name = stem[: 255 - len(ext)] + ext
    return name


def _text_field(value: object, label: str, limit: int, *, multiline: bool = False) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise RecordError(f"{label} must be text.")
    value = value.strip() if multiline else " ".join(value.split())
    if len(value) > limit:
        raise RecordError(f"{label} is limited to {limit} characters.")
    return value or None


def parse_day(value: object, label: str) -> str | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, date):
        day = value
    else:
        try:
            day = date.fromisoformat(str(value).strip()[:10])
        except ValueError:
            raise RecordError(f"{label} must be a date (YYYY-MM-DD).") from None
    if not 1990 <= day.year <= 2100:
        raise RecordError(f"{label} must be a date between 1990 and 2100.")
    return day.isoformat()


def clean_meta(values: dict[str, object], today: date, *, partial: bool = False) -> dict[str, str | None]:
    """Category, title, date, place and notes of an evidence item, validated. ``partial``: only the keys given."""
    unknown = sorted(set(values) - set(EDITABLE))
    if unknown:
        raise RecordError(f"These evidence details can't be changed: {', '.join(unknown)}.")
    out: dict[str, str | None] = {}
    if "category" in values or not partial:
        if values.get("category") not in CATEGORIES:
            raise RecordError(f"Choose a category: {', '.join(CATEGORIES)}.")
        out["category"] = str(values["category"])
    if "title" in values or not partial:
        out["title"] = _text_field(values.get("title"), "Title", 200)
        if partial and not out["title"]:
            raise RecordError("The title can't be empty.")
    if "captured_on" in values or not partial:
        out["captured_on"] = parse_day(values.get("captured_on"), "The capture or document date")
        if out["captured_on"] and out["captured_on"] > today.isoformat():
            raise RecordError("The capture or document date can't be in the future.")
    if "location" in values or not partial:
        out["location"] = _text_field(values.get("location"), "Where found", 300)
    if "notes" in values or not partial:
        out["notes"] = _text_field(values.get("notes"), "Notes", 2000, multiline=True)
    return out


@dataclass(frozen=True)
class Stored:
    sha256: str
    size: int
    kind: FileKind


class BlobStore:
    """Files named by their SHA-256 under ``root/<first two hex digits>/``; the same content is stored once."""

    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def path(self, sha256: str) -> Path:
        if not SHA256.fullmatch(sha256):
            raise ValueError(f"not a SHA-256: {sha256!r}")
        return self.root / sha256[:2] / sha256

    def ingest(self, stream: BinaryIO, file_name: str, max_mb: int) -> Stored:
        """Copy an upload into the store, checking its type and size on the way; returns its fingerprint."""
        kind = kind_for(file_name)
        limit = max_mb * 1024 * 1024
        digest, size, head = hashlib.sha256(), 0, b""
        fd, tmp = tempfile.mkstemp(prefix=".upload-", dir=self.root)
        try:
            with os.fdopen(fd, "wb") as out:
                while chunk := stream.read(1 << 16):
                    if len(head) < 8192:
                        head += chunk[: 8192 - len(head)]
                    size += len(chunk)
                    if size > limit:
                        raise RecordError(f"The file is larger than {max_mb} MB.", 413, "too_large")
                    digest.update(chunk)
                    out.write(chunk)
            if size == 0:
                raise RecordError("The file is empty.")
            if not kind.matches(head):
                raise RecordError(f"This file isn't a real {kind.label}: its content doesn't match its "
                                  f"{Path(file_name).suffix.lower()} name.", 415, "file_content")
            sha = digest.hexdigest()
            dest = self.path(sha)
            if dest.exists():
                os.unlink(tmp)  # already stored (the same file on another case, or withdrawn and added again)
            else:
                dest.parent.mkdir(exist_ok=True)
                os.replace(tmp, dest)
                os.chmod(dest, 0o444)  # read-only: evidence is never changed in place
            return Stored(sha, size, kind)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def verify(self, sha256: str) -> bool:
        """Whether the stored file still has the fingerprint it was stored under."""
        p = self.path(sha256)
        if not p.is_file():
            return False
        digest = hashlib.sha256()
        with p.open("rb") as f:
            while chunk := f.read(1 << 20):
                digest.update(chunk)
        return digest.hexdigest() == sha256
