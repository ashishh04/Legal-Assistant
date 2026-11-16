"""FastAPI app: the chat page plus a small JSON/SSE API.

Demo identity: the browser picks one of the dim_user personas and a conversation is bound to that user
when it is created; later messages cannot switch identity. This is for the demo only - before the app is
reachable by anyone else, replace it with Entra ID sign-in (validate the token, map its group claims to the
roles in ``security.ROLES``).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Iterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..assistant.agent import TRY_AGAIN, Assistant, AssistantError
from ..assistant.tools import case_detail
from ..casemodel import CaseModel
from ..config import Settings, get_settings
from ..ocr.results import OcrCache
from ..sync.index import DocumentIndex
from . import views
from .superset import SupersetClient, SupersetError, SupersetSettings

STATIC = Path(__file__).parent / "static"   # the original single-file page (kept at /classic)
DIST = Path(__file__).parent / "dist"       # the React frontend, built by `npm run build` in frontend/
log = logging.getLogger(__name__)

EXAMPLES = [
    "What damages were awarded in TM-2024-428?",
    "Compare the outcomes of TM-2024-428 and TM-2024-407.",
    "ما شروط التسوية في القضية TM-2024-421؟",
    "Which open cases have a hearing in the next 30 days?",
    "How many open cases do we have in KSA?",
    "What did the test purchase in TM-2026-421 find?",
]
CASE_FIELDS = ("case_id", "title", "country", "court_name", "case_type", "status", "stage", "outcome", "next_hearing_date",
               "next_action", "next_action_due", "lead_counsel")


class NewConversation(BaseModel):
    user_id: str = Field(pattern=r"^U-\d{2}$")
    case_id: str | None = Field(default=None, pattern=r"^(?i:TM-\d{4}-\d{3})$")


class NewMessage(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class GuestTokenRequest(BaseModel):
    user_id: str = Field(pattern=r"^U-\d{2}$")
    dashboard: str = Field(pattern=r"^[0-9a-fA-F-]{32,36}$")  # the dashboard's embed id
    case_id: str | None = Field(default=None, pattern=r"^(?i:TM-\d{4}-\d{3})$")


def _sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"


def create_app(settings: Settings | None = None, assistant: Assistant | None = None,
               superset: SupersetClient | None = None) -> FastAPI:
    settings = settings or get_settings()
    if assistant is None:
        model = CaseModel(settings.csv_dir, settings.demo_today, catalogue=settings.catalogue_path)
        assistant = Assistant(settings, model, DocumentIndex(settings.index_path, readonly=True))
    if superset is None and (superset_settings := SupersetSettings.from_env()) is not None:
        superset = SupersetClient(superset_settings)
    app = FastAPI(title="Ferrero case intelligence", docs_url="/api/docs", redoc_url=None)
    app.state.assistant = assistant
    # every country in the case data, for the dashboards' row rules (listed positively, so unknown ones stay hidden)
    countries = sorted({r["country"] for t in assistant.model.tables.values() for r in t.dicts() if r.get("country")})

    def principal(user_id: str):
        p = assistant.model.principal(user_id)
        if p is None:
            raise HTTPException(404, f"Unknown user {user_id}")
        return p

    @app.get("/api/meta")
    def meta() -> dict[str, Any]:
        return {"model": settings.model, "effort": settings.effort, "provider": settings.provider,
                "demo_today": settings.demo_today.isoformat(), "org_name": settings.org_name,
                "index": assistant.index.stats(), "examples": EXAMPLES, "dashboards": views.superset_dashboards(),
                "embedded_dashboards": superset is not None}

    @app.get("/api/dashboards")
    def dashboards(user_id: str) -> dict[str, Any]:
        """The Superset dashboards this app can embed (or plain links from FERRERO_SUPERSET_DASHBOARDS)."""
        principal(user_id)
        if superset is None:
            links = views.superset_dashboards()
            return {"mode": "links" if links else "none", "dashboards": links}
        try:
            found = superset.dashboards()
        except SupersetError as e:
            log.warning("Dashboards unavailable: %s", e)
            return {"mode": "embedded", "superset_url": superset.settings.url, "dashboards": [], "error": e.public}
        return {"mode": "embedded", "superset_url": superset.settings.url, "frame_ancestors": superset.frame_ancestors(),
                "dashboards": [d.public() for d in found if d.uuid]}

    @app.post("/api/dashboards/guest-token")
    def dashboard_token(body: GuestTokenRequest) -> dict[str, str]:
        """A short-lived token for one embedded dashboard, limited to the rows this persona may see."""
        if superset is None:
            raise HTTPException(404, "Dashboards are not connected")
        p = principal(body.user_id)
        case_id = body.case_id.upper() if body.case_id else None
        if case_id and assistant.model.visible_case(p, case_id) is None:
            raise HTTPException(404, f"Case {case_id} is not available to this user")
        visible = [r["case_id"] for r in assistant.model.tables["fact_case"].dicts() if p.sees_group(r["access_group"])]
        try:
            token = superset.guest_token(p, body.dashboard, countries, visible, case_id)
        except SupersetError as e:
            log.warning("Dashboard token for %s failed: %s", body.user_id, e)
            raise HTTPException(e.status, e.public) from None
        return {"token": token}

    @app.get("/api/users")
    def users() -> list[dict[str, Any]]:
        return assistant.model.users()

    @app.get("/api/overview")
    def overview(user_id: str, country: str | None = None, mark: str | None = None) -> dict[str, Any]:
        return views.overview(assistant.model, principal(user_id), country=country or None, mark=mark or None)

    @app.get("/api/cases")
    def cases(user_id: str) -> list[dict[str, Any]]:
        return views.case_list(assistant.model, principal(user_id))

    @app.get("/api/cases/{case_id}")
    def case(case_id: str, user_id: str) -> dict[str, Any]:
        found = case_detail(assistant.model, assistant.index, principal(user_id), case_id.upper())
        if found is None:
            raise HTTPException(404, f"Case {case_id} is not available to this user")
        return found

    @app.get("/api/sync")
    def sync_status(user_id: str) -> dict[str, Any]:
        return views.documents(assistant.index, principal(user_id))

    ocr_cache = OcrCache(settings.ocr_dir)

    @app.get("/api/documents/{name}")
    def document(name: str, user_id: str) -> dict[str, Any]:
        """One synced document: its searchable text and, for scans, its page images and recognition confidence."""
        p = principal(user_id)
        meta_ = assistant.index.document_meta(p, name)
        if meta_ is None:
            raise HTTPException(404, f"Document {name} is not available to this user")
        found = assistant.index.document(p, name)
        sha = meta_.pop("content_sha", None)
        result = ocr_cache.get(sha) if sha and meta_["extraction"] == "ocr" else None
        page_count = meta_["pages"] or (len(result.pages) if result else 0)
        images = bool(sha and meta_["extraction"] == "ocr" and ocr_cache.page_image(sha, 1))
        return {
            **meta_,
            "sections": [{"section": h.section, "seq": h.seq, "blocks": list(h.blocks)} for h in found[1]] if found else [],
            "page_images": page_count if images else 0,
            "page_confidence": [pg.score for pg in result.pages] if result else [],
            "review_confidence": settings.ocr_review_confidence,
        }

    @app.get("/api/documents/{name}/pages/{number}")
    def document_page(name: str, number: int, user_id: str) -> Response:
        """A scanned page as stored in the scan, for checking the recognised text against it."""
        meta_ = assistant.index.document_meta(principal(user_id), name)
        found = ocr_cache.page_image(meta_["content_sha"], number) if meta_ and meta_["content_sha"] and number >= 1 else None
        if found is None:
            raise HTTPException(404, "Page not available")
        data, media_type = found
        return Response(data, media_type=media_type, headers={"Cache-Control": "private, max-age=3600"})

    @app.post("/api/conversations")
    def new_conversation(body: NewConversation) -> dict[str, Any]:
        try:
            conv = assistant.start(body.user_id, body.case_id)
        except AssistantError as e:
            raise HTTPException(404, e.public) from None
        p = conv.principal
        return {
            "conversation_id": conv.id,
            "user": {"user_id": p.user_id, "full_name": p.full_name, "job_title": p.job_title,
                     "entra_group": p.entra_group, "access": p.role.description, "documents": p.sees_documents},
            "case": {k: conv.case_focus[k] for k in CASE_FIELDS} if conv.case_focus else None,
            "case_requested": body.case_id.upper() if body.case_id else None,
        }

    @app.post("/api/conversations/{conversation_id}/messages")
    def send(conversation_id: str, body: NewMessage) -> StreamingResponse:
        conv = assistant.conversations.get(conversation_id)
        if conv is None:
            raise HTTPException(404, "This conversation has expired; start a new one.")

        def events() -> Iterator[str]:
            try:
                for event in assistant.ask(conv, body.text.strip()):
                    yield _sse(event)
            except AssistantError as e:  # users see the plain-language message; operators get the detail in the log
                log.warning("Turn failed in conversation %s: %s", conversation_id, e)
                yield _sse({"type": "error", "message": e.public})
            except Exception:
                log.exception("Turn failed in conversation %s", conversation_id)
                yield _sse({"type": "error", "message": TRY_AGAIN})
            yield _sse({"type": "done"})

        return StreamingResponse(events(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/classic", include_in_schema=False)
    def classic() -> FileResponse:
        return FileResponse(STATIC / "index.html")

    if (DIST / "index.html").is_file():
        app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            if path.startswith("api/"):
                raise HTTPException(404, "Not found")
            candidate = (DIST / path).resolve()
            if path and candidate.is_file() and DIST.resolve() in candidate.parents:
                return FileResponse(candidate)  # favicon and other root-level build files
            return FileResponse(DIST / "index.html")  # client-side routes: /cases/TM-2024-428, /assistant, …
    else:
        @app.get("/", include_in_schema=False)
        def index() -> FileResponse:
            return FileResponse(STATIC / "index.html")

    return app
