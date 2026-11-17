"""Registering a case and the visual trademark comparison over HTTP."""
import pytest
from fastapi.testclient import TestClient

from ferrero.assistant.agent import Assistant
from ferrero.casemodel import CaseModel
from ferrero.web.app import create_app

from conftest import DEMO_TODAY, PACK, sign_in
from test_workflow import NEW_CASE


@pytest.fixture
def client(settings, index, fake_claude):
    fresh = CaseModel(PACK / "csv", DEMO_TODAY)
    with TestClient(create_app(settings, Assistant(settings, fresh, index, client=fake_claude.client()))) as c:
        yield c


def test_register_and_compare_over_http(client):
    sign_in(client, "U-06")
    options = client.get("/api/register/options").json()
    assert {"marks", "case_types", "countries", "courts", "infringers"} <= set(options)
    r = client.post("/api/cases", json=NEW_CASE)
    assert r.status_code == 200, r.text
    body = r.json()
    cid = body["case_id"]
    assert body["case"]["case_id"] == cid and body["case"]["stage"] == "Intake" and body["case"]["mark_id"] == "MK-01"
    assert body["case"]["registered_in_app"] is True  # not in the tracker the dashboards read
    assert client.get("/api/cases/TM-2026-430").json()["registered_in_app"] is False
    assert any(row["case_id"] == cid for row in client.get("/api/cases").json())
    assert client.post("/api/cases", json={**NEW_CASE, "country": "UAE"}).status_code == 403

    marks = client.get("/api/marks").json()
    assert len(marks) == 6 and all(m["specimen"] for m in marks)
    img = client.get("/api/marks/MK-01/specimen")
    assert img.status_code == 200 and img.headers["content-type"] == "image/png"
    assert client.get("/api/marks/../specimen").status_code == 404
    assert client.get("/api/marks/MK-01/similarity", params={"sign": "Vellora"}).json()["indication"] == "High"
    empty = client.get(f"/api/cases/{cid}/comparison").json()
    assert empty["current"] is None and empty["mark"]["registration_no"] == "UAE-TM-284517" and empty["photos"] == []
    saved = client.post(f"/api/cases/{cid}/comparison", json={
        "infringing_sign": "VELLORA", "visual": "High", "phonetic": "High", "conceptual": "Medium",
        "goods": "Identical", "overall": "High"}).json()
    assert saved["current"]["overall"] == "High" and saved["mark"]["specimen"]
    sign_in(client, "U-04")  # Sara (UAE) can't see the Jordan case
    assert client.get(f"/api/cases/{cid}/comparison").status_code == 404
