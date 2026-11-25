"""Apache Superset dashboards inside Ferrero, through Superset's embedded SDK and guest tokens.

Configure FERRERO_SUPERSET_URL, FERRERO_SUPERSET_USERNAME and FERRERO_SUPERSET_PASSWORD (a Superset account
that may grant guest tokens, such as an Admin). Ferrero then finds the dashboards whose title contains
FERRERO_SUPERSET_TITLE (default "Ferrero"), turns on embedding for any that lack it (unless
FERRERO_SUPERSET_AUTO_EMBED=false), and gives the browser one guest token per dashboard.

Each token carries row-level rules built from the signed-in user's role, so a dashboard shows the same rows
as every other page of Ferrero: datasets with a country column are limited to the countries the user may
see, datasets with only a case_id to the user's cases, and document datasets are empty for roles without
documents. The browser never signs in to Superset and never sees the service account.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Iterable

import httpx

from ..security import CASE_GROUPS, Principal

log = logging.getLogger(__name__)

DISCOVERY_TTL = 120.0    # seconds a dashboard list is reused before Superset is asked again
CSP_TTL = 300.0
TIMEOUT = httpx.Timeout(20.0, connect=5.0)
_HYPHENS = re.compile("[‐-―−­]")    # Superset titles may use non-breaking or typographic hyphens
_CODE = re.compile(r"\b(DS-?\d+|D\d+)\b", re.IGNORECASE)
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SEPARATORS = r"[\s·:|\-–—]*"


class SupersetError(Exception):
    """A failure the Dashboards page can explain in plain language; the detail goes to the log."""

    def __init__(self, public: str, detail: str = "", status: int = 502):
        super().__init__(detail or public)
        self.public = public
        self.status = status


@dataclass(frozen=True)
class SupersetSettings:
    url: str
    username: str
    password: str
    provider: str = "db"
    title_filter: str = "Ferrero"
    auto_embed: bool = True
    allowed_domains: tuple[str, ...] = ()

    @classmethod
    def from_env(cls, env=os.environ.get) -> SupersetSettings | None:
        url = (env("FERRERO_SUPERSET_URL") or "").strip().rstrip("/")
        username, password = env("FERRERO_SUPERSET_USERNAME") or "", env("FERRERO_SUPERSET_PASSWORD") or ""
        if not (url and username and password):
            return None
        domains = (env("FERRERO_SUPERSET_ALLOWED_DOMAINS") or "").split(",")
        return cls(
            url=url, username=username, password=password,
            provider=(env("FERRERO_SUPERSET_AUTH_PROVIDER") or "db").strip().lower(),
            title_filter=(env("FERRERO_SUPERSET_TITLE") or "Ferrero").strip(),
            auto_embed=(env("FERRERO_SUPERSET_AUTO_EMBED") or "true").strip().lower() not in ("0", "false", "no", "off"),
            allowed_domains=tuple(d.strip().rstrip("/") for d in domains if d.strip()),
        )


@dataclass(frozen=True)
class Dataset:
    id: int
    name: str
    columns: tuple[str, ...]


@dataclass(frozen=True)
class Dashboard:
    id: int
    full_title: str
    code: str | None
    title: str
    uuid: str | None
    allowed_domains: tuple[str, ...]
    url: str
    datasets: tuple[Dataset, ...] = field(default=())

    def public(self) -> dict[str, Any]:
        return {"code": self.code, "title": self.title, "full_title": self.full_title, "uuid": self.uuid,
                "url": self.url, "allowed_domains": list(self.allowed_domains)}


# ---------- titles ----------
def dashboard_code(title: str) -> str | None:
    """'Ferrero · D1 Legal Case Overview' -> 'D1'; 'Ferrero · DS‑1 Case Detail' -> 'DS-1'."""
    m = _CODE.search(_HYPHENS.sub("-", title))
    if not m:
        return None
    return re.sub(r"^DS(\d)", r"DS-\1", m.group(1).upper())


def short_title(title: str, code: str | None, prefix: str) -> str:
    """'Ferrero · D1 Legal Case Overview' -> 'Legal Case Overview'."""
    t = _HYPHENS.sub("-", title).strip()
    if prefix:
        t = re.sub(rf"^{re.escape(prefix)}{_SEPARATORS}", "", t, flags=re.IGNORECASE)
    if code:
        t = re.sub(rf"^{re.escape(code).replace('-', '-?')}\b{_SEPARATORS}", "", t, flags=re.IGNORECASE)
    return t.strip() or title


def _order(d: Dashboard) -> tuple[int, int, str]:
    """D1…D4 first, then the drill-throughs DS-1…, then anything else by title."""
    if d.code and d.code.startswith("DS-"):
        return 1, int(d.code[3:]), d.title
    if d.code:
        return 0, int(d.code[1:]), d.title
    return 2, 0, d.title


# ---------- row-level rules ----------
def _quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _column(columns: Iterable[str], name: str) -> str | None:
    """The dataset's own spelling of a column, quoted when it is not a plain identifier."""
    for c in columns:
        if c.lower() == name:
            return c if _IDENTIFIER.match(c) else '"' + c.replace('"', '""') + '"'
    return None


