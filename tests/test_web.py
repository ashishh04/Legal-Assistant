import json

from fastapi.testclient import TestClient

from ferrero.assistant.agent import Assistant
from ferrero.web.app import create_app

from conftest import message, sign_in, text, thinking, tool_use


def client_for(settings, model, index, fake_claude):
    return TestClient(create_app(settings, Assistant(settings, model, index, client=fake_claude.client())))


def events(response):
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


def test_page_and_metadata(settings, model, index, fake_claude):
    c = client_for(settings, model, index, fake_claude)
    assert "Ferrero" in c.get("/").text and "Ferrero" in c.get("/login").text  # the app's own pages are public
    assert c.get("/static/app.js").status_code == 200
    assert c.get("/api/meta").status_code == 401  # everything else needs a session
    public = c.get("/api/public").json()
    assert public["sign_in_configured"] and public["accounts"] is None  # no account list unless switched on
    sign_in(c, "U-08")
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
    c = sign_in(client_for(settings, model, index, fake_claude), "U-08")
    conv = c.post("/api/conversations", json={}).json()
    assert conv["user"]["user_id"] == "U-08"
    r = c.post(f"/api/conversations/{conv['conversation_id']}/messages", json={"text": "How many open cases in KSA?"})
    assert r.headers["content-type"].startswith("text/event-stream")
    got = events(r)
    assert [e["type"] for e in got] == ["tool", "answer", "done"]
    assert got[1]["route"] == ["case_data"] and got[1]["tools"][0]["summary"] == "Queried case data (1 rows)"


def test_case_focus_and_documents_respect_access(settings, model, index, fake_claude):
    c = sign_in(client_for(settings, model, index, fake_claude), "U-05")
    ksa = c.post("/api/conversations", json={"case_id": "tm-2024-428"}).json()
    assert ksa["case"] is None and ksa["case_requested"] == "TM-2024-428"
    assert c.get("/api/documents/TM-2024-428_Judgment_EN.docx").status_code == 404
    assert c.get("/api/cases/TM-2024-428").status_code == 404
    sign_in(c, "U-04")
    uae = c.post("/api/conversations", json={"case_id": "TM-2024-428"}).json()
    assert uae["case"]["title"] == "VELORA v. Zahrat Al Sahra Trading"
    doc = c.get("/api/documents/TM-2024-428_Judgment_EN.docx").json()
    assert doc["sections"][0]["section"] == "Header"


def test_a_conversation_belongs_to_whoever_started_it(settings, model, index, fake_claude):
    c = sign_in(client_for(settings, model, index, fake_claude), "U-08")
    conv = c.post("/api/conversations", json={}).json()
    sign_in(c, "U-05")  # someone else, holding the id, can't continue it as the first user
    assert c.post(f"/api/conversations/{conv['conversation_id']}/messages", json={"text": "Hi"}).status_code == 404


def test_overview_matches_the_dashboard_measures(settings, model, index, fake_claude):
    c = sign_in(client_for(settings, model, index, fake_claude), "U-08")
    k = c.get("/api/overview").json()["kpis"]
    assert (k["open_cases"], k["hearings_30d"], k["overdue_actions"], k["closed_ytd"], k["new_cases_30d"]) == (37, 8, 4, 28, 2)
    assert round(k["recovery_rate"], 3) == 0.641 and k["win_rate"] == 0.88
    assert (k["claimed"], k["legal_spend"]) == (152193967, 5826000)
    velora_uae = c.get("/api/overview", params={"country": "UAE", "mark": "MK-01"}).json()["kpis"]
    assert 0 < velora_uae["cases"] < 54
    sign_in(c, "U-05")
    ksa = c.get("/api/overview").json()
    assert ksa["kpis"]["cases"] == 23 and ksa["kpis"]["open_cases"] == 9
    assert ksa["filters"]["countries"] == ["KSA"]


def test_case_list_detail_and_sync_status_are_scoped(settings, model, index, fake_claude):
    c = sign_in(client_for(settings, model, index, fake_claude), "U-05")
    cases = c.get("/api/cases", params={"user_id": "U-08"}).json()  # a user_id in the request changes nothing
    assert len(cases) == 23 and {r["country"] for r in cases} == {"KSA"}
    ksa_docs = c.get("/api/sync").json()
    assert {d["case_id"] for d in ksa_docs["documents"]} == {"TM-2024-403", "TM-2024-438"}
    sign_in(c, "U-04")
    detail = c.get("/api/cases/TM-2024-428").json()
    assert detail["awarded_amount_local"] == 2288000
    assert any(d["text_searchable"] for d in detail["documents_on_file"])
    sign_in(c, "U-10")
    assert c.get("/api/sync").json() == {"documents": [], "counts": {}, "visible": False}


def test_errors_are_reported_in_the_stream(settings, model, index, fake_claude):
    fake_claude.responses = [("status", 529)]
    c = sign_in(client_for(settings, model, index, fake_claude), "U-08")
    conv = c.post("/api/conversations", json={}).json()
    got = events(c.post(f"/api/conversations/{conv['conversation_id']}/messages", json={"text": "Hi"}))
    assert got[0]["type"] == "error" and got[-1]["type"] == "done"
    assert got[0]["message"] == "Ferrero couldn't answer just now. Please try again in a moment."  # no technical detail
    assert "529" not in got[0]["message"]
    assert c.post("/api/conversations/nope/messages", json={"text": "Hi"}).status_code == 404
    assert c.post("/api/conversations", json={"case_id": "admin"}).status_code == 422
