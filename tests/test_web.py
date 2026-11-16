import json

from fastapi.testclient import TestClient

from ferrero.assistant.agent import Assistant
from ferrero.web.app import create_app

from conftest import message, text, thinking, tool_use


def client_for(settings, model, index, fake_claude):
    return TestClient(create_app(settings, Assistant(settings, model, index, client=fake_claude.client())))


def events(response):
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


def test_page_and_metadata(settings, model, index, fake_claude):
    c = client_for(settings, model, index, fake_claude)
    assert "Ferrero" in c.get("/").text
    assert c.get("/static/app.js").status_code == 200
    meta = c.get("/api/meta").json()
    assert meta["index"]["indexed"] == 12 and meta["demo_today"] == "2026-11-05"
    users = c.get("/api/users").json()
    assert len(users) == 10 and all("email" not in u for u in users)


def test_conversation_streams_steps_then_answer(settings, model, index, fake_claude):
    fake_claude.responses = [
        message([thinking(), tool_use("query_case_data", {"sql": "SELECT COUNT(*) FROM fact_case WHERE status='Open' AND country='KSA'"})],
                stop_reason="tool_use"),
        message([thinking(), text("9 open cases in KSA (case tracker).")]),
    ]
    c = client_for(settings, model, index, fake_claude)
    conv = c.post("/api/conversations", json={"user_id": "U-08"}).json()
    r = c.post(f"/api/conversations/{conv['conversation_id']}/messages", json={"text": "How many open cases in KSA?"})
    assert r.headers["content-type"].startswith("text/event-stream")
    got = events(r)
    assert [e["type"] for e in got] == ["tool", "answer", "done"]
    assert got[1]["route"] == ["case_data"] and got[1]["tools"][0]["summary"] == "Queried case data (1 rows)"


def test_case_focus_and_documents_respect_access(settings, model, index, fake_claude):
    c = client_for(settings, model, index, fake_claude)
    ksa = c.post("/api/conversations", json={"user_id": "U-05", "case_id": "tm-2024-428"}).json()
    assert ksa["case"] is None and ksa["case_requested"] == "TM-2024-428"
    uae = c.post("/api/conversations", json={"user_id": "U-04", "case_id": "TM-2024-428"}).json()
    assert uae["case"]["title"] == "VELORA v. Zahrat Al Sahra Trading"
    assert c.get("/api/documents/TM-2024-428_Judgment_EN.docx", params={"user_id": "U-05"}).status_code == 404
    doc = c.get("/api/documents/TM-2024-428_Judgment_EN.docx", params={"user_id": "U-04"}).json()
    assert doc["sections"][0]["section"] == "Header"
    assert c.get("/api/cases/TM-2024-428", params={"user_id": "U-05"}).status_code == 404


def test_overview_matches_the_dashboard_measures(settings, model, index, fake_claude):
    c = client_for(settings, model, index, fake_claude)
    k = c.get("/api/overview", params={"user_id": "U-08"}).json()["kpis"]
    assert (k["open_cases"], k["hearings_30d"], k["overdue_actions"], k["closed_ytd"], k["new_cases_30d"]) == (37, 8, 4, 28, 2)
    assert round(k["recovery_rate"], 3) == 0.641 and k["win_rate"] == 0.88
    assert (k["claimed"], k["legal_spend"]) == (152193967, 5826000)
    ksa = c.get("/api/overview", params={"user_id": "U-05"}).json()
    assert ksa["kpis"]["cases"] == 23 and ksa["kpis"]["open_cases"] == 9
    assert ksa["filters"]["countries"] == ["KSA"]
    velora_uae = c.get("/api/overview", params={"user_id": "U-08", "country": "UAE", "mark": "MK-01"}).json()["kpis"]
    assert 0 < velora_uae["cases"] < 54


def test_case_list_detail_and_sync_status_are_scoped(settings, model, index, fake_claude):
    c = client_for(settings, model, index, fake_claude)
    cases = c.get("/api/cases", params={"user_id": "U-05"}).json()
    assert len(cases) == 23 and {r["country"] for r in cases} == {"KSA"}
    detail = c.get("/api/cases/TM-2024-428", params={"user_id": "U-04"}).json()
    assert detail["awarded_amount_local"] == 2288000
    assert any(d["text_searchable"] for d in detail["documents_on_file"])
    ksa_docs = c.get("/api/sync", params={"user_id": "U-05"}).json()
    assert {d["case_id"] for d in ksa_docs["documents"]} == {"TM-2024-403", "TM-2024-438"}
    assert c.get("/api/sync", params={"user_id": "U-10"}).json() == {"documents": [], "counts": {}, "visible": False}


def test_errors_are_reported_in_the_stream(settings, model, index, fake_claude):
    fake_claude.responses = [("status", 529)]
    c = client_for(settings, model, index, fake_claude)
    conv = c.post("/api/conversations", json={"user_id": "U-08"}).json()
    got = events(c.post(f"/api/conversations/{conv['conversation_id']}/messages", json={"text": "Hi"}))
    assert got[0]["type"] == "error" and got[-1]["type"] == "done"
    assert got[0]["message"] == "Ferrero couldn't answer just now. Please try again in a moment."  # no technical detail
    assert "529" not in got[0]["message"]
    assert c.post("/api/conversations/nope/messages", json={"text": "Hi"}).status_code == 404
    assert c.post("/api/conversations", json={"user_id": "admin"}).status_code == 422
