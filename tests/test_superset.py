"""Embedded Superset dashboards: discovery, embedding, guest tokens and the row rules that mirror Ferrero's access."""
from __future__ import annotations

import base64
import json
import time

import httpx
from fastapi.testclient import TestClient

from ferrero.assistant.agent import Assistant
from ferrero.web.app import create_app
from ferrero.web.superset import (
    Dataset, SupersetClient, SupersetSettings, dashboard_code, frame_ancestors, row_rules, short_title,
)

SETTINGS = SupersetSettings(url="http://superset.test:8088", username="ferrero-svc", password="pw")
TITLES = {1: "Ferrero · D4 Infringer & Enforcement Outcomes", 2: "Ferrero · DS‑1 Case Detail",
          3: "Ferrero · D3 Infringement Intake & Triage", 4: "Ferrero · D2 Leadership Command View",
          5: "Ferrero · D1 Legal Case Overview"}
DATASETS = [
    {"id": 11, "table_name": "fact_case", "columns": [{"column_name": "case_id"}, {"column_name": "country"}]},
    {"id": 12, "table_name": "fact_invoice", "columns": [{"column_name": "case_id"}, {"column_name": "amount_aed"}]},
    {"id": 13, "table_name": "fact_document", "columns": [{"column_name": "case_id"}, {"column_name": "doc_type"}]},
    {"id": 14, "table_name": "dim_mark", "columns": [{"column_name": "mark_name"}]},
]


def _jwt(seconds: int = 900) -> str:
    def part(obj):
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")
    return f"{part({'alg': 'HS256'})}.{part({'exp': int(time.time()) + seconds})}.sig"


class FakeSuperset:
    """Just enough of Superset's REST API, recording what Ferrero sends."""

    def __init__(self, embedded: set[int] | None = None):
        self.embedded = {i: f"0000000{i}-aaaa-bbbb-cccc-00000000000{i}" for i in (embedded or {1, 3, 4, 5})}
        self.logins = 0
        self.created: list[tuple[int, dict]] = []
        self.guest_requests: list[dict] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path, method = request.url.path, request.method
        if path == "/api/v1/security/login":
            self.logins += 1
            body = json.loads(request.content)
            ok = body["username"] == "ferrero-svc" and body["password"] == "pw"
            return httpx.Response(200, json={"access_token": _jwt()}) if ok else httpx.Response(401, json={"message": "no"})
        if path == "/login/":
            return httpx.Response(200, text="<html></html>", headers={
                "Content-Security-Policy": "default-src 'self'; frame-ancestors 'self' http://localhost:8090"})
        if not request.headers.get("authorization", "").startswith("Bearer "):
            return httpx.Response(401)
        if path == "/api/v1/security/csrf_token/":
            return httpx.Response(200, json={"result": "csrf-1"}, headers={"set-cookie": "session=s1; Path=/"})
        if path == "/api/v1/dashboard/" and method == "GET":
            assert "dashboard_title" in request.url.params["q"] and "Ferrero" in request.url.params["q"]
            return httpx.Response(200, json={"count": 5, "result": [
                {"id": i, "dashboard_title": t, "url": f"/superset/dashboard/{i}/", "slug": None} for i, t in TITLES.items()]})
        if path.endswith("/embedded"):
            did = int(path.split("/")[4])
            if method == "POST":
                assert request.headers.get("x-csrftoken") == "csrf-1"
                self.created.append((did, json.loads(request.content)))
                self.embedded[did] = f"9999999{did}-aaaa-bbbb-cccc-00000000000{did}"
            if did not in self.embedded:
                return httpx.Response(404, json={"message": "Not found"})
            return httpx.Response(200, json={"result": {"uuid": self.embedded[did], "allowed_domains": []}})
        if path.endswith("/datasets"):
            return httpx.Response(200, json={"result": DATASETS})
        if path == "/api/v1/security/guest_token/" and method == "POST":
            assert request.headers.get("x-csrftoken") == "csrf-1"
            self.guest_requests.append(json.loads(request.content))
            return httpx.Response(200, json={"token": "guest-token-1"})
        return httpx.Response(404)


