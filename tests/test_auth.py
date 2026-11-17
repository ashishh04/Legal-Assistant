"""Sign-in: passwords, sessions, lockout, the app header, password changes, and that every API route needs a session."""
import re
import sqlite3
from contextlib import closing
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from ferrero.assistant.agent import Assistant
from ferrero.auth.passwords import hash_password, password_problem, verify_password
from ferrero.casemodel import CaseModel
from ferrero.web.app import create_app

from conftest import DEMO_TODAY, PACK, TEST_PASSWORD, sign_in


@pytest.fixture
def make_client(index, fake_claude):
    def make(settings):
        model = CaseModel(PACK / "csv", DEMO_TODAY)
        c = TestClient(create_app(settings, Assistant(settings, model, index, client=fake_claude.client())))
        c.headers["X-Ferrero"] = "1"
        return c
    return make


@pytest.fixture
def client(make_client, settings):
    return make_client(settings)


def login(c, name, password=TEST_PASSWORD, **extra):
    return c.post("/api/auth/login", json={"login": name, "password": password, **extra})


def test_password_hashing():
    stored = hash_password("correct horse battery")
    assert stored.startswith("scrypt$") and "correct" not in stored
    assert verify_password("correct horse battery", stored)
    assert not verify_password("correct horse batterY", stored)
    assert not verify_password("anything", "not-a-hash") and not verify_password("x", "md5$1$2$3$4$5")
    assert hash_password("same") != hash_password("same")  # salted
    assert password_problem("short", email="a@b") and password_problem("aaaaaaaaaaaa")
    assert "name" in password_problem("PriyaMenon-2026!", email="priya.menon@demo.local", full_name="Priya Menon")
    assert password_problem("Velvet-Harbour-73", email="priya.menon@demo.local", full_name="Priya Menon") is None


def test_sign_in_by_email_or_user_id_and_sign_out(client):
    r = login(client, "Priya.Menon@demo.local")
    assert r.status_code == 200 and r.json()["user"]["user_id"] == "U-08"
    assert r.json()["user"]["email"] == "priya.menon@demo.local" and r.json()["user"]["own_password"] is False
    cookie = r.headers["set-cookie"]
    assert "ferrero_session=" in cookie and "HttpOnly" in cookie and "samesite=lax" in cookie.lower()
    assert "secure" not in cookie.lower() and "max-age" not in cookie.lower()  # plain HTTP; ends with the browser
    assert client.get("/api/auth/me").json()["user"]["full_name"] == "Priya Menon"
    assert client.post("/api/auth/logout").json() == {"signed_out": True}
    assert client.get("/api/auth/me").json() == {"user": None}
    assert login(client, "u-05").json()["user"]["full_name"] == "Omar Al Qahtani"


def test_keep_me_signed_in_sets_a_lasting_cookie(make_client, settings):
    c = make_client(replace(settings, cookie_secure="true"))
    cookie = login(c, "U-08", remember=True).headers["set-cookie"].lower()
    assert "max-age=1209600" in cookie and "secure" in cookie  # 14 days


def test_wrong_and_unknown_names_get_the_same_answer_then_a_lockout(client):
    wrong = login(client, "U-08", "nope")
    unknown = login(client, "nobody@demo.local", "nope")
    assert wrong.status_code == unknown.status_code == 401 and wrong.json()["detail"] == unknown.json()["detail"]
    for _ in range(4):
        login(client, "U-08", "still wrong")
    locked = login(client, "U-08")  # the right password, but the name is locked for 15 minutes
    assert locked.status_code == 429 and locked.json()["code"] == "locked"
    assert login(client, "U-07").status_code == 200  # others aren't affected
    app_auth = client.app.state.auth
    with closing(sqlite3.connect(app_auth.store.path)) as conn:
        rows = conn.execute("SELECT login, ok, reason FROM sign_ins ORDER BY seq").fetchall()
    assert ("nobody@demo.local", 0, "unknown name") in rows and rows[-1] == ("U-07", 1, None)


def test_every_api_route_needs_a_session(client):
    open_routes = {"/api/public", "/api/auth/login", "/api/auth/logout", "/api/auth/me"}
    assert client.get("/api/auth/me").json() == {"user": None}  # answers, but tells nothing
    checked = 0
    for route in client.app.routes:
        path = getattr(route, "path", "")
        if not path.startswith("/api/") or path in open_routes or path.startswith("/api/docs") or path == "/api/openapi.json":
            continue
        url = re.sub(r"\{[^}]+\}", "TM-2026-417", path)
        for method in route.methods - {"HEAD", "OPTIONS"}:
            assert client.request(method, url, json={}).status_code == 401, (method, path)
            checked += 1
    assert checked >= 25  # the sweep really ran over the API


def test_changes_need_the_app_header(client):
    sign_in(client, "U-08")
    del client.headers["X-Ferrero"]
    refused = client.patch("/api/cases/TM-2026-424", json={"changes": {"priority": "High"}})
    assert refused.status_code == 403 and refused.json()["code"] == "csrf"
    assert client.get("/api/cases/TM-2026-424").status_code == 200  # reading needs no header


def test_expired_sessions_end(client):
    sign_in(client, "U-08")
    with closing(sqlite3.connect(client.app.state.auth.store.path)) as conn, conn:
        conn.execute("UPDATE sessions SET expires_at = '2000-01-01T00:00:00+00:00'")
    assert client.get("/api/auth/me").json() == {"user": None}
    assert client.get("/api/cases").status_code == 401


def test_changing_the_password(make_client, settings):
    first, second = make_client(settings), make_client(settings)
    sign_in(first, "U-04")
    sign_in(second, "U-04")  # the same person on another device
    bad = first.post("/api/auth/password", json={"current_password": "wrong", "new_password": "Velvet-Harbour-73"})
    assert bad.status_code == 400 and bad.json()["code"] == "bad_current"
    weak = first.post("/api/auth/password", json={"current_password": TEST_PASSWORD, "new_password": "short"})
    assert weak.json()["code"] == "weak_password"
    ok = first.post("/api/auth/password", json={"current_password": TEST_PASSWORD, "new_password": "Velvet-Harbour-73"})
    assert ok.status_code == 200
    assert first.get("/api/auth/me").json()["user"]["own_password"] is True  # this session continues
    assert second.get("/api/auth/me").json() == {"user": None}  # the other device is signed out
    assert login(second, "U-04").status_code == 401  # the starting password no longer works for Sara
    assert login(second, "U-04", "Velvet-Harbour-73").status_code == 200
    assert login(second, "U-07").status_code == 200  # but still does for everyone else


def test_without_any_password_nobody_can_sign_in(make_client, settings):
    c = make_client(replace(settings, demo_password=None))
    assert c.get("/api/public").json()["sign_in_configured"] is False
    assert login(c, "U-08", "").status_code == 400 and login(c, "U-08", "anything").status_code == 401


def test_the_account_list_is_shown_only_when_switched_on(make_client, settings):
    assert make_client(settings).get("/api/public").json()["accounts"] is None
    accounts = make_client(replace(settings, login_show_accounts=True)).get("/api/public").json()["accounts"]
    assert len(accounts) == 10 and all("password" not in str(a).lower() for a in accounts)
