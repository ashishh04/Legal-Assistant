"""The case workflow: register, assign, follow up and close; and the visual trademark comparison."""
import pytest

from ferrero.casemodel import CaseModel
from ferrero.records import CaseRecords, RecordError
from ferrero.records.similarity import compare, phonetic_key

from conftest import DEMO_TODAY, PACK

JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF" + bytes(range(256)) * 8
NEW_CASE = {"mark_id": "MK-01", "infringer_name": "Golden Spoon Sweets", "infringer_type": "Retailer",
            "infringer_city": "Amman", "case_type": "Trademark infringement – counterfeit goods", "country": "Jordan",
            "source_channel": "Distributor report", "priority": "High", "next_action": "Arrange a test purchase",
            "next_action_due": "2026-11-12", "claim_amount_local": 1000, "details": "Reported by our Jordan distributor."}


@pytest.fixture
def model():
    return CaseModel(PACK / "csv", DEMO_TODAY)


@pytest.fixture
def records(settings, model):
    return CaseRecords(settings, model)


@pytest.fixture
def people(model):
    return {name: model.principal(uid) for name, uid in
            {"ops": "U-08", "sara": "U-04", "omar": "U-05", "lina": "U-06", "khalid": "U-03", "procurement": "U-10"}.items()}


def unread(records, person):
    return [(n["title"], n["case_id"]) for n in records.notifications(person)["items"] if not n["read"]]


def test_registering_a_case_numbers_it_and_lays_it_over_the_tracker(model, records, people):
    found = records.register_case(people["lina"], NEW_CASE)
    cid = found["case_id"]
    assert cid == "TM-2026-435"  # after the tracker's last 2026 case, TM-2026-434
    case = model.visible_case(people["lina"], cid)
    assert case["title"] == "VELORA v. Golden Spoon Sweets"
    assert (case["status"], case["stage"], case["outcome"]) == ("Open", "Intake", "Pending")
    assert (case["access_group"], case["currency"], case["claim_amount_aed"]) == ("Legal-MENA", "JOD", 5180)
    assert case["lead_counsel_id"] == "U-06" and case["lead_counsel"] == "Lina Mansour"  # the registrant by default
    assert case["sharepoint_library"] == f"/sites/Legal/Cases/Jordan/{cid}"
    new_infringer = next(i for i in model.infringers() if i["infringer_name_en"] == "Golden Spoon Sweets")
    assert new_infringer["infringer_id"] == "INF-046" and case["infringer_id"] == "INF-046"
    # the assistant's SQL, the case list and the case page all see it
    rows = model.query(people["lina"], f"SELECT title, stage FROM fact_case WHERE case_id = '{cid}'")["rows"]
    assert rows == [["VELORA v. Golden Spoon Sweets", "Intake"]]
    joined = model.query(people["lina"], f"SELECT i.city FROM fact_case c JOIN dim_infringer i USING (infringer_id) "
                                         f"WHERE c.case_id = '{cid}'")["rows"]
    assert joined == [["Amman"]]
    assert model.visible_case(people["sara"], cid) is None  # UAE counsel can't see a Jordan case
    entry = records.audit(people["lina"], cid)["entries"][0]
    assert entry["action"] == "case.registered" and entry["reason"] == "Reported by our Jordan distributor."
    assert {c["label"] for c in entry["changes"]} >= {"Mark", "Infringer", "Country", "Case owner", "Next action due"}
    # the next one gets the next number; a known infringer is reused rather than duplicated
    again = records.register_case(people["ops"], {**NEW_CASE, "infringer_name": "golden spoon sweets",
                                                  "lead_counsel_id": "U-06"})
    assert again["case_id"] == "TM-2026-436"
    assert model.case(again["case_id"])["infringer_id"] == "INF-046"


def test_registration_checks_role_country_owner_and_details(records, people):
    with pytest.raises(RecordError, match="can see cases but not change"):
        records.register_case(people["procurement"], NEW_CASE)
    with pytest.raises(RecordError, match="doesn't cover Jordan") as e:
        records.register_case(people["sara"], NEW_CASE)
    assert e.value.status == 403
    with pytest.raises(RecordError, match="legal team who covers Jordan"):
        records.register_case(people["ops"], {**NEW_CASE, "lead_counsel_id": "U-04"})  # Sara covers the UAE
    with pytest.raises(RecordError, match="mark"):
        records.register_case(people["lina"], {**NEW_CASE, "mark_id": "MK-99"})
    with pytest.raises(RecordError, match="future"):
        records.register_case(people["lina"], {**NEW_CASE, "opened_date": "2026-12-01"})
    with pytest.raises(RecordError, match="court in Jordan"):
        records.register_case(people["lina"], {**NEW_CASE, "court_id": "CT-01"})  # a Dubai court
    with pytest.raises(RecordError, match="infringer's name"):
        records.register_case(people["lina"], {**NEW_CASE, "infringer_name": ""})
    options = records.register_options(people["sara"])
    assert [c["country"] for c in options["countries"]] == ["UAE"]
    assert all(c["country"] == "UAE" for c in options["courts"]) and options["infringers"]