def row_rules(principal: Principal, datasets: Iterable[Dataset], countries: Iterable[str],
              visible_cases: Iterable[str], case_id: str | None = None) -> list[dict[str, Any]]:
    """Superset guest-token RLS rules that give this principal the rows it sees elsewhere in Ferrero.

    Countries are listed positively, so a country nobody configured stays hidden (fail closed)."""
    sees_all = principal.role.case_groups >= frozenset(CASE_GROUPS)
    allowed = sorted({c for c in countries if c and principal.sees_country(c)})
    cases = sorted(set(visible_cases))
    rules: list[dict[str, Any]] = []
    for ds in datasets:
        country_col, case_col = _column(ds.columns, "country"), _column(ds.columns, "case_id")
        if not sees_all:
            if country_col:
                clause = f"{country_col} IN ({', '.join(map(_quote, allowed))})" if allowed else "1 = 0"
                rules.append({"dataset": ds.id, "clause": clause})
            elif case_col:
                clause = f"{case_col} IN ({', '.join(map(_quote, cases))})" if cases else "1 = 0"
                rules.append({"dataset": ds.id, "clause": clause})
        if not principal.sees_documents and "document" in ds.name.lower():
            rules.append({"dataset": ds.id, "clause": "1 = 0"})
        if case_id and case_col:
            rules.append({"dataset": ds.id, "clause": f"{case_col} = {_quote(case_id)}"})
    return rules


def _jwt_expiry(token: str) -> float:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return float(json.loads(base64.urlsafe_b64decode(payload))["exp"])
    except Exception:  # not a JWT we can read: treat it as good for a few minutes
        return time.time() + 240


def _rison_text(text: str) -> str:
    return "'" + text.replace("!", "!!").replace("'", "!'") + "'"


def frame_ancestors(headers: httpx.Headers) -> list[str] | None:
    """Who may put Superset in a frame, from its security headers; None when it sets no limit."""
    m = re.search(r"frame-ancestors\s+([^;]+)", headers.get("content-security-policy", ""), re.IGNORECASE)
    if m:
        return m.group(1).split()
    if headers.get("x-frame-options", "").upper() in ("DENY", "SAMEORIGIN"):
        return ["'self'"]
    return None


