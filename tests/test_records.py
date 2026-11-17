"""Case records: case changes, the business-consultation gate, evidence, follow-ups, reminders and the audit trail."""
import csv
import io
import sqlite3
from contextlib import closing
from dataclasses import replace
from datetime import date

import pytest

from ferrero.casemodel import CaseModel
from ferrero.records import CaseRecords, RecordError
from ferrero.records import fields as cf
from ferrero.records.mailer import MailSettings

from conftest import DEMO_TODAY, PACK

JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF" + bytes(range(256)) * 8
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 600


@pytest.fixture
def model():  # a fresh model per test: the records lay their changes over it
    return CaseModel(PACK / "csv", DEMO_TODAY)


@pytest.fixture
def records(settings, model):
    return CaseRecords(settings, model)


@pytest.fixture
def people(model):
    return {name: model.principal(uid) for name, uid in
            {"ops": "U-08", "sara": "U-04", "youssef": "U-07", "omar": "U-05", "lina": "U-06", "procurement": "U-10",
             "head": "U-01"}.items()}


def unread(records, person):
    return [(n["title"], n["case_id"]) for n in records.notifications(person)["items"] if not n["read"]]


def sent_for(records, follow_up_id):
    """(recipient, stage) of every notification about one follow-up (the pack's own deadlines fire too)."""
    with records.store.read() as conn:
        return [(r["user_id"], r["stage"]) for r in conn.execute(
            "SELECT user_id, stage FROM notifications WHERE ref_id = ? ORDER BY seq", (follow_up_id,))]


def raw(records):
    return closing(sqlite3.connect(records.store.path, isolation_level=None))


# ---------- case fields ----------
def test_closing_a_case_fills_in_what_closing_implies(model, records, people):
    with pytest.raises(RecordError, match="outcome"):
        records.update_case(people["sara"], "TM-2026-424", {"status": "Closed"})
    diffs = records.update_case(people["sara"], "TM-2026-424", {"status": "Closed", "outcome": "Takedown achieved"},
                                reason="Listing removed by the marketplace")
    changed = {d["field"]: (d["old"], d["new"]) for d in diffs}
    assert changed["stage"] == ("Notice sent", "Closed") and changed["closed_date"] == (None, "2026-11-05")
    assert changed["next_action_due"] == ("2026-11-03", None)
    case = model.case_summary(people["ops"], "TM-2026-424")
    assert (case["status"], case["outcome"], case["days_open"]) == ("Closed", "Takedown achieved", 98)
    # pages, KPIs and the assistant read the same model
    assert model.query(people["ops"], "SELECT COUNT(*) FROM fact_case WHERE status = 'Open'")["rows"] == [[36]]
    entry = records.audit(people["sara"], "TM-2026-424")["entries"][0]
    assert entry["action"] == "case.closed" and entry["actor_name"] == "Sara Haddad" and entry["actor_role"] == "Legal-UAE"
    assert entry["reason"] == "Listing removed by the marketplace" and entry["at"].endswith("+00:00")


def test_reopening_needs_a_stage_and_open_cases_keep_pending(records, people):
    with pytest.raises(RecordError, match="reopened"):
        records.update_case(people["ops"], "TM-2024-428", {"status": "Open"})
    records.update_case(people["ops"], "TM-2024-428", {"status": "Open", "stage": "Appeal"})
    with pytest.raises(RecordError, match="Pending"):
        records.update_case(people["ops"], "TM-2024-428", {"outcome": "Won"})
    with pytest.raises(RecordError, match="can't be changed"):
        records.update_case(people["ops"], "TM-2024-428", {"claim_amount_aed": 1})


def test_who_may_change_what(records, people):
    with pytest.raises(RecordError) as e:
        records.update_case(people["procurement"], "TM-2026-424", {"priority": "Low"})
    assert e.value.status == 403
    with pytest.raises(RecordError) as e:  # a KSA lawyer can't see (so can't change) a UAE case
        records.update_case(people["omar"], "TM-2026-424", {"priority": "Low"})
    assert e.value.status == 404
    with pytest.raises(RecordError, match="owner"):  # owners must see the case: Omar is KSA-only
        records.update_case(people["sara"], "TM-2026-424", {"lead_counsel_id": "U-05"})
    records.update_case(people["sara"], "TM-2026-424", {"lead_counsel_id": "U-04"})
    assert records.model.visible_case(people["sara"], "TM-2026-424")["lead_counsel"] == "Sara Haddad"