def test_assigning_a_case_tells_the_new_owner(records, people):
    found = records.register_case(people["ops"], {**NEW_CASE, "lead_counsel_id": "U-06"})
    assert ("Case assigned to you", found["case_id"]) in unread(records, people["lina"])
    records.update_case(people["ops"], "TM-2026-421", {"lead_counsel_id": "U-03"}, reason="Workload")
    assert ("Case assigned to you", "TM-2026-421") in unread(records, people["khalid"])
    records.update_case(people["khalid"], "TM-2026-421", {"lead_counsel_id": "U-03", "priority": "High"})
    assert sum(1 for n in unread(records, people["khalid"]) if n == ("Case assigned to you", "TM-2026-421")) == 1


def test_a_registered_case_follows_the_workflow_to_closure(model, records, people):
    cid = records.register_case(people["lina"], NEW_CASE)["case_id"]
    records.update_case(people["lina"], cid, {"stage": "Investigation"})
    fu = records.create_follow_up(people["lina"], cid, {"kind": "Compliance deadline", "title": "Remove the stock",
                                                        "start_date": "2026-11-01", "period_days": 4})
    records.resolve_follow_up(people["lina"], fu["follow_up_id"], {"decision": "close_case", "outcome": "Takedown achieved"})
    case = model.case(cid)
    assert (case["status"], case["stage"], case["outcome"]) == ("Closed", "Closed", "Takedown achieved")
    actions = [e["action"] for e in records.audit(people["lina"], cid)["entries"]]
    assert actions == ["case.closed", "follow_up.resolved", "follow_up.created", "case.updated", "case.registered"]
    assert records.store.verify_chain()["ok"]


def test_similarity_indicators():
    found = compare("VELORA", "فيلورا", "VELLORA")
    assert (found["letters_different"], found["sounds_alike"], found["indication"]) == (1, True, "High")
    assert found["word_similarity"] == 0.86
    assert compare("VELORA", "فيلورا", "فيلوورا")["compared_with"] == "فيلورا"  # Arabic signs against the Arabic name
    assert compare("MINTIQ", None, "OCEANIC")["indication"] == "Low"
    assert compare("CRISPINO", None, "Krispino")["sounds_alike"]
    assert phonetic_key("PICCOLINI") == phonetic_key("Pikolini")
    assert compare("AURELIA", None, "")["indication"] is None


def test_recording_a_comparison_supersedes_and_audits(records, people):
    photo = records.add_evidence(people["omar"], "TM-2024-435", __import__("io").BytesIO(JPEG), "shelf.jpg",
                                 {"category": "Product photo"})
    first = records.record_comparison(people["omar"], "TM-2024-435", {
        "infringing_sign": "VELLORA", "evidence_id": photo["evidence_id"], "visual": "High", "phonetic": "High",
        "conceptual": "Medium", "goods": "Identical", "overall": "High", "notes": "Same oval label and colours."})
    current = first["current"]
    assert current["comparison_id"] == "CMP-00001" and current["word_similarity"] == 0.86 and current["sounds_alike"]
    assert first["mark"]["mark_name"] == "VELORA" and first["indicators"]["indication"] == "High"
    assert [p["evidence_id"] for p in first["photos"]] == [photo["evidence_id"]]
    second = records.record_comparison(people["omar"], "TM-2024-435", {
        "infringing_sign": "VELLORA", "evidence_id": photo["evidence_id"], "visual": "High", "phonetic": "High",
        "conceptual": "High", "goods": "Identical", "overall": "High"})
    assert [h["status"] for h in second["history"]] == ["Current", "Superseded"]
    entry = records.audit(people["omar"], "TM-2024-435")["entries"][0]
    assert entry["action"] == "comparison.recorded" and entry["ref_id"] == "CMP-00002"
    assert {c["field"] for c in entry["changes"]} == {"conceptual", "notes"}
    # the assistant's case view carries the current assessment
    assert records.model.case_summary(people["omar"], "TM-2024-435")["mark_comparison"]["conceptual"] == "High"
    # procurement sees the assessment but no photos, and can't record one
    seen = records.comparison(people["procurement"], "TM-2024-435")
    assert seen["photos"] is None and seen["current"]["overall"] == "High" and not seen["can_record"]
    with pytest.raises(RecordError):
        records.record_comparison(people["procurement"], "TM-2024-435", {"infringing_sign": "X"})
    with pytest.raises(RecordError, match="likelihood of confusion"):
        records.record_comparison(people["omar"], "TM-2024-435", {
            "infringing_sign": "VELLORA", "visual": "High", "phonetic": "High", "conceptual": "High", "goods": "Identical"})
    with pytest.raises(RecordError, match="photo that is on file"):
        records.record_comparison(people["omar"], "TM-2024-435", {
            "infringing_sign": "VELLORA", "evidence_id": "EVD-00099", "visual": "High", "phonetic": "High",
            "conceptual": "High", "goods": "Identical", "overall": "High"})
