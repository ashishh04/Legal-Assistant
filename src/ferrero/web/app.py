"""FastAPI app: the web frontend plus a JSON/SSE API.

Everyone signs in (``ferrero.auth``): the session cookie decides who is asking, and every endpoint serves only what
that person's role may see or change. Nothing the browser sends can choose the user. State-changing requests must
carry the ``X-Ferrero`` header, which another site can't add, so a page elsewhere can't act with the user's cookie.
For a single sign-on later, map the identity provider's token and group claims to ``security.ROLES`` in
``current_principal``.
"""
from __future__ import annotations

import json
import logging
import tempfile
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, AsyncIterator, Iterator

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi import Path as FastAPIPath
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..assistant.agent import TRY_AGAIN, Assistant, AssistantError
from ..assistant.tools import case_detail
from ..auth import Auth, AuthError
from ..casemodel import CaseModel
from ..config import Settings, get_settings
from ..ocr.results import OcrCache
from ..records import CaseRecords, RecordError, case_options
from ..records.mailer import Mailer
from ..security import Principal
from ..sync.index import DocumentIndex
from . import views
from .superset import SupersetClient, SupersetError, SupersetSettings

STATIC = Path(__file__).parent / "static"   # the original single-file page's assets (the page itself is retired)
DIST = Path(__file__).parent / "dist"       # the React frontend, built by `npm run build` in frontend/
MARKS = Path(__file__).parent / "marks"     # registered mark specimens (MK-01.png ...), for the trademark comparison
COOKIE = "ferrero_session"
CSRF_HEADER = "x-ferrero"
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
CASE_ID = r"^(?i:TM-\d{4}-\d{3})$"
MARK_ID = r"^MK-\d{2}$"


class SignIn(BaseModel):
    login: str = Field(default="", max_length=200)      # e-mail address or user id
    password: str = Field(default="", max_length=400)
    remember: bool = False


class PasswordChange(BaseModel):
    current_password: str = Field(default="", max_length=400)
    new_password: str = Field(default="", max_length=400)


class NewConversation(BaseModel):
    case_id: str | None = Field(default=None, pattern=CASE_ID)


class NewMessage(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class GuestTokenRequest(BaseModel):
    dashboard: str = Field(pattern=r"^[0-9a-fA-F-]{32,36}$")  # the dashboard's embed id
    case_id: str | None = Field(default=None, pattern=CASE_ID)


class CaseChange(BaseModel):
    changes: dict[str, Any]
    reason: str | None = Field(default=None, max_length=2000)
    override_reason: str | None = Field(default=None, max_length=2000)  # going ahead without business clearance


class Changes(BaseModel):
    changes: dict[str, Any]
    reason: str | None = Field(default=None, max_length=2000)


class Withdrawal(BaseModel):
    reason: str = Field(default="", max_length=2000)


class NewFollowUp(BaseModel):
    kind: str | None = None
    title: str | None = Field(default=None, max_length=400)
    details: str | None = Field(default=None, max_length=4000)
    owner_id: str | None = None
    start_date: str | None = None
    period_days: int | None = None
    due_date: str | None = None
    remind_days: int | None = None


class FollowUpDecision(BaseModel):
    decision: str
    note: str | None = Field(default=None, max_length=2000)
    outcome: str | None = None
    closed_date: str | None = None
    case_changes: dict[str, Any] | None = None
    override_reason: str | None = Field(default=None, max_length=2000)


class NewCase(BaseModel):
    mark_id: str | None = Field(default=None, max_length=10)
    infringer_id: str | None = Field(default=None, max_length=12)
    infringer_name: str | None = Field(default=None, max_length=400)
    infringer_name_ar: str | None = Field(default=None, max_length=400)
    infringer_type: str | None = Field(default=None, max_length=80)
    infringer_city: str | None = Field(default=None, max_length=200)
    case_type: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=40)
    court_id: str | None = Field(default=None, max_length=10)
    source_channel: str | None = Field(default=None, max_length=80)
    opened_date: str | None = Field(default=None, max_length=10)
    priority: str | None = Field(default=None, max_length=10)
    risk_rating: str | None = Field(default=None, max_length=10)
    lead_counsel_id: str | None = Field(default=None, max_length=10)
    external_firm: str | None = Field(default=None, max_length=400)
    next_action: str | None = Field(default=None, max_length=400)
    next_action_due: str | None = Field(default=None, max_length=10)
    claim_amount_local: float | None = None
    language: str | None = Field(default=None, max_length=10)
    sensitivity: str | None = Field(default=None, max_length=20)
    business_priority: str | None = Field(default=None, max_length=10)
    consultation_required: bool | None = None
    commercial_relationship: str | None = Field(default=None, max_length=40)
    details: str | None = Field(default=None, max_length=4000)


