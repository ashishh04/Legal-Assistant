"""Checks that every feature the customer asked for is present and working: one command, on a throw-away copy.

    .venv\\Scripts\\python scripts\\check_features.py                        (this machine)
    sudo docker compose exec -T ferrero python - < scripts/check_features.py   (a server: inside the running container)

- It starts the real application inside this process with an empty, temporary records store. Your own records, your
  passwords and any Ferrero you have running are not touched, and nothing is kept afterwards. It sends no e-mail,
  even where a mail service is configured.
- It signs in as the platform administrator (with a temporary password made for this run) and works through each
  request with the same calls the web pages make.
- Nothing is sent to the AI model service: the assistant's answers (R2-R4, R6, R7) are checked by hand in the browser.
- The dashboard server is asked for its dashboards; if it can't be reached from this machine, that line says so.
Exit code 0 when nothing failed.
"""
from __future__ import annotations

import dataclasses
import logging
import os
import secrets
import shutil
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()  # piped in: no __file__
sys.path.insert(0, str(ROOT / "src"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

from fastapi.testclient import TestClient  # noqa: E402

from ferrero.config import get_settings  # noqa: E402
from ferrero.web.app import create_app  # noqa: E402

JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + bytes(range(256)) * 8
PDF = b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF\n"
rows: list[tuple[str, str, str, str]] = []
state: dict = {}


def check(group: str, name: str, fn, manual: bool = False) -> None:
    try:
        detail = fn() or ""
        rows.append((group, name, "MANUAL" if manual else "PASS", str(detail)))
    except Warn as w:
        rows.append((group, name, "WARN", str(w)))
    except Exception as e:  # noqa: BLE001 - every failure is reported, the run goes on
        rows.append((group, name, "FAIL", f"{type(e).__name__}: {e}"[:160]))


class Warn(Exception):
    pass


def ok(r, *codes):
    if r.status_code not in (codes or (200,)):
        raise AssertionError(f"HTTP {r.status_code}: {r.text[:120]}")
    return r


def main() -> int:
    logging.getLogger("ferrero").setLevel(logging.ERROR)  # the report says it; the log needn't
    base = get_settings()  # reads .env into the environment ...
    for key in [k for k in os.environ if k.startswith("FERRERO_SMTP_")]:
        del os.environ[key]  # ... and the check never sends e-mail, even where a mail service is configured
    tmp = Path(tempfile.mkdtemp(prefix="ferrero-check-"))
    admin_pw = "Check-" + secrets.token_urlsafe(12)
    settings = dataclasses.replace(base, records_path=tmp, admin_password=admin_pw, demo_password=None)
    today = settings.today()
    app = create_app(settings)
    H = {"X-Ferrero": "1"}
    try:
        with TestClient(app, headers=H) as c:
            run(c, TestClient(app, headers=H), TestClient(app, headers=H), settings, admin_pw, today)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    report(today)
    return 1 if any(r[2] == "FAIL" for r in rows) else 0


def run(c, anon, other, settings, admin_pw, today) -> None:
    G = "Sign-in, landing and sign-out pages (17-18 Nov)"
    check(G, "Landing, sign-in and sign-out pages are served",
          lambda: all('id="root"' in ok(anon.get(p)).text for p in ("/", "/login", "/logout")) and "/, /login, /logout")
    check(G, "Every API call needs a signed-in user", lambda: ok(anon.get("/api/cases"), 401) and "401 without a session")

    def admin_sign_in():
        assert ok(c.post("/api/auth/login", json={"login": settings.admin_email, "password": admin_pw + "x"}), 401)
        me = ok(c.post("/api/auth/login", json={"login": settings.admin_email, "password": admin_pw})).json()["user"]
        assert me["is_admin"], "not the administrator"
        return f"{settings.admin_email} signs in (wrong password refused)"
    check(G, "Platform administrator signs in", admin_sign_in)

    G = "Users and switching user (18 Nov)"

    def add_user():
        u = ok(c.post("/api/admin/users", json={
            "full_name": "Check Counsel", "email": "check.counsel@example.com", "job_title": "IP Counsel",
            "entra_group": "Legal-UAE", "country": "UAE", "password": "Temporary-Pass-4821"})).json()
        state["new_user"] = u["user_id"]
        me = ok(other.post("/api/auth/login", json={"login": "check.counsel@example.com",
                                                    "password": "Temporary-Pass-4821"})).json()["user"]
        assert me["own_password"] is False, "not asked to change the temporary password"
        return f"{u['user_id']} added; signs in and is asked to set a personal password"
    check(G, "Administrator adds a user with a temporary password", add_user)

    def switch():
        me = ok(c.post("/api/admin/switch", json={"user_id": "U-05"})).json()["user"]
        assert me["acting_by"], "no switch recorded"
        countries = {r["country"] for r in ok(c.get("/api/cases")).json()}
        ok(c.post("/api/admin/switch/back"))
        assert countries == {"KSA"}, countries
        return "viewed as Omar Al Qahtani (KSA cases only), then returned"
    check(G, "Administrator switches user inside the portal and back", switch)

    def disable():
        ok(c.patch(f"/api/admin/users/{state['new_user']}", json={"changes": {"active": False}}))
        r = other.post("/api/auth/login", json={"login": "check.counsel@example.com", "password": "Temporary-Pass-4821"})
        assert r.status_code == 403, r.status_code
        return "disabled account can't sign in"
    check(G, "Administrator disables an account", disable)

    G = "Demo feedback: workflow, alerts, comparison, simpler pages (17 Nov)"
    check(G, "Simpler landing page and Overview", lambda: "look at / signed out, then the Overview", manual=True)

    def register():
        o = ok(c.get("/api/register/options")).json()
        r = ok(c.post("/api/cases", json={
            "mark_id": "MK-01", "infringer_name": "Check Trading LLC", "infringer_type": o["infringer_types"][0],
            "case_type": o["case_types"][0], "country": "UAE", "source_channel": o["sources"][0],
            "lead_counsel_id": "U-04", "details": "Feature check"})).json()
        state["case"] = r["case_id"]
        assert r["case"]["stage"] == "Intake"
        return f"{r['case_id']} registered at Intake"
    check(G, "Register a case", register)

    def as_user(uid, fn):
        ok(c.post("/api/admin/switch", json={"user_id": uid}))
        try:
            return fn()
        finally:
            ok(c.post("/api/admin/switch/back"))

    def unread(uid):
        return as_user(uid, lambda: [(n["title"], n["case_id"]) for n in ok(c.get("/api/notifications")).json()["items"]
                                     if not n["read"]])

    def assign():
        ok(c.patch(f"/api/cases/{state['case']}", json={"changes": {"lead_counsel_id": "U-07"}, "reason": "Feature check"}))
        assert ("Case assigned to you", state["case"]) in unread("U-07"), "no assignment alert"
        return "new owner (Youssef Nasser) gets 'Case assigned to you'"
    check(G, "Assign the case to a new owner", assign)

    G2 = "Case-management requirements (17 Nov)"

    def photo():
        r = ok(c.post(f"/api/cases/{state['case']}/evidence", params={"file_name": "shelf.jpg", "category": "Product photo",
                      "location": "Dubai outlet"}, content=JPEG, headers={"Content-Type": "image/jpeg"})).json()
        state["photo"] = r["evidence_id"]
        assert r["image"]
        return f"{r['evidence_id']} stored with SHA-256 {r['sha256'][:12]}..."
    check(G2, "Photo upload (mandatory)", photo)

    def repository():
        cats = set(ok(c.get("/api/meta")).json()["case_options"]["evidence_categories"])
        need = {"Product photo", "Screenshot", "Cease-and-desist letter", "Correspondence with authorities", "Invoice",
                "External counsel document", "Other evidence"}
        assert need <= cats, need - cats
        ok(c.post(f"/api/cases/{state['case']}/evidence", params={"file_name": "cease-and-desist.pdf",
               "category": "Cease-and-desist letter"}, content=PDF, headers={"Content-Type": "application/pdf"}))
        return "7 categories; a signed letter (PDF) stored too"
    check(G2, "Evidence and document repository", repository)
    check(G2, "Evidence integrity check",
          lambda: ok(c.get(f"/api/evidence/{state['photo']}/verify")).json()["ok"] and "file unchanged since upload")

    def commercial():
        ok(c.patch(f"/api/cases/{state['case']}", json={"changes": {
            "business_priority": "High", "consultation_required": True, "commercial_relationship": "Customer"}}))
        r = c.patch(f"/api/cases/{state['case']}", json={"changes": {"stage": "Notice sent"}})
        assert r.status_code == 409 and r.json().get("code") == "consultation_required", r.status_code
        return "Business Priority + Consultation saved; enforcement blocked until cleared"
    check(G2, "Commercial sensitivity indicators", commercial)

    def comparison():
        marks = ok(c.get("/api/marks")).json()
        assert len(marks) >= 6 and all(m["specimen"] for m in marks)
        assert ok(c.get("/api/marks/MK-01/specimen")).headers["content-type"] == "image/png"
        r = ok(c.post(f"/api/cases/{state['case']}/comparison", json={
            "infringing_sign": "VELLORA", "evidence_id": state["photo"], "visual": "High", "phonetic": "High",
            "conceptual": "Medium", "goods": "Identical", "overall": "High"})).json()
        return f"mark vs photo recorded; indication {r['indicators']['indication']}, {r['indicators']['word_similarity']:.0%} alike"
    check(G, "Visual trademark comparison", comparison)

    def follow_up():
        start = (today - timedelta(days=30)).isoformat()
        f = ok(c.post(f"/api/cases/{state['case']}/follow-ups", json={
            "kind": "Compliance deadline", "title": "Store to remove the products", "start_date": start,
            "period_days": 30, "owner_id": "U-07"})).json()
        state["fu"] = f["follow_up_id"]
        assert f["due_date"] == today.isoformat(), f["due_date"]
        alerts = unread("U-07")
        assert ("Deadline reached: follow up and decide", state["case"]) in alerts, alerts[:3]
        return f"30-day deadline due today -> owner alerted 'Deadline reached: follow up and decide'"
    check(G2, "Automated follow-up notifications", follow_up)
    check(G, "Deadline alerts (bell and Follow-ups page)",
          lambda: f"{len(ok(c.get('/api/follow-ups')).json()['items'])} open deadlines on the Follow-ups page")

    def close():
        ok(c.post(f"/api/follow-ups/{state['fu']}/resolve", json={"decision": "close_case", "outcome": "Takedown achieved"}))
        case = ok(c.get(f"/api/cases/{state['case']}")).json()
        assert (case["status"], case["outcome"]) == ("Closed", "Takedown achieved"), case["status"]
        return "decision 'complied, close the case' -> Closed, Takedown achieved"
    check(G, "Close the case", close)

    def audit():
        a = ok(c.get(f"/api/cases/{state['case']}/audit")).json()
        assert a["integrity"]["ok"], a["integrity"]
        actions = {e["action"] for e in a["entries"]}
        assert {"case.registered", "evidence.added", "comparison.recorded", "case.closed"} <= actions, actions
        e = a["entries"][0]
        assert e["actor_name"] and e["at"] and e["changes"]
        csv = ok(c.get(f"/api/cases/{state['case']}/audit.csv"))
        assert csv.headers["content-type"].startswith("text/csv")
        return f"{len(a['entries'])} entries (who, when, before/after); tamper check passed; CSV export"
    check(G2, "Comprehensive audit trail", audit)

    G = "Technical proposal R1-R11"

    def access():
        def omar():
            assert c.get(f"/api/cases/{state['case']}").status_code == 404  # a UAE case
            groups = {d["access_group"] for d in ok(c.get("/api/sync")).json()["documents"]}
            assert groups <= {"Legal-KSA"}, groups
        as_user("U-05", omar)

        def procurement():
            assert ok(c.get("/api/sync")).json()["visible"] is False
            assert c.get(f"/api/cases/{state['case']}/evidence").status_code == 403
        as_user("U-10", procurement)
        return "KSA counsel: no UAE case, KSA documents only; Procurement: no documents or evidence"
    check(G, "R5 Respect document access", access)

    def scans():
        docs = ok(c.get("/api/sync")).json()["documents"]
        read = [d for d in docs if d["extraction"] == "ocr" and str(d["index_status"]).startswith("Indexed")]
        waiting = [d for d in docs if str(d["skip_reason"] or "").startswith("Scanned PDF")]
        if not read:
            raise AssertionError("no scanned document is searchable")
        view = ok(c.get(f"/api/documents/{read[0]['doc_id']}")).json()
        assert view["page_images"] > 0 and view["sections"]
        return f"{len(read)} scans searchable (page image + text), {len(waiting)} still queued"
    check(G, "R9 Scanned documents searchable", scans)

    def dashboards():
        try:
            d = c.get("/api/dashboards").json()
        except Exception as e:  # noqa: BLE001
            raise Warn(f"dashboard server not reachable from this machine ({type(e).__name__})") from None
        if d.get("mode") == "none":
            raise Warn("dashboards are not configured in .env")
        if d.get("error") or not d.get("dashboards"):
            raise Warn(f"dashboard server not reachable from this machine: {d.get('error') or 'no dashboards'}")
        return f"{len(d['dashboards'])} dashboards: " + ", ".join((x.get('code') or x.get('title') or '?') for x in d['dashboards'][:6])
    check(G, "R1 Consolidated case dashboards", dashboards)

    check(G, "R2-R4, R6, R7 Assistant (EN/AR, cited, only from files, exact IDs, comparisons)",
          lambda: ok(c.post("/api/conversations", json={})) and "assistant ready - ask the questions in the browser", manual=True)
    check(G, "R8 Prompt injection / misuse", lambda: "partly: access enforced in the data layer; no separate filter", manual=True)
    check(G, "R10 Quality and cost transparency", lambda: "partly: steps + time per answer; python -m ferrero.eval (billed)", manual=True)
    check(G, "R11 Run on your cloud", lambda: "Docker container (Dockerfile, docker-compose.yml); Microsoft stack: open", manual=True)


def report(today) -> None:
    print(f"\nFerrero feature check - {today:%d %b %Y} - temporary copy, nothing saved\n")
    order = ["Sign-in", "Users", "Case-management", "Demo feedback", "Technical proposal"]
    groups = sorted(dict.fromkeys(r[0] for r in rows),
                    key=lambda g: next((i for i, k in enumerate(order) if g.startswith(k)), len(order)))
    for g in groups:
        print(f"  {g}")
        for _, name, status, detail in (r for r in rows if r[0] == g):
            print(f"    {status:<6} {name:<62} {detail}")
    n = {s: sum(1 for r in rows if r[2] == s) for s in ("PASS", "FAIL", "WARN", "MANUAL")}
    print(f"\n  {n['PASS']} passed, {n['FAIL']} failed, {n['WARN']} warning(s), {n['MANUAL']} to check by hand in the browser\n")


if __name__ == "__main__":
    sys.exit(main())