# ---------- commercial sensitivity ----------
def test_business_assessment_and_the_enforcement_gate(model, records, people):
    records.update_case(people["youssef"], "TM-2026-417", {
        "business_priority": "High", "consultation_required": True, "commercial_relationship": "Customer"})
    case = model.case_summary(people["ops"], "TM-2026-417")
    assert (case["business_priority"], case["consultation_required"], case["consultation_status"]) == ("High", True, "Not started")
    assert records.audit(people["ops"], "TM-2026-417")["entries"][0]["action"] == "business.updated"

    with pytest.raises(RecordError) as e:  # starting enforcement before the business has cleared it
        records.update_case(people["youssef"], "TM-2026-417", {"stage": "Notice sent"})
    assert (e.value.status, e.value.code) == (409, "consultation_required")
    records.update_case(people["youssef"], "TM-2026-417", {"stage": "Investigation"})  # not enforcement: allowed

    records.update_case(people["youssef"], "TM-2026-417", {"stage": "Notice sent"}, override_reason="Health risk: act now")
    first, second = records.audit(people["ops"], "TM-2026-417")["entries"][:2]
    assert second["action"] == "business.override" and second["reason"] == "Health risk: act now"
    assert first["action"] == "case.updated"

    with pytest.raises(RecordError, match="required"):  # a status needs consultation to be required
        records.update_case(people["sara"], "TM-2026-424", {"consultation_status": "In progress"})
    rows = model.query(people["ops"], "SELECT case_id FROM fact_case WHERE consultation_required = 1")["rows"]
    assert rows == [["TM-2026-417"]]


def test_cleared_consultation_lets_enforcement_go_ahead(records, people):
    records.update_case(people["youssef"], "TM-2026-417", {"consultation_required": True})
    records.update_case(people["youssef"], "TM-2026-417", {"consultation_status": "Cleared to proceed",
                                                            "consultation_contact": "Commercial director, UAE"})
    assert records.update_case(people["youssef"], "TM-2026-417", {"stage": "Notice sent"})
    records.update_case(people["youssef"], "TM-2026-417", {"consultation_required": False})
    assert records.model.visible_case(people["ops"], "TM-2026-417")["consultation_status"] is None


def test_field_rules_refuse_inconsistent_changes():
    case = {"status": "Open", "stage": "Intake", "outcome": "Pending", "opened_date": "2026-05-11"}
    plan = cf.plan_update(case, {"status": "Closed", "outcome": "Settled"}, today=DEMO_TODAY, can_own=lambda _: True)
    assert plan.new["stage"] == "Settled" and plan.closing
    for change, message in [({"status": "Closed", "outcome": "Won", "closed_date": "2026-01-01"}, "before the case"),
                            ({"status": "Closed", "outcome": "Won", "closed_date": "2027-01-01"}, "future"),
                            ({"stage": "Closed"}, "status to Closed"), ({"next_action_due": "soon"}, "date"),
                            ({"priority": "Urgent"}, "one of"), ({"priority": ""}, "can't be empty")]:
        with pytest.raises(RecordError, match=message):
            cf.plan_update(case, change, today=DEMO_TODAY, can_own=lambda _: True)


# ---------- evidence ----------
def test_photo_upload_is_fingerprinted_and_audited(records, people):
    item = records.add_evidence(people["youssef"], "TM-2026-417", io.BytesIO(JPEG), "C:\\Users\\y\\IMG_0412.JPG",
                                {"category": "Product photo", "captured_on": "2026-11-04", "location": "Deira, Dubai",
                                 "notes": "Lookalike VELORA jars, shelf 3"})
    assert item["evidence_id"] == "EVD-00001" and item["file_name"] == "IMG_0412.JPG" and item["title"] == "IMG_0412"
    assert item["image"] and item["size_bytes"] == len(JPEG) and item["uploaded_by"] == "Youssef Nasser"
    path, kind, name = records.evidence_file(people["sara"], "EVD-00001")
    assert path.read_bytes() == JPEG and kind.inline and path.name == item["sha256"]
    assert records.verify_evidence(people["sara"], "EVD-00001")["ok"]
    entry = records.audit(people["sara"], "TM-2026-417")["entries"][0]
    assert entry["action"] == "evidence.added" and entry["ref_id"] == "EVD-00001"
    assert {"field": "sha256", "label": "SHA-256 fingerprint", "old": None, "new": item["sha256"]} in entry["changes"]
    # the case model and the assistant see it (metadata only)
    assert records.model.case_summary(people["ops"], "TM-2026-417")["evidence_on_file"][0]["category"] == "Product photo"


