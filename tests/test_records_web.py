"""The case-records API: case changes, evidence upload and download, follow-ups, notifications and the audit trail."""
import pytest
from fastapi.testclient import TestClient

from ferrero.assistant.agent import Assistant
from ferrero.casemodel import CaseModel
from ferrero.web.app import create_app

from conftest import DEMO_TODAY, PACK, sign_in

JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x01" * 4000


@pytest.fixture
def client(settings, index, fake_claude):
    model = CaseModel(PACK / "csv", DEMO_TODAY)  # fresh: the requests below change it
    with TestClient(create_app(settings, Assistant(settings, model, index, client=fake_claude.client()))) as c:
        yield c  # entering runs the app's start-up deadline check


def upload(c, case_id="TM-2026-417", user="U-07", name="shelf.jpg", data=JPEG, **details):
    sign_in(c, user)
    params = {"file_name": name, "category": "Product photo", **details}
    return c.post(f"/api/cases/{case_id}/evidence", params=params, content=data,
                  headers={"Content-Type": "application/octet-stream"})


def test_meta_users_and_case_page_carry_what_the_forms_need(client):
    sign_in(client, "U-07")
    meta = client.get("/api/meta").json()
    options = meta["case_options"]
    assert "Product photo" in options["evidence_categories"] and options["evidence_max_mb"] == 25
    assert [k["kind"] for k in options["follow_up_kinds"]][0] == "Compliance deadline"
    users = {u["user_id"]: u for u in client.get("/api/users").json()}
    assert users["U-04"]["can_edit"] and not users["U-10"]["can_edit"] and users["U-05"]["case_groups"] == ["Legal-KSA"]
    page = client.get("/api/cases/TM-2026-417").json()
    assert page["permissions"] == {"edit": True, "evidence": True, "add_evidence": True}
    assert page["counts"] == {"evidence": 0, "follow_ups_open": 0, "audit": 0}
    assert page["consultation_required"] is None and page["business_priority"] is None
    sign_in(client, "U-10")
    proc = client.get("/api/cases/TM-2026-417").json()
    assert proc["permissions"]["edit"] is False and proc["counts"]["evidence"] is None


def test_photo_upload_download_and_integrity(client):
    r = upload(client, title="Lookalike jars", captured_on="2026-11-04", location="Deira, Dubai")
    assert r.status_code == 200, r.text
    item = r.json()
    assert item["evidence_id"] == "EVD-00001" and item["image"] and item["title"] == "Lookalike jars"
    assert item["uploaded_by"] == "Youssef Nasser"  # the signed-in user, not anything the request said
    sign_in(client, "U-04")
    got = client.get("/api/evidence/EVD-00001/file")
    assert got.content == JPEG and got.headers["content-type"] == "image/jpeg"
    assert got.headers["content-disposition"].startswith("inline") and got.headers["x-content-type-options"] == "nosniff"
    assert got.headers["content-security-policy"] == "sandbox"
    assert client.get("/api/evidence/EVD-00001/file", params={"download": True}).headers["content-disposition"].startswith("attachment")
    assert client.get("/api/evidence/EVD-00001/verify").json()["ok"] is True
    assert [e["evidence_id"] for e in client.get("/api/cases/TM-2026-417/evidence").json()] == ["EVD-00001"]
    # no one outside the case's group, and no role without documents, gets the file
    sign_in(client, "U-05")
    assert client.get("/api/evidence/EVD-00001/file").status_code == 404
    sign_in(client, "U-10")
    assert client.get("/api/evidence/EVD-00001/file").status_code == 403


def test_uploads_are_refused_with_a_reason(client):
    assert upload(client, user="U-10").json()["code"] == "read_only"
    assert upload(client, user="U-05").status_code == 404
    bad = upload(client, name="page.jpg", data=b"<html></html>")
    assert bad.status_code == 415 and "isn't a real JPEG" in bad.json()["detail"]
    assert upload(client, name="tool.exe", data=b"MZ").json()["code"] == "file_type"
    big = client.post("/api/cases/TM-2026-417/evidence", params={"file_name": "big.jpg", "category": "Product photo"},
                      content=JPEG, headers={"Content-Length": str(26 * 1024 * 1024)})
    assert big.status_code == 413
    assert upload(client).status_code == 200 and upload(client, name="again.jpg").status_code == 409


