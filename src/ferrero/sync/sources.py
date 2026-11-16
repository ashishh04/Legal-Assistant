"""Where documents come from.

* ``LocalFolderSource`` – a folder on disk (the demo pack's ``documents/``), listed in full each run.
* ``SharePointSource`` – SharePoint document libraries through Microsoft Graph, app-only auth,
  incremental via the drive delta API. Grant the app registration ``Sites.Selected`` on the
  Legal site only (least privilege), not tenant-wide ``Sites.Read.All``.
"""
from __future__ import annotations

import csv
import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import partial
from pathlib import Path, PurePosixPath
from typing import Callable, Protocol
from urllib.parse import unquote

import httpx

from .extract import SUPPORTED_SUFFIXES

GRAPH = "https://graph.microsoft.com/v1.0"


@dataclass
class SourceFile:
    key: str             # stable identifier within the source (relative path, Graph item id)
    name: str            # file name
    library_path: str    # SharePoint-style path, e.g. /sites/Legal/Cases/UAE/TM-2024-428/<file>
    version: str | None  # changes whenever the content changes
    modified_at: str | None
    read: Callable[[], bytes] = field(repr=False)
    hints: dict[str, str] = field(default_factory=dict)  # authoritative metadata from a manifest, if any


@dataclass
class Changes:
    files: list[SourceFile]  # new or changed files (all files when ``complete``)
    deleted: list[str]       # keys removed since the cursor
    complete: bool           # True: ``files`` is the full listing, so anything else synced from here is gone
    cursor: str | None       # opaque token for the next incremental run


class Source(Protocol):
    name: str

    def changes(self, cursor: str | None) -> Changes: ...


def _supported(name: str) -> bool:
    return PurePosixPath(name).suffix.lower() in SUPPORTED_SUFFIXES and not name.startswith("~$")


def load_manifest(path: Path) -> dict[str, dict[str, str]]:
    """File name -> row of a corpus manifest (e.g. documents_150_meta/manifest.csv).

    The manifest is the authoritative file -> case mapping (file names are deliberately messy). Any
    ``password`` column is dropped unread: protected files are recorded as skipped, never opened.
    """
    rows: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            row.pop("password", None)
            clean = {k.strip(): (v or "").strip() for k, v in row.items() if k}
            name = PurePosixPath(clean.get("file", "").replace("\\", "/")).name
            if name:
                rows[name] = clean
    return rows


def manifest_next_to(folder: Path) -> Path | None:
    """``<folder>_meta/manifest.csv`` when it exists (the layout of the documents_150 corpus)."""
    candidate = folder.parent / f"{folder.name}_meta" / "manifest.csv"
    return candidate if candidate.is_file() else None


class LocalFolderSource:
    name = "local"

    def __init__(self, root: Path, library_path_for: Callable[[str], str | None] | None = None,
                 site_root: str = "/sites/Legal/Cases", manifest: dict[str, dict[str, str]] | None = None):
        self.root = Path(root)
        self.library_path_for = library_path_for
        self.site_root = site_root.rstrip("/")
        self.manifest = manifest or {}

    def changes(self, cursor: str | None = None) -> Changes:
        if not self.root.is_dir():
            raise FileNotFoundError(f"Document folder not found: {self.root}")
        files = []
        for path in sorted(self.root.rglob("*")):
            if not path.is_file() or not _supported(path.name):
                continue
            rel = path.relative_to(self.root).as_posix()
            hints = self.manifest.get(path.name, {})
            mapped = hints.get("library_path") or (self.library_path_for(path.name) if self.library_path_for else None)
            modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
            files.append(SourceFile(
                key=rel, name=path.name, library_path=mapped or f"{self.site_root}/{rel}",
                version=hashlib.sha256(path.read_bytes()).hexdigest()[:20], modified_at=modified, read=path.read_bytes,
                hints=hints,
            ))
        return Changes(files, [], complete=True, cursor=None)


class SharePointSource:
    name = "sharepoint"

    def __init__(self, tenant_id: str, client_id: str, client_secret: str, hostname: str,
                 site_path: str = "Legal", library: str = "Cases", http: httpx.Client | None = None):
        self.tenant_id, self.client_id, self._secret = tenant_id, client_id, client_secret
        self.hostname, self.site_path, self.library = hostname, site_path.strip("/"), library
        self._http = http or httpx.Client(timeout=60.0, follow_redirects=True)
        self._token: str | None = None
        self._token_expires = 0.0

    # ---------- HTTP ----------
    def _headers(self) -> dict[str, str]:
        if self._token is None or time.time() > self._token_expires - 120:
            r = self._http.post(
                f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token",
                data={"client_id": self.client_id, "client_secret": self._secret,
                      "scope": "https://graph.microsoft.com/.default", "grant_type": "client_credentials"},
            )
            r.raise_for_status()
            body = r.json()
            self._token = body["access_token"]
            self._token_expires = time.time() + int(body.get("expires_in", 3600))
        return {"Authorization": f"Bearer {self._token}"}

    def _get(self, url: str) -> httpx.Response:
        for attempt in range(5):
            r = self._http.get(url, headers=self._headers())
            if r.status_code in (429, 503) and attempt < 4:  # throttled: honour Retry-After
                time.sleep(min(60, int(r.headers.get("Retry-After", "5"))))
                continue
            r.raise_for_status()
            return r
        raise RuntimeError("unreachable")

    # ---------- listing ----------
    def _drive_id(self) -> str:
        site = self._get(f"{GRAPH}/sites/{self.hostname}:/sites/{self.site_path}").json()
        for drive in self._get(f"{GRAPH}/sites/{site['id']}/drives").json().get("value", []):
            if drive.get("name") == self.library or drive.get("webUrl", "").rstrip("/").endswith(f"/{self.library}"):
                return drive["id"]
        raise LookupError(f"Document library {self.library!r} not found on site /sites/{self.site_path}")

    def changes(self, cursor: str | None = None) -> Changes:
        drive_id = self._drive_id()
        url = cursor or f"{GRAPH}/drives/{drive_id}/root/delta"
        files: list[SourceFile] = []
        deleted: list[str] = []
        while True:
            page = self._get(url).json()
            for item in page.get("value", []):
                if "deleted" in item:
                    deleted.append(item["id"])
                elif "file" in item and _supported(item.get("name", "")):
                    files.append(self._file(drive_id, item))
            if "@odata.nextLink" in page:
                url = page["@odata.nextLink"]
                continue
            return Changes(files, deleted, complete=cursor is None, cursor=page.get("@odata.deltaLink"))

    def _file(self, drive_id: str, item: dict) -> SourceFile:
        parent = unquote(item.get("parentReference", {}).get("path", ""))  # /drives/<id>/root:/UAE/TM-2024-428
        folder = parent.split("root:", 1)[1].strip("/") if "root:" in parent else ""
        library_path = "/".join(p for p in (f"/sites/{self.site_path}/{self.library}", folder, item["name"]) if p)
        return SourceFile(
            key=item["id"], name=item["name"], library_path=library_path,
            version=item.get("cTag") or item.get("eTag") or item.get("lastModifiedDateTime"),
            modified_at=item.get("lastModifiedDateTime"),
            read=partial(self._download, drive_id, item["id"]),
        )

    def _download(self, drive_id: str, item_id: str) -> bytes:
        # Graph answers with a redirect to a pre-authenticated URL; httpx drops the bearer token cross-origin.
        return self._get(f"{GRAPH}/drives/{drive_id}/items/{item_id}/content").content