@pytest.mark.parametrize("name, data, message", [
    ("shelf.jpg", b"<html><script>alert(1)</script>", "isn't a real JPEG"),
    ("shelf.svg", b"<svg/>", "can't be added"),
    ("notes.exe", b"MZ\x90\x00", "can't be added"),
    ("empty.png", b"", "empty"),
])
def test_files_that_are_not_what_they_claim_are_refused(records, people, name, data, message):
    with pytest.raises(RecordError, match=message):
        records.add_evidence(people["sara"], "TM-2026-424", io.BytesIO(data), name, {"category": "Screenshot"})


def test_evidence_limits_and_access(settings, model, records, people):
    records.add_evidence(people["sara"], "TM-2026-424", io.BytesIO(PNG), "listing.png", {"category": "Screenshot"})
    with pytest.raises(RecordError, match="already on file") as e:
        records.add_evidence(people["sara"], "TM-2026-424", io.BytesIO(PNG), "copy.png", {"category": "Screenshot"})
    assert e.value.status == 409
    small = CaseRecords(replace(settings, evidence_max_mb=1), model)
    with pytest.raises(RecordError, match="larger than 1 MB"):
        small.add_evidence(people["sara"], "TM-2026-424", io.BytesIO(PNG + b"\0" * (1 << 20)), "big.png",
                           {"category": "Screenshot"})
    with pytest.raises(RecordError, match="category"):
        records.add_evidence(people["sara"], "TM-2026-424", io.BytesIO(PNG), "x.png", {"category": "Selfie"})
    for who in ("procurement", "omar"):  # no documents for Procurement; KSA can't see a UAE case
        with pytest.raises(RecordError) as e:
            records.list_evidence(people[who], "TM-2026-424")
        assert e.value.status in (403, 404)
    with pytest.raises(RecordError):
        records.evidence_file(people["omar"], "EVD-00001")
    assert model.query(people["procurement"], "SELECT COUNT(*) FROM case_audit")["rows"] == [[0]]  # evidence entries hidden


def test_withdrawn_evidence_is_kept_with_the_reason(records, people):
    records.add_evidence(people["sara"], "TM-2026-424", io.BytesIO(PNG), "listing.png", {"category": "Screenshot"})
    with pytest.raises(RecordError, match="reason"):
        records.withdraw_evidence(people["sara"], "EVD-00001", "")
    item = records.withdraw_evidence(people["sara"], "EVD-00001", "Wrong listing: belongs to TM-2026-427")
    assert item["status"] == "Withdrawn" and item["withdrawn_by"] == "Sara Haddad"
    assert records.evidence_file(people["sara"], "EVD-00001")[0].is_file()  # the file stays
    with raw(records) as conn, pytest.raises(sqlite3.DatabaseError, match="never deleted"):
        conn.execute("DELETE FROM evidence")
    updated = records.add_evidence(people["sara"], "TM-2026-424", io.BytesIO(PNG), "listing.png", {"category": "Screenshot"})
    assert updated["evidence_id"] == "EVD-00002"  # a withdrawn file can be added again


# ---------- follow-ups and reminders ----------
def test_deadline_reached_notifies_the_owner_to_decide(model, records, people):
    # The store was given 30 days on 6 October: the deadline is today, so the case owner hears now.
    fu = records.create_follow_up(people["ops"], "TM-2026-417", {
        "kind": "Compliance deadline", "title": "Store to remove infringing products", "start_date": "2026-10-06",
        "period_days": 30})
    assert (fu["due_date"], fu["owner_id"], fu["days_left"]) == ("2026-11-05", "U-07", 0)
    titles = unread(records, people["youssef"])
    assert ("Deadline reached: follow up and decide", "TM-2026-417") in titles
    assert ("Follow-up assigned to you", "TM-2026-417") in titles
    assert ("Deadline reached: follow up and decide", "TM-2026-417") in unread(records, people["ops"])  # who set it

    done = records.resolve_follow_up(people["youssef"], fu["follow_up_id"],
                                     {"decision": "close_case", "outcome": "Takedown achieved", "note": "Shelves cleared"})
    assert done["status"] == "Done" and done["decision_label"] == "Complied – case closed"
    # the decision is made and the case closed: those reminders are no longer news, for anyone they went to
    assert not any(c == "TM-2026-417" for _, c in unread(records, people["youssef"]))
    assert not any(c == "TM-2026-417" for _, c in unread(records, people["ops"]))
    case = model.visible_case(people["ops"], "TM-2026-417")
    assert (case["status"], case["outcome"], case["closed_date"]) == ("Closed", "Takedown achieved", "2026-11-05")
    actions = [e["action"] for e in records.audit(people["ops"], "TM-2026-417")["entries"]]
    assert actions[:3] == ["case.closed", "follow_up.resolved", "follow_up.created"]