def test_case_changes_and_the_consultation_gate_over_http(client):
    sign_in(client, "U-07")
    r = client.patch("/api/cases/TM-2026-417", json={"changes": {
        "business_priority": "High", "consultation_required": True, "commercial_relationship": "Commercial partner"}})
    assert r.status_code == 200 and r.json()["case"]["consultation_status"] == "Not started"
    blocked = client.patch("/api/cases/TM-2026-417", json={"changes": {"stage": "Filed"}})
    assert blocked.status_code == 409 and blocked.json()["code"] == "consultation_required"
    ok = client.patch("/api/cases/TM-2026-417", json={"changes": {"stage": "Filed"}, "override_reason": "Customs seizure deadline"})
    assert ok.json()["case"]["stage"] == "Filed" and ok.json()["case"]["counts"]["audit"] == 3
    assert client.patch("/api/cases/TM-2026-417", json={"changes": {"status": "Closed"}}
                        ).json()["detail"] == "Choose the outcome to close the case."
    sign_in(client, "U-04")
    row = next(r for r in client.get("/api/cases").json() if r["case_id"] == "TM-2026-417")
    assert row["business_priority"] == "High" and row["consultation_required"] == 1
    sign_in(client, "U-10")
    assert client.patch("/api/cases/TM-2026-417", json={"changes": {"priority": "Low"}}).status_code == 403


def test_follow_up_lifecycle_and_notifications(client):
    sign_in(client, "U-08")
    made = client.post("/api/cases/TM-2026-417/follow-ups", json={
        "kind": "Compliance deadline", "title": "Store to remove infringing products", "start_date": "2026-10-06",
        "period_days": 30})
    assert made.status_code == 200, made.text
    fid = made.json()["follow_up_id"]
    sign_in(client, "U-07")
    inbox = client.get("/api/notifications").json()
    titles = [n["title"] for n in inbox["items"]]
    assert "Deadline reached: follow up and decide" in titles and inbox["unread"] >= 2
    reached = next(n for n in inbox["items"] if n["title"].startswith("Deadline reached"))
    assert reached["link"] == "/cases/TM-2026-417?tab=follow-ups" and reached["days_left"] == 0
    assert client.post("/api/notifications/read", json={"ids": [reached["id"]]}).json() == {"marked": 1}
    assert client.post("/api/notifications/read", json={}).json()["marked"] == inbox["unread"] - 1

    work = client.get("/api/follow-ups").json()
    assert any(i["id"] == fid and i["mine"] for i in work["items"])
    resolved = client.post(f"/api/follow-ups/{fid}/resolve", json={
        "decision": "close_case", "outcome": "Takedown achieved", "note": "Store visit: shelves clear"})
    assert resolved.status_code == 200 and resolved.json()["status"] == "Done"
    case = client.get("/api/cases/TM-2026-417").json()
    assert case["status"] == "Closed" and case["follow_ups"][0]["decision"] == "Complied – case closed"
    assert client.post(f"/api/follow-ups/{fid}/resolve", json={"decision": "keep_open"}).status_code == 409


def test_audit_trail_endpoint_and_csv(client):
    sign_in(client, "U-04")
    client.patch("/api/cases/TM-2026-424", json={"changes": {"risk_rating": "High"},
                                                 "reason": "Second report from the same seller"})
    upload(client, case_id="TM-2026-424", user="U-04")
    trail = client.get("/api/cases/TM-2026-424/audit").json()
    assert trail["integrity"]["ok"] and [e["action"] for e in trail["entries"]] == ["evidence.added", "case.updated"]
    assert trail["entries"][1]["changes"] == [{"field": "risk_rating", "label": "Risk rating", "old": "Low", "new": "High"}]
    assert trail["entries"][1]["actor_name"] == "Sara Haddad"
    got = client.get("/api/cases/TM-2026-424/audit.csv")
    assert got.headers["content-disposition"] == 'attachment; filename="TM-2026-424_audit_trail.csv"'
    assert got.text.startswith("﻿Entry,") and "Second report from the same seller" in got.text
    sign_in(client, "U-10")
    assert [e["action"] for e in client.get("/api/cases/TM-2026-424/audit").json()["entries"]] == ["case.updated"]
    sign_in(client, "U-05")
    assert client.get("/api/cases/TM-2026-424/audit").status_code == 404
