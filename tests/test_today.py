"""The app's date: the real calendar, moving on while the app runs; fixed only when a date is configured."""
from dataclasses import replace
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from ferrero.assistant.agent import Assistant
from ferrero.casemodel import CaseModel
from ferrero.config import Settings, get_settings
from ferrero.eval.cli import GOLDEN_TODAY, evaluation_day
from ferrero.records.service import CaseRecords
from ferrero.web.app import create_app

from conftest import DEMO_TODAY, PACK, message, sign_in, text, thinking

OVERDUE = "SELECT COUNT(*) FROM fact_case WHERE status = 'Open' AND next_action_due < reporting_date()"


class Calendar:
    """A calendar the test can turn."""

    def __init__(self, day: date) -> None:
        self.day = day

    def __call__(self) -> date:
        return self.day


# ---------- settings ----------
def test_settings_follow_the_real_calendar_unless_a_date_is_fixed(tmp_path):
    live = Settings(pack_dir=PACK, data_dir=tmp_path)
    before, today, after = date.today(), live.today(), date.today()
    assert live.demo_today is None and before <= today <= after
    assert replace(live, demo_today=DEMO_TODAY).today() == DEMO_TODAY


def test_a_time_zone_decides_when_the_day_starts(tmp_path):
    def today_in(zone):
        before = datetime.now(ZoneInfo(zone)).date()
        today = Settings(pack_dir=PACK, data_dir=tmp_path, timezone=zone).today()
        assert before <= today <= datetime.now(ZoneInfo(zone)).date()
        return today

    # Kiritimati is 25 hours ahead of Pago Pago, so the two are never on the same date
    assert today_in("Pacific/Kiritimati") > today_in("Pacific/Pago_Pago")
    # a fixed date wins over the time zone
    assert Settings(pack_dir=PACK, data_dir=tmp_path, timezone="Asia/Dubai", demo_today=DEMO_TODAY).today() == DEMO_TODAY
    with pytest.raises(ValueError, match="FERRERO_TIMEZONE"):
        Settings(pack_dir=PACK, data_dir=tmp_path, timezone="Mars/Olympus")


def test_the_date_is_fixed_only_when_the_environment_says_so(monkeypatch):
    monkeypatch.setattr("ferrero.config.load_dotenv", lambda path: None)  # the developer's own .env stays out of it
    monkeypatch.delenv("FERRERO_DEMO_TODAY", raising=False)
    monkeypatch.delenv("FERRERO_TIMEZONE", raising=False)
    free = get_settings.__wrapped__()
    assert free.demo_today is None and free.timezone is None
    monkeypatch.setenv("FERRERO_DEMO_TODAY", "2026-11-05")
    monkeypatch.setenv("FERRERO_TIMEZONE", "Asia/Dubai")
    fixed = get_settings.__wrapped__()
    assert (fixed.demo_today, fixed.timezone, fixed.today()) == (DEMO_TODAY, "Asia/Dubai", DEMO_TODAY)


# ---------- the case model ----------
def test_the_case_model_moves_on_with_the_calendar():
    calendar = Calendar(DEMO_TODAY)
    model = CaseModel(PACK / "csv", calendar)
    ops = model.principal("U-08")
    stored = {r["case_id"]: (r["status"], r["days_open"]) for r in model.base_cases()}

    def rows(sql):
        return model.query(ops, sql)["rows"]

    # on the data pack's own day, every figure is the pack's
    assert rows("SELECT reporting_date(), demo_today()") == [["2026-11-05", "2026-11-05"]] and rows(OVERDUE) == [[4]]
    assert all(days == stored[case][1] for case, days in rows("SELECT case_id, days_open FROM fact_case"))

    calendar.day = date(2026, 11, 19)  # two weeks on
    assert rows("SELECT reporting_date()") == [["2026-11-19"]] and rows(OVERDUE) == [[15]]
    for case, days in rows("SELECT case_id, days_open FROM fact_case"):
        status, was = stored[case]
        assert days == (was + 14 if status == "Open" else was), case  # open cases have aged; closed ones have not
    assert stored["TM-2026-430"][0] == "Open"
    assert model.case_summary(ops, "TM-2026-430")["days_open"] == stored["TM-2026-430"][1] + 14
    assert {day for _, day in model._snapshots} == {date(2026, 11, 19)}  # the earlier day's data is not kept