def test_extending_a_deadline_needs_a_reason_and_resets_the_reminders(records, people):
    fu = records.create_follow_up(people["sara"], "TM-2026-424", {
        "kind": "Response deadline", "title": "Reply to cease-and-desist", "start_date": "2026-10-20", "due_date": "2026-11-03"})
    assert fu["period_days"] == 14 and fu["owner_id"] == "U-07"
    with pytest.raises(RecordError, match="why"):
        records.update_follow_up(people["sara"], fu["follow_up_id"], {"due_date": "2026-11-20"})
    moved = records.update_follow_up(people["sara"], fu["follow_up_id"], {"due_date": "2026-11-20"},
                                     reason="Infringer's counsel asked for two more weeks")
    assert moved["period_days"] == 31
    assert records.audit(people["sara"], "TM-2026-424")["entries"][0]["action"] == "follow_up.extended"
    records.run_reminders(date(2026, 11, 13))  # "due soon" again, for the new date
    assert sent_for(records, fu["follow_up_id"])[-1] == ("U-07", "upcoming")
    with pytest.raises(RecordError, match="note"):
        records.resolve_follow_up(people["sara"], fu["follow_up_id"], {"decision": "escalate"})
    records.resolve_follow_up(people["sara"], fu["follow_up_id"], {
        "decision": "escalate", "note": "No reply", "case_changes": {"next_action": "File statement of claim",
                                                                    "next_action_due": "2026-12-01"}})
    case = records.model.visible_case(people["sara"], "TM-2026-424")
    assert (case["status"], case["next_action"]) == ("Open", "File statement of claim")


def test_reminders_follow_the_deadline_stages_once_each(records, people):
    fu = records.create_follow_up(people["lina"], "TM-2026-412", {
        "kind": "Internal follow-up", "title": "Check customs register", "due_date": "2026-11-20", "remind_days": 7})
    fid = fu["follow_up_id"]
    for day in (12, 13, 13, 19, 20, 22):
        records.run_reminders(date(2026, 11, day))
    assert sent_for(records, fid) == [("U-06", "upcoming"), ("U-06", "due")]  # once each; Lina set it herself
    records.run_reminders(date(2026, 11, 23))  # three days late: escalated to Legal-Ops as well
    assert sent_for(records, fid)[2:] == [("U-06", "overdue"), ("U-08", "overdue")]
    assert ("Overdue: decision still needed", "TM-2026-412") in unread(records, people["ops"])
    records.resolve_follow_up(people["lina"], fid, {"decision": "cancel", "note": "Not needed"})
    records.run_reminders(date(2026, 11, 30))
    assert len(sent_for(records, fid)) == 4


def test_case_tracker_deadlines_reach_their_owners(records, people):
    records.run_reminders()
    assert set(unread(records, people["omar"])) == {("Next action due soon", "TM-2024-435"),
                                                   ("Next action overdue", "TM-2026-425")}
    lina = unread(records, people["lina"])
    assert ("Hearing coming up", "TM-2026-412") in lina and ("Next action overdue", "TM-2026-430") in lina
    assert {c for _, c in unread(records, people["ops"])} == {"TM-2026-425", "TM-2026-430", "TM-2026-402"}  # escalated
    assert unread(records, people["procurement"]) == []
    # TM-2026-402 is an India case whose lead counsel is in Legal-UAE: never told about a case they can't open
    assert all(c != "TM-2026-402" for _, c in unread(records, records.model.principal("U-03")))
    assert records.mark_read(people["omar"]) == 2 and records.notifications(people["omar"])["unread"] == 0


def test_moving_a_deadline_clears_reminders_about_the_old_date(records, people):
    records.run_reminders()
    assert ("Next action overdue", "TM-2026-425") in unread(records, people["omar"])
    records.update_case(people["omar"], "TM-2026-425", {"next_action_due": "2026-11-20"}, reason="Test purchase rebooked")
    assert ("Next action overdue", "TM-2026-425") not in unread(records, people["omar"])
    assert ("Next action overdue", "TM-2026-425") not in unread(records, people["ops"])  # the escalation too
    assert ("Next action due soon", "TM-2024-435") in unread(records, people["omar"])  # other cases untouched