def client_with(fake: FakeSuperset, **overrides) -> SupersetClient:
    settings = SupersetSettings(**{**SETTINGS.__dict__, **overrides})
    return SupersetClient(settings, transport=httpx.MockTransport(fake.handler))


def test_titles_codes_and_order():
    assert dashboard_code("Ferrero · DS‑1 Case Detail") == "DS-1"
    assert dashboard_code("Ferrero · D2 Leadership Command View") == "D2"
    assert dashboard_code("Something else") is None
    assert short_title("Ferrero · D1 Legal Case Overview", "D1", "Ferrero") == "Legal Case Overview"
    assert short_title("Ferrero · DS‑1 Case Detail", "DS-1", "Ferrero") == "Case Detail"
    fake = FakeSuperset()
    found = client_with(fake).dashboards()
    assert [d.code for d in found] == ["D1", "D2", "D3", "D4", "DS-1"]
    assert found[0].url == "http://superset.test:8088/superset/dashboard/5/"


def test_embedding_turned_on_once_for_dashboards_without_it():
    fake = FakeSuperset(embedded={1, 3, 4, 5})          # DS-1 (id 2) has no embed settings yet
    client = client_with(fake, allowed_domains=("http://localhost:8000",))
    found = client.dashboards()
    assert fake.created == [(2, {"allowed_domains": ["http://localhost:8000"]})]
    assert all(d.uuid for d in found)
    client.dashboards()                                  # cached: no second round of calls
    assert len(fake.created) == 1 and fake.logins == 1


def test_auto_embed_can_be_switched_off():
    fake = FakeSuperset(embedded={5})
    found = client_with(fake, auto_embed=False).dashboards()
    assert fake.created == [] and [d.code for d in found if d.uuid] == ["D1"]


def test_row_rules_follow_each_role(principals, model):
    datasets = [Dataset(x["id"], x["table_name"], tuple(c["column_name"] for c in x["columns"])) for x in DATASETS]
    countries = sorted({r["country"] for r in model.tables["fact_case"].dicts()})

    def visible(p):
        return [r["case_id"] for r in model.tables["fact_case"].dicts() if p.sees_group(r["access_group"])]

    ops = principals["ops"]
    assert row_rules(ops, datasets, countries, visible(ops)) == []
    uae = principals["uae"]
    rules = row_rules(uae, datasets, countries, visible(uae))
    assert {"dataset": 11, "clause": "country IN ('UAE')"} in rules
    invoice = next(r for r in rules if r["dataset"] == 12)["clause"]
    assert invoice.startswith("case_id IN (") and "'TM-2024-401'" in invoice and "'TM-2024-403'" not in invoice
    assert not any(r["dataset"] == 14 for r in rules)    # reference data stays unfiltered
    mena = principals["mena"]
    clause = next(r for r in row_rules(mena, datasets, countries, visible(mena)) if r["dataset"] == 11)["clause"]
    assert "'Egypt'" in clause and "'UAE'" not in clause and "'KSA'" not in clause
    procurement = principals["procurement"]
    assert row_rules(procurement, datasets, countries, visible(procurement)) == [{"dataset": 13, "clause": "1 = 0"}]
    focus = row_rules(ops, datasets, countries, visible(ops), case_id="TM-2024-428")
    assert {"dataset": 11, "clause": "case_id = 'TM-2024-428'"} in focus and len(focus) == 3


def test_guest_token_carries_user_resource_and_rules(principals, model):
    fake = FakeSuperset()
    client = client_with(fake)
    uuid = next(d.uuid for d in client.dashboards() if d.code == "D1")
    token = client.guest_token(principals["ksa"], uuid, ["KSA", "UAE"], ["TM-2024-403"])
    assert token == "guest-token-1"
    sent = fake.guest_requests[0]
    assert sent["user"]["username"] == "U-05"
    assert sent["resources"] == [{"type": "dashboard", "id": uuid}]
    assert {"dataset": 11, "clause": "country IN ('KSA')"} in sent["rls"]


