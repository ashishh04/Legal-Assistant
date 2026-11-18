"""The platform administrator: signing in with the configured password, managing users, switching into a user's view."""
import dataclasses

import pytest
from fastapi.testclient import TestClient

from ferrero.assistant.agent import Assistant
from ferrero.casemodel import CaseModel
from ferrero.web.app import create_app

from conftest import DEMO_TODAY, PACK, sign_in

ADMIN_PASSWORD = "Harbour-Lantern-2026"
NEW_USER = {"full_name": "Hana Khoury", "email": "Hana.Khoury@demo.local", "job_title": "IP Counsel",
            "entra_group": "Legal-UAE", "country": "UAE", "password": "Cedar-Window-418"}


@pytest.fixture
def make_client(settings, index, fake_claude):
    """A fresh app (and records store) per client; the same store when `like` names an earlier client."""
    made = []

    def make(**overrides):
        s = dataclasses.replace(settings, **{"admin_password": ADMIN_PASSWORD, **overrides})
        c = TestClient(create_app(s, Assistant(s, CaseModel(PACK / "csv", DEMO_TODAY), index, client=fake_claude.client())))
        c.__enter__()
        made.append(c)
        return c

    yield make
    for c in made:
        c.__exit__(None, None, None)


def admin_in(c):
    c.headers.update({"X-Ferrero": "1"})
    r = c.post("/api/auth/login", json={"login": "admin@ferrero.com", "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["user"]


def login(c, who, password):
    c.headers.update({"X-Ferrero": "1"})
    return c.post("/api/auth/login", json={"login": who, "password": password})


def test_the_administrator_signs_in_with_the_configured_password(make_client):
    c = make_client()
    assert login(c, "admin@ferrero.com", "wrong-password-1").status_code == 401
    me = admin_in(c)
    assert me["is_admin"] and me["email"] == "admin@ferrero.com" and me["user_id"] == "U-00" and me["own_password"]
    assert me["acting_by"] is None and me["entra_group"] == "Platform-Admin"
    assert len(c.get("/api/cases").json()) == 120  # every country
    admin = next(u for u in c.get("/api/users").json() if u["user_id"] == "U-00")
    assert admin["can_own"] is False and admin["admin"]  # changes cases, owns none
    r = c.post("/api/auth/password", json={"current_password": ADMIN_PASSWORD, "new_password": "Another-Pass-2026"})
    assert r.status_code == 400 and r.json()["code"] == "managed"
    listing = c.get("/api/admin/users").json()
    assert listing["users"][0]["user_id"] == "U-00" and listing["users"][0]["password"] == "configured"
    assert "Platform-Admin" not in [r["group"] for r in listing["roles"]] and "UAE" in listing["countries"]
    # no FERRERO_PASSWORD: the administrator can't sign in at all (no built-in default)
    bare = make_client(admin_password=None)
    assert login(bare, "admin@ferrero.com", ADMIN_PASSWORD).status_code == 401


def test_only_the_administrator_manages_users_or_switches(make_client):
    c = make_client()
    sign_in(c, "U-08")  # Legal Operations
    assert c.get("/api/admin/users").status_code == 403
    assert c.post("/api/admin/users", json=NEW_USER).status_code == 403
    assert c.post("/api/admin/switch", json={"user_id": "U-06"}).status_code == 403
    assert c.post("/api/admin/switch/back").status_code == 403
    me = c.get("/api/auth/me").json()["user"]
    assert me["is_admin"] is False and me["acting_by"] is None


def test_adding_a_user_with_a_temporary_password(make_client):
    c = make_client()
    admin_in(c)
    r = c.post("/api/admin/users", json=NEW_USER)
    assert r.status_code == 200, r.text
    added = r.json()
    assert added["user_id"] == "U-11" and added["email"] == "hana.khoury@demo.local" and added["source"] == "added"
    assert added["password"] == "temporary" and added["active"] and added["team"] == "IP"
    # she signs in, is asked to change the temporary password, and sees UAE cases only
    r = login(c, "hana.khoury@demo.local", NEW_USER["password"])
    assert r.status_code == 200 and r.json()["user"]["own_password"] is False
    assert {row["country"] for row in c.get("/api/cases").json()} == {"UAE"}
    r = c.post("/api/auth/password", json={"current_password": NEW_USER["password"], "new_password": "Quiet-Harbour-Bell-9"})
    assert r.status_code == 200
    assert c.get("/api/auth/me").json()["user"]["own_password"] is True
    # she can own UAE cases
    new_case = {"mark_id": "MK-01", "infringer_name": "Desert Sweets", "infringer_type": "Retailer",
                "case_type": "Online marketplace listing", "country": "UAE", "source_channel": "Intake form",
                "lead_counsel_id": "U-11"}
    r = c.post("/api/cases", json=new_case)
    assert r.status_code == 200, r.text
    assert r.json()["case"]["lead_counsel"] == "Hana Khoury"


def test_user_details_are_checked(make_client):
    c = make_client()
    admin_in(c)
    assert c.post("/api/admin/users", json={**NEW_USER, "email": "sara.haddad@demo.local"}).status_code == 409
    weak = c.post("/api/admin/users", json={**NEW_USER, "password": "short"})
    assert weak.status_code == 400 and weak.json()["code"] == "weak_password"
    assert c.post("/api/admin/users", json={**NEW_USER, "entra_group": "Platform-Admin"}).status_code == 400
    assert c.post("/api/admin/users", json={**NEW_USER, "email": "not-an-address"}).status_code == 400
    assert c.post("/api/admin/users", json={**NEW_USER, "country": "Atlantis"}).status_code == 400
    # people from the company directory: only their access can be turned off and on
    r = c.patch("/api/admin/users/U-04", json={"changes": {"job_title": "Partner"}})
    assert r.status_code == 409 and r.json()["code"] == "directory"
    assert c.patch("/api/admin/users/U-00", json={"changes": {"active": False}}).status_code == 409
    assert c.post("/api/admin/users/U-00/password", json={"password": "Another-Pass-2026"}).status_code == 409
    added = c.post("/api/admin/users", json=NEW_USER).json()
    changed = c.patch(f"/api/admin/users/{added['user_id']}",
                      json={"changes": {"entra_group": "Legal-KSA", "job_title": "Litigation Counsel"}}).json()
    assert (changed["entra_group"], changed["job_title"], changed["team"]) == ("Legal-KSA", "Litigation Counsel", "Litigation")


def test_disabling_and_enabling_an_account(make_client):
    c = make_client()
    admin_in(c)
    r = c.patch("/api/admin/users/U-04", json={"changes": {"active": False}})
    assert r.status_code == 200 and r.json()["active"] is False
    users = {u["user_id"]: u for u in c.get("/api/users").json()}
    assert users["U-04"]["active"] is False and users["U-04"]["can_own"] is False
    # she can't own cases while disabled
    r = c.patch("/api/cases/TM-2026-421", json={"changes": {"lead_counsel_id": "U-04"}})
    assert r.status_code == 400
    r = login(c, "sara.haddad@demo.local", "Starting-pass-2026")
    assert r.status_code == 403 and r.json()["code"] == "disabled"
    admin_in(c)
    assert c.patch("/api/admin/users/U-04", json={"changes": {"active": True}}).json()["active"] is True
    assert login(c, "sara.haddad@demo.local", "Starting-pass-2026").status_code == 200


def test_temporary_passwords_without_a_starting_password(make_client):
    c = make_client(demo_password=None)
    assert login(c, "lina.mansour@demo.local", "Starting-pass-2026").status_code == 401
    admin_in(c)
    assert {u["password"] for u in c.get("/api/admin/users").json()["users"] if u["source"] == "directory"} == {"not set"}
    r = c.post("/api/admin/users/U-06/password", json={"password": "Olive-Garden-2077"})
    assert r.status_code == 200 and r.json()["password"] == "temporary"
    r = login(c, "lina.mansour@demo.local", "Olive-Garden-2077")
    assert r.status_code == 200 and r.json()["user"]["own_password"] is False


def test_switching_into_a_users_view_and_back(make_client):
    c = make_client()
    admin_in(c)
    r = c.post("/api/admin/switch", json={"user_id": "U-06"})
    assert r.status_code == 200, r.text
    me = r.json()["user"]
    assert me["user_id"] == "U-06" and me["acting_by"] == {"user_id": "U-00", "full_name": "Platform Administrator"}
    assert me["is_admin"] is False and me["own_password"] is True
    assert c.get("/api/auth/me").json()["user"]["full_name"] == "Lina Mansour"
    countries = {row["country"] for row in c.get("/api/cases").json()}
    assert "UAE" not in countries and "KSA" not in countries  # exactly Lina's access (Legal-MENA)
    assert c.get("/api/cases/TM-2026-421").status_code == 404  # a UAE case
    # a change made in her view names the administrator too
    r = c.patch("/api/cases/TM-2026-430", json={"changes": {"priority": "Medium"}, "reason": "Re-prioritised"})
    assert r.status_code == 200, r.text
    entry = c.get("/api/cases/TM-2026-430/audit").json()["entries"][0]
    assert entry["actor_name"] == "Platform Administrator as Lina Mansour" and entry["actor_id"] == "U-06"
    # while switched: no administration, no password changes
    assert c.get("/api/admin/users").status_code == 403
    # straight on to another user's view (still the administrator's session)
    omar = c.post("/api/admin/switch", json={"user_id": "U-05"}).json()["user"]
    assert omar["user_id"] == "U-05" and omar["acting_by"]["user_id"] == "U-00"
    assert {row["country"] for row in c.get("/api/cases").json()} == {"KSA"}
    r = c.post("/api/auth/password", json={"current_password": "x", "new_password": "Something-Long-2026"})
    assert r.status_code == 400 and r.json()["code"] == "acting"
    back = c.post("/api/admin/switch/back").json()["user"]
    assert back["user_id"] == "U-00" and back["is_admin"] and back["acting_by"] is None
    assert c.post("/api/admin/switch", json={"user_id": "U-00"}).status_code == 400
    assert c.post("/api/admin/switch", json={"user_id": "U-99"}).status_code == 404
    c.patch("/api/admin/users/U-05", json={"changes": {"active": False}})
    assert c.post("/api/admin/switch", json={"user_id": "U-05"}).status_code == 409
    # the switch into an account that is then disabled ends with the administrator's own view
    c.post("/api/admin/switch", json={"user_id": "U-06"})
    auth = c.app.state.auth
    with auth.store.connect() as conn:
        conn.execute("INSERT INTO disabled_users (user_id, disabled_by, disabled_at) VALUES ('U-06', 'U-00', 'now')")
    auth.reload_directory()
    assert c.get("/api/auth/me").json()["user"]["user_id"] == "U-00"
    with auth.store.connect() as conn:
        actions = [r["action"] for r in conn.execute("SELECT action FROM admin_log ORDER BY seq")]
    assert actions == ["switch", "switch", "switch.back", "user.disabled", "switch"]
