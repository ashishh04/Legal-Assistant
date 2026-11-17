"""Shared fixtures. No network and no API key: Claude and Microsoft Graph are replaced by local fakes."""
from __future__ import annotations

import itertools
import json
import shutil
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

import anthropic
import pytest

from ferrero.casemodel import CaseModel
from ferrero.config import PROJECT_ROOT, Settings
from ferrero.sync.index import DocumentIndex
from ferrero.sync.runner import run_sync
from ferrero.sync.sources import LocalFolderSource

PACK = PROJECT_ROOT / "docs" / "Ferrero_Demo_Pack"
DEMO_TODAY = date(2026, 11, 5)
TEST_PASSWORD = "Starting-pass-2026"  # the starting password in tests (FERRERO_DEMO_PASSWORD)


def sign_in(client, user_id: str):
    """Sign a TestClient in as one of the dim_user accounts (its cookie jar keeps the session)."""
    client.headers["X-Ferrero"] = "1"
    r = client.post("/api/auth/login", json={"login": user_id, "password": TEST_PASSWORD})
    assert r.status_code == 200, r.text
    return client


@pytest.fixture(scope="session")
def model() -> CaseModel:
    return CaseModel(PACK / "csv", DEMO_TODAY)


def catalogue_paths(model: CaseModel) -> Callable[[str], str | None]:
    return lambda name: (model.catalogue_entry(name) or {}).get("library_path")


@pytest.fixture(scope="session")
def pack_docs(tmp_path_factory, model) -> Path:
    """Just the 12 pack documents (the live documents/ folder also holds other files)."""
    folder = tmp_path_factory.mktemp("pack_docs")
    for p in (PACK / "documents").glob("*.docx"):
        if model.catalogue_entry(p.name):
            shutil.copy2(p, folder / p.name)
    assert len(list(folder.iterdir())) == 12
    return folder


@pytest.fixture(scope="session")
def index(tmp_path_factory, model, pack_docs) -> DocumentIndex:
    ix = DocumentIndex(tmp_path_factory.mktemp("index") / "index.sqlite")
    result = run_sync(LocalFolderSource(pack_docs, library_path_for=catalogue_paths(model)), ix, model)
    assert len(result.indexed) == 12, result.summary()
    return ix


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(pack_dir=PACK, data_dir=tmp_path, demo_today=DEMO_TODAY, demo_password=TEST_PASSWORD)


@pytest.fixture(scope="session")
def principals(model):
    return {name: model.principal(uid) for name, uid in
            {"ops": "U-08", "uae": "U-04", "ksa": "U-05", "mena": "U-06", "procurement": "U-10"}.items()}


# ---------- a local stand-in for the Claude Messages API ----------
_ids = itertools.count(1)


def message(content: list[dict], stop_reason: str = "end_turn", model: str = "claude-opus-5-5") -> dict[str, Any]:
    return {"id": f"msg_{next(_ids)}", "type": "message", "role": "assistant", "model": model, "content": content,
            "stop_reason": stop_reason, "stop_sequence": None,
            "usage": {"input_tokens": 1500, "output_tokens": 90, "cache_read_input_tokens": 1200,
                      "cache_creation_input_tokens": 0}}


def thinking(signature: str = "sig-abc") -> dict[str, Any]:
    return {"type": "thinking", "thinking": "", "signature": signature}


def tool_use(name: str, tool_input: dict, tool_id: str | None = None) -> dict[str, Any]:
    return {"type": "tool_use", "id": tool_id or f"toolu_{next(_ids)}", "name": name, "input": tool_input}


def text(value: str, citations: list[dict] | None = None) -> dict[str, Any]:
    block: dict[str, Any] = {"type": "text", "text": value}
    if citations:
        block["citations"] = citations
    return block


class FakeClaude:
    """Replays scripted responses (dicts, callables taking the request body, or ("status", code))."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.responses: list[Any] = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fake.requests.append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()},
                                      "body": body})
                status, payload = 200, fake.responses.pop(0) if fake.responses else ("status", 500)
                if isinstance(payload, tuple):
                    status, payload = payload[1], {"type": "error", "error": {"type": "api_error", "message": "scripted"}}
                elif callable(payload):
                    payload = payload(body)
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args: Any) -> None:
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def client(self) -> anthropic.Anthropic:
        return anthropic.Anthropic(api_key="test-key", base_url=f"http://127.0.0.1:{self.server.server_port}", max_retries=0)

    def close(self) -> None:
        self.server.shutdown()


@pytest.fixture
def fake_claude():
    fake = FakeClaude()
    yield fake
    fake.close()