def test_restricted_personas_never_get_an_unfiltered_token(principals):
    fake = FakeSuperset()
    fake_handler = fake.handler

    def no_datasets(request):
        if request.url.path.endswith("/datasets"):
            return httpx.Response(403, json={"message": "Forbidden"})
        return fake_handler(request)

    client = SupersetClient(SETTINGS, transport=httpx.MockTransport(no_datasets))
    uuid = next(d.uuid for d in client.dashboards() if d.code == "D1")
    for name in ("uae", "procurement"):
        try:
            client.guest_token(principals[name], uuid, ["UAE", "KSA"], [])
            raise AssertionError("an unfiltered token was issued")
        except Exception as e:
            assert getattr(e, "status", None) == 503
    assert client.guest_token(principals["ops"], uuid, ["UAE", "KSA"], []) == "guest-token-1"
    assert len(fake.guest_requests) == 1


def test_frame_ancestors_parsing():
    assert frame_ancestors(httpx.Headers({"content-security-policy": "frame-ancestors 'self' http://a:1; x y"})) == ["'self'", "http://a:1"]
    assert frame_ancestors(httpx.Headers({"x-frame-options": "SAMEORIGIN"})) == ["'self'"]
    assert frame_ancestors(httpx.Headers({})) is None


def test_settings_from_env():
    env = {"FERRERO_SUPERSET_URL": "http://s:8088/", "FERRERO_SUPERSET_USERNAME": "u", "FERRERO_SUPERSET_PASSWORD": "p",
           "FERRERO_SUPERSET_ALLOWED_DOMAINS": "http://localhost:8000/, http://127.0.0.1:8000"}
    s = SupersetSettings.from_env(env.get)
    assert s.url == "http://s:8088" and s.allowed_domains == ("http://localhost:8000", "http://127.0.0.1:8000")
    assert SupersetSettings.from_env({}.get) is None


def test_web_endpoints(settings, model, index, fake_claude):
    fake = FakeSuperset()
    app = create_app(settings, Assistant(settings, model, index, client=fake_claude.client()), superset=client_with(fake))
    c = TestClient(app)
    assert c.get("/api/meta").json()["embedded_dashboards"] is True
    info = c.get("/api/dashboards", params={"user_id": "U-03"}).json()
    assert info["mode"] == "embedded" and [d["code"] for d in info["dashboards"]] == ["D1", "D2", "D3", "D4", "DS-1"]
    assert info["frame_ancestors"] == ["'self'", "http://localhost:8090"]
    ds1 = info["dashboards"][-1]["uuid"]
    ok = c.post("/api/dashboards/guest-token", json={"user_id": "U-03", "dashboard": ds1, "case_id": "TM-2024-428"})
    assert ok.status_code == 200 and ok.json() == {"token": "guest-token-1"}
    assert {"dataset": 11, "clause": "case_id = 'TM-2024-428'"} in fake.guest_requests[-1]["rls"]
    # a KSA user cannot scope a dashboard to a UAE case, and unknown dashboards are refused
    assert c.post("/api/dashboards/guest-token", json={"user_id": "U-05", "dashboard": ds1, "case_id": "TM-2024-428"}).status_code == 404
    assert c.post("/api/dashboards/guest-token", json={"user_id": "U-05", "dashboard": "12345678-0000-0000-0000-000000000000"}).status_code == 404


def test_without_superset_the_page_falls_back(settings, model, index, fake_claude, monkeypatch):
    monkeypatch.delenv("FERRERO_SUPERSET_URL", raising=False)
    c = TestClient(create_app(settings, Assistant(settings, model, index, client=fake_claude.client())))
    assert c.get("/api/dashboards", params={"user_id": "U-08"}).json()["mode"] in ("none", "links")
    assert c.post("/api/dashboards/guest-token", json={"user_id": "U-08", "dashboard": "0" * 32}).status_code == 404