# ---------- client ----------
class SupersetClient:
    def __init__(self, settings: SupersetSettings, transport: httpx.BaseTransport | None = None):
        self.settings = settings
        self._transport = transport
        self._token: str | None = None
        self._token_expires = 0.0
        self._lock = threading.Lock()
        self._dashboards: tuple[float, list[Dashboard]] | None = None
        self._ancestors: tuple[float, list[str] | None] | None = None

    def _http(self) -> httpx.Client:
        return httpx.Client(base_url=self.settings.url, timeout=TIMEOUT, transport=self._transport)

    def _login(self, http: httpx.Client) -> str:
        s = self.settings
        try:
            r = http.post("/api/v1/security/login",
                          json={"username": s.username, "password": s.password, "provider": s.provider, "refresh": False})
        except httpx.HTTPError as e:
            raise SupersetError("The dashboards can't be reached right now.", f"login failed: {e!r}") from None
        if r.status_code == 401:
            raise SupersetError("The dashboard server rejected Ferrero's sign-in.", "login answered 401: check "
                                "FERRERO_SUPERSET_USERNAME, FERRERO_SUPERSET_PASSWORD and FERRERO_SUPERSET_AUTH_PROVIDER")
        if r.status_code != 200:
            raise SupersetError("The dashboards can't be reached right now.", f"login answered {r.status_code}: {r.text[:200]}")
        token = r.json()["access_token"]
        self._token_expires = _jwt_expiry(token) - 30
        return token

    def _bearer(self, http: httpx.Client, fresh: bool = False) -> dict[str, str]:
        with self._lock:
            if fresh or self._token is None or time.time() >= self._token_expires:
                self._token = self._login(http)
            return {"Authorization": f"Bearer {self._token}"}

    def _get(self, http: httpx.Client, path: str, params: dict[str, str] | None = None) -> httpx.Response:
        try:
            r = http.get(path, params=params, headers=self._bearer(http))
            if r.status_code == 401:
                r = http.get(path, params=params, headers=self._bearer(http, fresh=True))
        except httpx.HTTPError as e:
            raise SupersetError("The dashboards can't be reached right now.", f"GET {path} failed: {e!r}") from None
        return r

    def _post(self, http: httpx.Client, path: str, body: dict[str, Any]) -> httpx.Response:
        """A POST with a CSRF token. Superset ties the token to the session cookie, so both stay on one client."""
        try:
            for attempt in range(2):
                headers = self._bearer(http, fresh=attempt > 0)
                csrf = http.get("/api/v1/security/csrf_token/", headers=headers)
                if csrf.status_code == 401:
                    continue
                if csrf.status_code != 200:
                    raise SupersetError("The dashboards can't be reached right now.",
                                        f"csrf_token answered {csrf.status_code}: {csrf.text[:200]}")
                r = http.post(path, json=body, headers={**headers, "X-CSRFToken": csrf.json()["result"],
                                                        "Referer": self.settings.url + "/"})
                if r.status_code != 401:
                    return r
        except httpx.HTTPError as e:
            raise SupersetError("The dashboards can't be reached right now.", f"POST {path} failed: {e!r}") from None
        raise SupersetError("The dashboard server stopped accepting Ferrero's sign-in.", f"POST {path} answered 401")

    # ---------- discovery ----------
    def dashboards(self, refresh: bool = False) -> list[Dashboard]:
        cached = self._dashboards
        if cached and not refresh and time.time() - cached[0] < DISCOVERY_TTL:
            return cached[1]
        s = self.settings
        query = (f"(filters:!((col:dashboard_title,opr:ct,value:{_rison_text(s.title_filter)})),"
                 "order_column:dashboard_title,order_direction:asc,page:0,page_size:100)")
        found: list[Dashboard] = []
        with self._http() as http:
            r = self._get(http, "/api/v1/dashboard/", {"q": query})
            if r.status_code != 200:
                raise SupersetError("The dashboards can't be listed right now.", f"dashboard list answered {r.status_code}: {r.text[:200]}")
            for row in r.json().get("result", []):
                found.append(self._describe(http, row))
        found.sort(key=_order)
        self._dashboards = (time.time(), found)
        return found

    def _describe(self, http: httpx.Client, row: dict[str, Any]) -> Dashboard:
        s = self.settings
        did, title = int(row["id"]), str(row.get("dashboard_title") or row["id"])
        embedded: dict[str, Any] | None = None
        r = self._get(http, f"/api/v1/dashboard/{did}/embedded")
        if r.status_code == 200:
            embedded = r.json().get("result")
        elif r.status_code == 404 and s.auto_embed:
            created = self._post(http, f"/api/v1/dashboard/{did}/embedded", {"allowed_domains": list(s.allowed_domains)})
            if created.status_code in (200, 201):
                embedded = created.json().get("result")
                log.info("Turned on embedding for dashboard %s (%s)", did, title)
            else:
                log.warning("Could not turn on embedding for dashboard %s (%s): %s %s", did, title,
                            created.status_code, created.text[:200])
        else:
            log.warning("Embedding settings for dashboard %s (%s) answered %s", did, title, r.status_code)
        datasets: list[Dataset] = []
        d = self._get(http, f"/api/v1/dashboard/{did}/datasets")
        if d.status_code == 200:
            for x in d.json().get("result", []):
                cols = tuple(c["column_name"] for c in x.get("columns") or [] if c.get("column_name"))
                datasets.append(Dataset(int(x["id"]), str(x.get("table_name") or x.get("datasource_name") or ""), cols))
        else:
            log.warning("Datasets of dashboard %s answered %s; row rules cannot be applied to it", did, d.status_code)
        code = dashboard_code(title)
        link = row.get("url") or f"/superset/dashboard/{row.get('slug') or did}/"
        return Dashboard(did, title, code, short_title(title, code, s.title_filter),
                         (embedded or {}).get("uuid"), tuple((embedded or {}).get("allowed_domains") or ()),
                         s.url + link if link.startswith("/") else link, tuple(datasets))

    def frame_ancestors(self) -> list[str] | None:
        cached = self._ancestors
        if cached and time.time() - cached[0] < CSP_TTL:
            return cached[1]
        try:
            with self._http() as http:
                value = frame_ancestors(http.get("/login/").headers)
        except httpx.HTTPError:
            value = None
        self._ancestors = (time.time(), value)
        return value

    # ---------- guest tokens ----------
    def guest_token(self, principal: Principal, uuid: str, countries: Iterable[str], visible_cases: Iterable[str],
                    case_id: str | None = None) -> str:
        dash = next((d for d in self.dashboards() if d.uuid == uuid), None) \
            or next((d for d in self.dashboards(refresh=True) if d.uuid == uuid), None)
        if dash is None:
            raise SupersetError("This dashboard is not available.", f"no dashboard with embed id {uuid}", status=404)
        restricted = not principal.role.case_groups >= frozenset(CASE_GROUPS) or not principal.sees_documents
        if restricted and not dash.datasets:
            # Without the dataset list no row rules can be built, and an unfiltered token would show every row.
            raise SupersetError("This dashboard can't be shown for your role right now.",
                                f"no datasets known for dashboard {dash.id}; refusing an unfiltered token for {principal.user_id}",
                                status=503)
        first, _, last = principal.full_name.partition(" ")
        body = {
            "user": {"username": principal.user_id, "first_name": first or principal.user_id, "last_name": last},
            "resources": [{"type": "dashboard", "id": uuid}],
            "rls": row_rules(principal, dash.datasets, countries, visible_cases, case_id),
        }
        with self._http() as http:
            r = self._post(http, "/api/v1/security/guest_token/", body)
        if r.status_code == 403:
            raise SupersetError("Ferrero isn't allowed to open this dashboard.",
                                "guest_token answered 403: the Ferrero account needs 'can grant guest token on SecurityRestApi'")
        if r.status_code != 200:
            raise SupersetError("This dashboard can't be opened right now.", f"guest_token answered {r.status_code}: {r.text[:300]}")
        return r.json()["token"]