class Comparison(BaseModel):
    infringing_sign: str | None = Field(default=None, max_length=240)
    evidence_id: str | None = Field(default=None, max_length=12)
    visual: str | None = None
    phonetic: str | None = None
    conceptual: str | None = None
    goods: str | None = None
    overall: str | None = None
    notes: str | None = Field(default=None, max_length=4000)


class NewUser(BaseModel):
    full_name: str | None = Field(default=None, max_length=240)
    email: str | None = Field(default=None, max_length=240)
    job_title: str | None = Field(default=None, max_length=240)
    entra_group: str | None = Field(default=None, max_length=40)
    country: str | None = Field(default=None, max_length=40)
    password: str | None = Field(default=None, max_length=400)


class UserChanges(BaseModel):
    changes: dict[str, Any]


class TemporaryPassword(BaseModel):
    password: str = Field(default="", max_length=400)


class SwitchTo(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)


class ReadMark(BaseModel):
    ids: list[int] | None = None  # None: all


def _sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"


def current_principal(request: Request) -> Principal:
    """The signed-in user, from the session cookie; 401 without a live session."""
    p = request.app.state.auth.session(request.cookies.get(COOKIE))
    if p is None:
        raise HTTPException(401, "Please sign in.")
    return p


# Module level on purpose: with postponed annotations FastAPI resolves this name from the module's globals.
Me = Annotated[Principal, Depends(current_principal)]