def test_a_fixed_date_still_works_as_before():
    model = CaseModel(PACK / "csv", DEMO_TODAY)
    assert model.today == DEMO_TODAY
    assert model.query(model.principal("U-08"), OVERDUE)["rows"] == [[4]]


# ---------- deadlines and reminders ----------
def test_deadlines_and_reminders_follow_the_calendar(settings):
    calendar = Calendar(DEMO_TODAY)
    model = CaseModel(PACK / "csv", calendar)
    records = CaseRecords(settings, model)  # no clock of its own: it shares the model's
    lina = model.principal("U-06")
    fid = records.create_follow_up(lina, "TM-2026-412", {
        "kind": "Internal follow-up", "title": "Check customs register", "due_date": "2026-11-20", "remind_days": 7})["follow_up_id"]

    def left():
        work = records.worklist(lina)
        return work["as_of"], next(i["days_left"] for i in work["items"] if i["id"] == fid)

    def sent():
        with records.store.read() as conn:
            return [r["stage"] for r in conn.execute("SELECT stage FROM notifications WHERE ref_id = ? ORDER BY seq", (fid,))]

    records.run_reminders()
    assert left() == ("2026-11-05", 15) and sent() == []
    calendar.day = date(2026, 11, 14)
    records.run_reminders()
    assert left() == ("2026-11-14", 6) and sent() == ["upcoming"]
    calendar.day = date(2026, 11, 21)
    records.run_reminders()
    assert left() == ("2026-11-21", -1) and sent() == ["upcoming", "due"]


# ---------- the pages ----------
def test_the_pages_show_the_real_date_and_keep_up_with_it(settings, index, fake_claude):
    calendar = Calendar(date(2026, 11, 19))
    live = replace(settings, demo_today=None)
    model = CaseModel(PACK / "csv", calendar)
    with TestClient(create_app(live, Assistant(live, model, index, client=fake_claude.client()))) as c:
        sign_in(c, "U-08")

        def overdue():
            return sum(1 for r in c.get("/api/cases").json() if r["overdue"])

        meta = c.get("/api/meta").json()
        assert (meta["demo_today"], meta["today_fixed"]) == ("2026-11-19", False)
        assert c.get("/api/follow-ups").json()["as_of"] == "2026-11-19" and overdue() == 15
        calendar.day += timedelta(days=30)  # the app has been running for a month
        assert c.get("/api/meta").json()["demo_today"] == "2026-12-19"
        assert c.get("/api/follow-ups").json()["as_of"] == "2026-12-19" and overdue() > 15


# ---------- the assistant ----------
def test_the_assistant_is_told_the_date_in_each_conversation(settings, index, fake_claude):
    calendar = Calendar(date(2026, 11, 19))
    assistant = Assistant(settings, CaseModel(PACK / "csv", calendar), index, client=fake_claude.client())
    fake_claude.responses = [message([thinking(), text("One.")]), message([thinking("sig-2"), text("Two.")])]
    list(assistant.ask(assistant.start("U-08"), "What is due today?"))
    calendar.day = date(2026, 11, 20)
    list(assistant.ask(assistant.start("U-08"), "What is due today?"))
    first, second = (r["body"] for r in fake_claude.requests)

    def note(body):
        return next(m["content"] for m in body["messages"] if m["role"] == "system")

    assert note(first).startswith("Today's date is Thursday 19 November 2026. Signed-in user: Priya Menon")
    assert "Today's date is Friday 20 November 2026." in note(second)
    # the prompt itself carries no date, so it is the same every day (and stays cached)
    assert first["system"] == second["system"] and "Today's date is" not in first["system"]
    assert "reporting_date()" in first["system"]


# ---------- the evaluation ----------
def test_the_evaluation_keeps_the_day_its_reference_answers_were_written_for(tmp_path):
    live = Settings(pack_dir=PACK, data_dir=tmp_path)
    assert evaluation_day(live) == GOLDEN_TODAY == DEMO_TODAY
    assert evaluation_day(replace(live, demo_today=date(2026, 12, 1))) == date(2026, 12, 1)