# ---------- connection check: python -m ferrero.web.superset ----------
def check(persona: str = "U-05") -> int:
    """Signs in, lists the dashboards (turning embedding on where needed), checks framing and issues one guest token."""
    from ..casemodel import CaseModel
    from ..config import get_settings

    settings = get_settings()  # also loads .env
    cfg = SupersetSettings.from_env()
    if cfg is None:
        print("NOT CONFIGURED  set FERRERO_SUPERSET_URL, FERRERO_SUPERSET_USERNAME and FERRERO_SUPERSET_PASSWORD in .env")
        return 2
    print(f"Superset        {cfg.url}")
    client = SupersetClient(cfg)
    try:
        dashboards = client.dashboards(refresh=True)
    except SupersetError as e:
        print(f"FAILED          {e.public}\n                {e}")
        return 1
    print(f"OK  sign-in     as {cfg.username}")
    print(f"OK  dashboards  {len(dashboards)} with '{cfg.title_filter}' in the title")
    for d in dashboards:
        state = f"embed id {d.uuid}" if d.uuid else "NOT EMBEDDABLE (turn on 'Embed dashboard' in Superset)"
        print(f"      {d.code or '-':5} {d.title[:38]:38} {state}, {len(d.datasets)} datasets")
    origin = f"http://localhost:{os.environ.get('FERRERO_PORT') or '8000'}"
    ancestors = client.frame_ancestors()
    if ancestors is None or "*" in ancestors or origin in ancestors:
        print(f"OK  framing     Superset allows embedding from {origin}")
    else:
        print(f"WARNING         Superset allows embedding only from {' '.join(ancestors)}; Ferrero at {origin} is not "
              "on that list (set FERRERO_PORT to match, or add the address to Superset's frame-ancestors)")
    embeddable = [d for d in dashboards if d.uuid]
    if not embeddable:
        print("FAILED          no dashboard can be embedded")
        return 1
    model = CaseModel(settings.csv_dir, settings.today, catalogue=settings.catalogue_path)
    p = model.principal(persona)
    if p is None:
        print(f"FAILED          unknown persona {persona}")
        return 1
    countries = sorted({r["country"] for t in model.tables.values() for r in t.dicts() if r.get("country")})
    visible = [r["case_id"] for r in model.tables["fact_case"].dicts() if p.sees_group(r["access_group"])]
    target = embeddable[0]
    try:
        client.guest_token(p, target.uuid, countries, visible)
    except SupersetError as e:
        print(f"FAILED          guest token: {e.public}\n                {e}")
        return 1
    rules = row_rules(p, target.datasets, countries, visible)
    print(f"OK  guest token for {p.full_name} ({p.entra_group}) on {target.code or target.title}, with {len(rules)} row rules")
    print(f"Ready. Run start.cmd and open {origin}/dashboards")
    return 0


if __name__ == "__main__":
    raise SystemExit(check())