def create_app(settings: Settings | None = None, assistant: Assistant | None = None,
               superset: SupersetClient | None = None, records: CaseRecords | None = None,
               auth: Auth | None = None) -> FastAPI:
    settings = settings or get_settings()
    if assistant is None:
        model = CaseModel(settings.csv_dir, settings.today, catalogue=settings.catalogue_path)  # the date as it moves on
        assistant = Assistant(settings, model, DocumentIndex(settings.index_path, readonly=True))
    if superset is None and (superset_settings := SupersetSettings.from_env()) is not None:
        superset = SupersetClient(superset_settings)
    if records is None:  # case changes, evidence, follow-ups, notifications and the audit trail, over the same model
        records = CaseRecords(settings, assistant.model, mailer=Mailer.from_env())
    auth = auth or Auth(settings, assistant.model)
    if not auth.configured:
        log.warning("Nobody can sign in yet: set FERRERO_DEMO_PASSWORD, or `python -m ferrero.auth set-password <user>`")

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        """Checks deadlines at start and every FERRERO_REMINDER_MINUTES (and e-mails reminders when configured)."""
        stop = threading.Event()

        def check() -> None:
            while True:
                try:
                    records.run_reminders()
                    records.deliver_email()
                except Exception:  # a failed check is retried at the next one
                    log.exception("Deadline check failed")
                if settings.reminder_minutes <= 0 or stop.wait(settings.reminder_minutes * 60):
                    return

        threading.Thread(target=check, name="ferrero-reminders", daemon=True).start()
        try:
            yield
        finally:
            stop.set()

    app = FastAPI(title="Ferrero case intelligence", docs_url="/api/docs", redoc_url=None, lifespan=lifespan)
    app.state.assistant, app.state.records, app.state.auth = assistant, records, auth

    @app.exception_handler(RecordError)
    async def record_error(_: Request, e: RecordError) -> JSONResponse:
        return JSONResponse({"detail": e.message, "code": e.code}, status_code=e.status)

    @app.exception_handler(AuthError)
    async def auth_error(_: Request, e: AuthError) -> JSONResponse:
        return JSONResponse({"detail": e.message, "code": e.code}, status_code=e.status)

    @app.middleware("http")
    async def require_app_header(request: Request, call_next):
        """Changes need the X-Ferrero header: browsers only let this app's own pages add it."""
        if (request.method not in ("GET", "HEAD", "OPTIONS") and request.url.path.startswith("/api/")
                and request.headers.get(CSRF_HEADER) != "1"):
            return JSONResponse({"detail": "This request didn't come from the Ferrero app.", "code": "csrf"},
                                status_code=403)
        return await call_next(request)

    # every country in the case data, for the dashboards' row rules (listed positively, so unknown ones stay hidden)
    countries = sorted({r["country"] for t in assistant.model.tables.values() for r in t.dicts() if r.get("country")})

    def secure_cookie(request: Request) -> bool:
        if settings.cookie_secure != "auto":
            return settings.cookie_secure == "true"
        return request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "").lower() == "https"

    def me_payload(p: Principal) -> dict[str, Any]:
        user = next((u for u in assistant.model.users() if u["user_id"] == p.user_id), {"user_id": p.user_id})
        return {**user, **auth.profile(p)}

    # ---------- signing in ----------
    @app.get("/api/public")
    def public() -> dict[str, Any]:
        """What the landing and sign-in pages need before anyone signs in."""
        return {"org_name": settings.org_name, "sign_in_configured": auth.configured,
                "accounts": auth.public_accounts() if settings.login_show_accounts else None}

    @app.post("/api/auth/login")
    def sign_in(body: SignIn, request: Request, response: Response) -> dict[str, Any]:
        token, p, max_age = auth.login(body.login, body.password, ip=request.client.host if request.client else None,
                                       user_agent=request.headers.get("user-agent"), remember=body.remember)
        response.set_cookie(COOKIE, token, max_age=max_age, path="/", httponly=True, samesite="lax",
                            secure=secure_cookie(request))
        return {"user": me_payload(p)}

    @app.post("/api/auth/logout")
    def sign_out(request: Request, response: Response) -> dict[str, bool]:
        auth.logout(request.cookies.get(COOKIE))
        response.delete_cookie(COOKIE, path="/", httponly=True, samesite="lax", secure=secure_cookie(request))
        return {"signed_out": True}

    @app.get("/api/auth/me")
    def me(request: Request) -> dict[str, Any]:
        """Who is signed in: the user, or null (not an error: the landing page asks before anyone signs in)."""
        p = auth.session(request.cookies.get(COOKIE))
        return {"user": me_payload(p) if p else None}

    @app.post("/api/auth/password")
    def change_password(body: PasswordChange, request: Request, p: Me) -> dict[str, bool]:
        auth.change_password(p, body.current_password, body.new_password, keep_token=request.cookies.get(COOKIE))
        return {"changed": True}

    # ---------- the platform administrator: users, and switching into another user's view ----------
    @app.get("/api/admin/users")
    def admin_users(p: Me) -> dict[str, Any]:
        return auth.list_users(p)

    @app.post("/api/admin/users")
    def admin_add_user(body: NewUser, p: Me) -> dict[str, Any]:
        return auth.add_user(p, body.model_dump())

    @app.patch("/api/admin/users/{user_id}")
    def admin_update_user(user_id: str, body: UserChanges, p: Me) -> dict[str, Any]:
        return auth.update_user(p, user_id, body.changes)

    @app.post("/api/admin/users/{user_id}/password")
    def admin_set_password(user_id: str, body: TemporaryPassword, p: Me) -> dict[str, Any]:
        return auth.set_temporary_password(p, user_id, body.password)

    @app.post("/api/admin/switch")
    def admin_switch(body: SwitchTo, request: Request, _: Me) -> dict[str, Any]:
        """The administrator's session acts as another user until switched back; their changes name both."""
        return {"user": me_payload(auth.switch(request.cookies.get(COOKIE), body.user_id))}

    @app.post("/api/admin/switch/back")
    def admin_switch_back(request: Request, _: Me) -> dict[str, Any]:  # Me: a live session, whoever it acts as
        return {"user": me_payload(auth.switch_back(request.cookies.get(COOKIE)))}

    # ---------- reference data ----------
    @app.get("/api/meta")
    def meta(_: Me) -> dict[str, Any]:
        return {"model": settings.model, "effort": settings.effort, "provider": settings.provider,
                # "demo_today": the date the app works to (the real date, unless FERRERO_DEMO_TODAY fixes one)
                "demo_today": assistant.model.today.isoformat(), "today_fixed": settings.demo_today is not None,
                "org_name": settings.org_name,
                "index": assistant.index.stats(), "examples": EXAMPLES, "dashboards": views.superset_dashboards(),
                "embedded_dashboards": superset is not None, "case_options": case_options(settings),
                "email_notifications": records.mailer is not None}

    @app.get("/api/users")
    def users(_: Me) -> list[dict[str, Any]]:
        return assistant.model.users()

    @app.get("/api/dashboards")
    def dashboards(_: Me) -> dict[str, Any]:
        """The Superset dashboards this app can embed (or plain links from FERRERO_SUPERSET_DASHBOARDS)."""
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
    def dashboard_token(body: GuestTokenRequest, p: Me) -> dict[str, str]:
        """A short-lived token for one embedded dashboard, limited to the rows the signed-in user may see."""
        if superset is None:
            raise HTTPException(404, "Dashboards are not connected")
        case_id = body.case_id.upper() if body.case_id else None
        if case_id and assistant.model.visible_case(p, case_id) is None:
            raise HTTPException(404, f"Case {case_id} is not available to this user")
        visible = [r["case_id"] for r in assistant.model.tables["fact_case"].dicts() if p.sees_group(r["access_group"])]
        try:
            token = superset.guest_token(p, body.dashboard, countries, visible, case_id)
        except SupersetError as e:
            log.warning("Dashboard token for %s failed: %s", p.user_id, e)
            raise HTTPException(e.status, e.public) from None
        return {"token": token}

    # ---------- cases ----------
    @app.get("/api/overview")
    def overview(p: Me, country: str | None = None, mark: str | None = None) -> dict[str, Any]:
        return views.overview(assistant.model, p, country=country or None, mark=mark or None)

    @app.get("/api/cases")
    def cases(p: Me) -> list[dict[str, Any]]:
        return views.case_list(assistant.model, p)

    def case_page(p: Principal, case_id: str) -> dict[str, Any]:
        found = case_detail(assistant.model, assistant.index, p, case_id.upper())
        if found is None:
            raise HTTPException(404, f"Case {case_id} is not available to this user")
        found["permissions"] = {"edit": p.can_edit, "evidence": p.sees_documents, "add_evidence": p.can_edit and p.sees_documents}
        found["counts"] = records.counts(p, found["case_id"])
        found["registered_in_app"] = not assistant.model.in_pack(found["case_id"])
        return found

    @app.get("/api/cases/{case_id}")
    def case(case_id: str, p: Me) -> dict[str, Any]:
        return case_page(p, case_id)

    @app.get("/api/register/options")
    def register_options(p: Me) -> dict[str, Any]:
        """The choices the case registration form offers this user (their countries, marks, infringers, courts)."""
        return records.register_options(p)

    @app.post("/api/cases")
    def register_case(body: NewCase, p: Me) -> dict[str, Any]:
        """Register a new case; it starts at Intake with an owner, and the registration opens its audit trail."""
        found = records.register_case(p, body.model_dump())
        return {**found, "case": case_page(p, found["case_id"])}

    # ---------- registered marks and the visual trademark comparison ----------
    def has_specimen(mark_id: str) -> bool:
        return (MARKS / f"{mark_id}.png").is_file()

    @app.get("/api/marks")
    def marks(_: Me) -> list[dict[str, Any]]:
        return [records.mark_info(m, has_specimen(m["mark_id"])) for m in assistant.model.marks()]

    @app.get("/api/marks/{mark_id}/specimen")
    def mark_specimen(mark_id: Annotated[str, FastAPIPath(pattern=MARK_ID)], _: Me) -> FileResponse:
        """The mark as registered (its specimen), shown beside the infringing product."""
        if not has_specimen(mark_id):
            raise HTTPException(404, "No specimen on file for this mark")
        return FileResponse(MARKS / f"{mark_id}.png", media_type="image/png",
                            headers={"Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff"})

    @app.get("/api/marks/{mark_id}/similarity")
    def mark_similarity(mark_id: Annotated[str, FastAPIPath(pattern=MARK_ID)], _: Me,
                        sign: str = Query("", max_length=240)) -> dict[str, Any]:
        """Indicative similarity between the mark and a sign, as the assessor types it."""
        return records.similarity(mark_id, sign)

    @app.get("/api/cases/{case_id}/comparison")
    def case_comparison(case_id: str, p: Me) -> dict[str, Any]:
        return records.comparison(p, case_id, has_specimen)

    @app.post("/api/cases/{case_id}/comparison")
    def record_comparison(case_id: str, body: Comparison, p: Me) -> dict[str, Any]:
        """Record an assessment of the registered mark against the sign on the product (it goes in the audit trail)."""
        return records.record_comparison(p, case_id, body.model_dump(), has_specimen)

    @app.patch("/api/cases/{case_id}")
    def update_case(case_id: str, body: CaseChange, p: Me) -> dict[str, Any]:
        """Change case fields (status, next steps, owner, business assessment); every change goes in the audit trail."""
        changes = records.update_case(p, case_id, body.changes, body.reason, body.override_reason)
        return {"changes": changes, "case": case_page(p, case_id)}

    @app.get("/api/cases/{case_id}/audit")
    def case_audit(case_id: str, p: Me) -> dict[str, Any]:
        return records.audit(p, case_id)

    @app.get("/api/cases/{case_id}/audit.csv")
    def case_audit_csv(case_id: str, p: Me) -> Response:
        text = records.audit_csv(p, case_id)  # 404 unless the case is visible, so the id is valid
        return Response("﻿" + text, media_type="text/csv",  # BOM: Excel opens it as UTF-8 (Arabic names)
                        headers={"Content-Disposition": f'attachment; filename="{case_id.upper()}_audit_trail.csv"'})

    # ---------- evidence and supporting documents ----------
    @app.get("/api/cases/{case_id}/evidence")
    def case_evidence(case_id: str, p: Me) -> list[dict[str, Any]]:
        return records.list_evidence(p, case_id)

    @app.post("/api/cases/{case_id}/evidence")
    async def add_evidence(case_id: str, request: Request, p: Me,
                           file_name: str = Query(min_length=1, max_length=400), category: str = Query(max_length=80),
                           title: str | None = Query(None, max_length=400), captured_on: str | None = Query(None, max_length=10),
                           location: str | None = Query(None, max_length=600),
                           notes: str | None = Query(None, max_length=4000)) -> dict[str, Any]:
        """One file as the request body (any content type); its details in the query string."""
        await run_in_threadpool(records.check_can_add_evidence, p, case_id)  # before reading the body
        limit = settings.evidence_max_mb * 1024 * 1024
        too_large = RecordError(f"The file is larger than {settings.evidence_max_mb} MB.", 413, "too_large")
        declared = request.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > limit:
            raise too_large
        with tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024) as spool:
            size = 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > limit:
                    raise too_large
                spool.write(chunk)
            spool.seek(0)
            details = {"category": category, "title": title, "captured_on": captured_on, "location": location, "notes": notes}
            return await run_in_threadpool(records.add_evidence, p, case_id, spool, file_name, details)

    @app.patch("/api/evidence/{evidence_id}")
    def update_evidence(evidence_id: str, body: Changes, p: Me) -> dict[str, Any]:
        return records.update_evidence(p, evidence_id, body.changes, body.reason)

    @app.post("/api/evidence/{evidence_id}/withdraw")
    def withdraw_evidence(evidence_id: str, body: Withdrawal, p: Me) -> dict[str, Any]:
        return records.withdraw_evidence(p, evidence_id, body.reason)

    @app.get("/api/evidence/{evidence_id}/verify")
    def verify_evidence(evidence_id: str, p: Me) -> dict[str, Any]:
        return records.verify_evidence(p, evidence_id)

    @app.get("/api/evidence/{evidence_id}/file")
    def evidence_file(evidence_id: str, p: Me, download: bool = False) -> FileResponse:
        """The file exactly as uploaded. Photos and PDFs open in the browser; everything else downloads."""
        path, kind, name = records.evidence_file(p, evidence_id)
        headers = {"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=86400"}
        if kind.content_type != "application/pdf":  # nothing an upload contains may run in the app's origin
            headers["Content-Security-Policy"] = "sandbox"
        return FileResponse(path, media_type=kind.content_type, filename=name, headers=headers,
                            content_disposition_type="inline" if kind.inline and not download else "attachment")

    # ---------- follow-ups and notifications ----------
    @app.get("/api/cases/{case_id}/follow-ups")
    def case_follow_ups(case_id: str, p: Me) -> list[dict[str, Any]]:
        return records.list_follow_ups(p, case_id)

    @app.post("/api/cases/{case_id}/follow-ups")
    def new_follow_up(case_id: str, body: NewFollowUp, p: Me) -> dict[str, Any]:
        return records.create_follow_up(p, case_id, body.model_dump())

    @app.patch("/api/follow-ups/{follow_up_id}")
    def update_follow_up(follow_up_id: str, body: Changes, p: Me) -> dict[str, Any]:
        return records.update_follow_up(p, follow_up_id, body.changes, body.reason)

    @app.post("/api/follow-ups/{follow_up_id}/resolve")
    def resolve_follow_up(follow_up_id: str, body: FollowUpDecision, p: Me) -> dict[str, Any]:
        return records.resolve_follow_up(p, follow_up_id, body.model_dump())

    @app.get("/api/follow-ups")
    def worklist(p: Me) -> dict[str, Any]:
        return records.worklist(p)

    @app.get("/api/notifications")
    def notifications(p: Me, limit: int = Query(30, ge=1, le=100)) -> dict[str, Any]:
        return records.notifications(p, limit)

    @app.post("/api/notifications/read")
    def notifications_read(body: ReadMark, p: Me) -> dict[str, int]:
        return {"marked": records.mark_read(p, body.ids)}

    # ---------- documents ----------
    @app.get("/api/sync")
    def sync_status(p: Me) -> dict[str, Any]:
        return views.documents(assistant.index, p)

    ocr_cache = OcrCache(settings.ocr_dir)

    @app.get("/api/documents/{name}")
    def document(name: str, p: Me) -> dict[str, Any]:
        """One synced document: its searchable text and, for scans, its page images and recognition confidence."""
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
    def document_page(name: str, number: int, p: Me) -> Response:
        """A scanned page as stored in the scan, for checking the recognised text against it."""
        meta_ = assistant.index.document_meta(p, name)
        found = ocr_cache.page_image(meta_["content_sha"], number) if meta_ and meta_["content_sha"] and number >= 1 else None
        if found is None:
            raise HTTPException(404, "Page not available")
        data, media_type = found
        return Response(data, media_type=media_type, headers={"Cache-Control": "private, max-age=3600"})

    # ---------- the assistant ----------
    @app.post("/api/conversations")
    def new_conversation(body: NewConversation, p: Me) -> dict[str, Any]:
        try:
            conv = assistant.start(p.user_id, body.case_id)
        except AssistantError as e:
            raise HTTPException(404, e.public) from None
        return {
            "conversation_id": conv.id,
            "user": {"user_id": p.user_id, "full_name": p.full_name, "job_title": p.job_title,
                     "entra_group": p.entra_group, "access": p.role.description, "documents": p.sees_documents},
            "case": {k: conv.case_focus[k] for k in CASE_FIELDS} if conv.case_focus else None,
            "case_requested": body.case_id.upper() if body.case_id else None,
        }

    @app.post("/api/conversations/{conversation_id}/messages")
    def send(conversation_id: str, body: NewMessage, p: Me) -> StreamingResponse:
        conv = assistant.conversations.get(conversation_id)
        if conv is None or conv.principal.user_id != p.user_id:  # a conversation belongs to whoever started it
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

    # ---------- pages ----------
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/classic", include_in_schema=False)
    def classic() -> RedirectResponse:
        return RedirectResponse("/assistant")  # the old single-file chat predates sign-in; the Assistant page replaces it

    if (DIST / "index.html").is_file():
        app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            if path.startswith("api/"):
                raise HTTPException(404, "Not found")
            candidate = (DIST / path).resolve()
            if path and candidate.is_file() and DIST.resolve() in candidate.parents:
                return FileResponse(candidate)  # favicon and other root-level build files
            # Client-side routes: /, /login, /cases/TM-2024-428, … The page names the build's script and stylesheet, so
            # browsers must check it on every visit, or they keep showing the previous build after an update.
            return FileResponse(DIST / "index.html", headers={"Cache-Control": "no-cache"})
    else:
        @app.get("/", include_in_schema=False)
        def index() -> FileResponse:
            return FileResponse(STATIC / "index.html")

    return app