def test_worklist_lists_every_open_deadline(records, people):
    records.create_follow_up(people["sara"], "TM-2026-424", {
        "kind": "Compliance deadline", "title": "Remove listings", "period_days": 30, "owner_id": "U-04"})
    work = records.worklist(people["sara"])
    kinds = {(i["type"], i["case_id"]) for i in work["items"]}
    assert ("follow_up", "TM-2026-424") in kinds and ("next_action", "TM-2026-424") in kinds
    assert all(i["case_id"].startswith("TM-") for i in work["items"])
    assert [i for i in work["items"] if i["type"] == "follow_up"][0]["mine"] is True
    assert {i["case_id"] for i in records.worklist(people["omar"])["items"]} <= {
        c["case_id"] for c in records.model.visible_cases(people["omar"])}


def test_reminders_are_emailed_once_per_recipient(settings, model, people):
    class FakeMailer:
        settings = MailSettings("smtp.test", 587, "ferrero@test", redirect_to=None, public_url="http://ferrero.test")
        sent: list = []

        def send(self, to, subject, text):
            self.sent.append((to, subject, text))

    mailer = FakeMailer()
    records = CaseRecords(settings, model, mailer=mailer)
    records.run_reminders()
    assert records.deliver_email() > 0 and records.deliver_email() == 0
    to = {t for t, _, _ in mailer.sent}
    assert "omar.alqahtani@demo.local" in to and len(to) == len(mailer.sent)
    omar = next(text for t, _, text in mailer.sent if t.startswith("omar"))
    assert "TM-2026-425" in omar and "http://ferrero.test/cases/TM-2026-425" in omar


# ---------- the audit trail ----------
def test_audit_trail_is_append_only_and_tamper_evident(records, people):
    records.update_case(people["sara"], "TM-2026-424", {"priority": "High"})
    records.update_case(people["sara"], "TM-2026-424", {"business_priority": "Low"})
    records.update_case(people["sara"], "TM-2026-424", {"risk_rating": "High"})
    found = records.store.verify_chain()
    assert found["ok"] and found["entries"] == 3
    with raw(records) as conn:
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            conn.execute("UPDATE audit_log SET actor_name = 'Someone else' WHERE seq = 2")
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            conn.execute("DELETE FROM audit_log WHERE seq = 3")
        # someone with the database file in hand drops the guard and edits an entry: the chain shows it
        conn.execute("DROP TRIGGER audit_log_no_update")
        conn.execute("UPDATE audit_log SET summary = 'Legal priority: Medium → Low' WHERE seq = 1")
    found = records.store.verify_chain()
    assert not found["ok"] and found["first_bad"] == "AUD-000001" and "changed" in found["problem"]


def test_removing_the_latest_audit_entry_is_detected(records, people):
    records.update_case(people["sara"], "TM-2026-424", {"priority": "High"})
    records.update_case(people["sara"], "TM-2026-424", {"priority": "Low"})
    with raw(records) as conn:
        conn.execute("DROP TRIGGER audit_log_no_delete")
        conn.execute("DELETE FROM audit_log WHERE seq = 2")
    found = records.store.verify_chain()
    assert not found["ok"] and "missing" in found["problem"]


def test_audit_csv_has_one_row_per_change(records, people):
    records.update_case(people["sara"], "TM-2026-424", {"priority": "High", "business_priority": "High"},
                        reason="Repeat infringer")
    header, *rows = list(csv.reader(io.StringIO(records.audit_csv(people["sara"], "TM-2026-424"))))
    assert header[:3] == ["Entry", "When (UTC)", "Who"] and len(rows) == 2
    assert [r[6:10] for r in rows] == [["Legal priority", "Low", "High", "Repeat infringer"],
                                       ["Business priority", "–", "High", "Repeat infringer"]]


def test_changes_survive_a_restart(settings, records, people):
    records.update_case(people["sara"], "TM-2026-424", {"business_priority": "High"})
    fresh = CaseModel(PACK / "csv", DEMO_TODAY)
    CaseRecords(settings, fresh)
    assert fresh.visible_case(people["ops"], "TM-2026-424")["business_priority"] == "High"
