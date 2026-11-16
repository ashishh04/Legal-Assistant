"""Build the "case tracker snapshot" knowledge file for the Copilot Studio agent.

Copilot Studio answers from documents, not from a live data model, so this script freezes the
case tracker (the data behind the Power BI dashboards) at the demo date as one Word document:
pre-computed figures first, so the agent never has to count rows itself, then one short
section per case. Key figures repeat in Arabic so Arabic questions find them too.

    python make_snapshot.py                     # writes knowledge/Case_Tracker_Snapshot_2026-11-05.docx
    python make_snapshot.py --csv-dir <pack>/csv --out <file.docx>

Regenerate it whenever the pack's CSVs change.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import docx

DEMO_TODAY = date(2026, 11, 5)
HERE = Path(__file__).resolve().parent
DEFAULT_CSV = HERE.parent / "docs" / "Ferrero_Demo_Pack" / "csv"
DEFAULT_OUT = HERE / "knowledge" / f"Case_Tracker_Snapshot_{DEMO_TODAY.isoformat()}.docx"

COUNTRY_ORDER = ["UAE", "KSA", "Egypt", "Jordan", "Kuwait", "Oman", "Qatar", "Turkey", "India"]
COUNTRY_EN = {"UAE": "UAE (United Arab Emirates)", "KSA": "KSA (Saudi Arabia)"}
COUNTRY_AR = {
    "UAE": "الإمارات العربية المتحدة", "KSA": "المملكة العربية السعودية", "Egypt": "مصر", "Jordan": "الأردن",
    "Kuwait": "الكويت", "Oman": "عمان", "Qatar": "قطر", "Turkey": "تركيا", "India": "الهند",
}
DECIDED = {"Won", "Partially won", "Settled", "Lost", "Takedown achieved"}  # as the Win Rate measure
WINS = DECIDED - {"Lost"}


def read(csv_dir: Path, name: str) -> list[dict[str, str]]:
    with (csv_dir / f"{name}.csv").open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def day(s: str) -> date | None:
    return date.fromisoformat(s[:10]) if s else None


def fdate(d: date) -> str:
    return f"{d.day} {d:%B %Y}"


def num(s: str) -> float:
    return float(s) if s else 0.0


def money(amount: float, currency: str = "AED") -> str:
    return f"{currency} {amount:,.0f}"


def country_en(c: str) -> str:
    return COUNTRY_EN.get(c, c)


def ar_cases(n: int) -> str:
    """Arabic count of cases with the right noun form."""
    if n == 0:
        return "لا توجد قضايا"
    if n == 1:
        return "قضية واحدة"
    if n == 2:
        return "قضيتان"
    if 3 <= n <= 10:
        return f"{n} قضايا"
    return f"{n} قضية"


def local_and_aed(case: dict[str, str], field: str) -> str:
    local, aed, cur = num(case[f"{field}_local"]), num(case[f"{field}_aed"]), case["currency"]
    return money(aed) if cur == "AED" else f"{money(local, cur)} (AED {aed:,.0f})"


class Doc:
    def __init__(self) -> None:
        self.d = docx.Document()

    def h(self, text: str, level: int) -> None:
        self.d.add_heading(text, level=level)

    def p(self, text: str) -> None:
        self.d.add_paragraph(text)

    def bullet(self, text: str) -> None:
        self.d.add_paragraph(text, style="List Bullet")

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.d.save(path)


def build(csv_dir: Path) -> Doc:
    cases = sorted(read(csv_dir, "fact_case"), key=lambda c: c["case_id"])
    marks = {m["mark_id"]: m for m in read(csv_dir, "dim_mark")}
    infringers = {i["infringer_id"]: i for i in read(csv_dir, "dim_infringer")}
    courts = {c["court_id"]: c for c in read(csv_dir, "dim_court")}
    invoices = read(csv_dir, "fact_invoice")
    mailbox = read(csv_dir, "fact_mailbox")
    appstore = read(csv_dir, "fact_appstore")
    intake = read(csv_dir, "fact_intake_form")
    by_id = {c["case_id"]: c for c in cases}
    fees = defaultdict(float)
    for inv in invoices:
        fees[inv["case_id"]] += num(inv["amount_aed"])

    open_cases = [c for c in cases if c["status"] == "Open"]
    closed_cases = [c for c in cases if c["status"] == "Closed"]
    countries = [c for c in COUNTRY_ORDER if any(x["country"] == c for x in cases)]
    today = fdate(DEMO_TODAY)
    doc = Doc()

    # ---------- introduction ----------
    doc.h(f"Case tracker snapshot – {today}", 0)
    doc.p("ملخص متتبع القضايا – 5 نوفمبر 2026")
    doc.p(
        f"This document is a snapshot of the legal team's case tracker, the same data behind the Power BI dashboards, "
        f"frozen at the demo date of {today}. In this demo, today is {today}. Figures below are pre-computed from the "
        f"tracker; use them as stated. Amounts are in AED unless a local currency is shown. The tracker holds "
        f"{len(cases)} cases in {', '.join(country_en(c) for c in countries)}."
    )
    doc.p(
        f"هذه نسخة ثابتة من متتبع القضايا لدى الفريق القانوني (البيانات نفسها التي تعرضها لوحات Power BI) بتاريخ 5 نوفمبر 2026. "
        f"الأرقام محسوبة مسبقاً، والمبالغ بالدرهم الإماراتي ما لم تُذكر عملة محلية."
    )

    # ---------- headline figures ----------
    doc.h("Headline figures (الأرقام الرئيسية)", 1)
    doc.p(f"Total cases: {len(cases)}. Open cases: {len(open_cases)}. Closed cases: {len(closed_cases)}.")
    doc.p(f"إجمالي القضايا: {len(cases)}. القضايا المفتوحة: {len(open_cases)}. القضايا المغلقة: {len(closed_cases)}.")

    # ---------- by country ----------
    doc.h("Cases by country (القضايا حسب الدولة)", 1)
    for c in countries:
        rows = [x for x in cases if x["country"] == c]
        n_open = sum(x["status"] == "Open" for x in rows)
        doc.bullet(f"Open cases in {country_en(c)}: {n_open}. Closed cases: {len(rows) - n_open}. Total cases: {len(rows)}.")
        doc.bullet(f"عدد القضايا المفتوحة في {COUNTRY_AR[c]}: {ar_cases(n_open)}، من إجمالي {len(rows)}.")

    # ---------- by trademark ----------
    doc.h("Cases by trademark (القضايا حسب العلامة التجارية)", 1)
    for mid, m in marks.items():
        rows = [x for x in cases if x["mark_id"] == mid]
        if rows:
            n_open = sum(x["status"] == "Open" for x in rows)
            doc.bullet(f"{m['mark_name']} ({m['mark_name_ar']}, {m['product_category']}): {len(rows)} cases, {n_open} open.")

    # ---------- stages and outcomes ----------
    doc.h("Open cases by stage", 1)
    for stage, n in Counter(x["stage"] for x in open_cases).most_common():
        doc.bullet(f"{stage}: {n} open cases.")
    doc.h("Outcomes of closed cases", 1)
    for outcome, n in Counter(x["outcome"] for x in closed_cases).most_common():
        doc.bullet(f"{outcome}: {n} cases.")

    # ---------- hearings in the next 30 days ----------
    end = DEMO_TODAY + timedelta(days=30)
    hearings = sorted(
        (x for x in open_cases if x["next_hearing_date"] and DEMO_TODAY <= day(x["next_hearing_date"]) <= end),
        key=lambda x: (x["next_hearing_date"], x["case_id"]),
    )
    window = f"{DEMO_TODAY.day} {DEMO_TODAY:%B} to {fdate(end)}"
    doc.h("Hearings in the next 30 days (الجلسات خلال الثلاثين يوماً القادمة)", 1)
    doc.p(f"{len(hearings)} open cases have a hearing in the next 30 days ({window}).")
    doc.p(f"عدد القضايا المفتوحة التي لها جلسة خلال الثلاثين يوماً القادمة (من 5 نوفمبر إلى {end.day} ديسمبر 2026): {ar_cases(len(hearings))}.")
    for x in hearings:
        doc.bullet(f"{x['case_id']} ({x['mark_name']}, {x['country']}): hearing on {fdate(day(x['next_hearing_date']))}, at {x['court_name']}.")

    # ---------- overdue actions ----------
    overdue = sorted(
        (x for x in open_cases if x["next_action_due"] and day(x["next_action_due"]) < DEMO_TODAY),
        key=lambda x: (x["next_action_due"], x["case_id"]),
    )
    doc.h("Overdue next actions (الإجراءات المتأخرة)", 1)
    doc.p(f"{len(overdue)} open cases have a next action that was due before {today}.")
    doc.p(f"عدد القضايا المفتوحة التي تأخر إجراؤها التالي عن موعده: {ar_cases(len(overdue))}.")
    for x in overdue:
        late = (DEMO_TODAY - day(x["next_action_due"])).days
        doc.bullet(f"{x['case_id']} ({x['country']}): {x['next_action']}, due {fdate(day(x['next_action_due']))} ({late} days overdue).")

    # ---------- infringers ----------
    counts = Counter(x["infringer_id"] for x in cases)
    ranked = counts.most_common()
    top_n = ranked[0][1]
    leaders = [infringers[i]["infringer_name_en"] for i, n in ranked if n == top_n]
    doc.h("Infringers with the most cases (المخالفون الأكثر تكراراً)", 1)
    if len(leaders) == 1:
        doc.p(f"The infringer with the most cases is {leaders[0]}, with {top_n} cases.")
        doc.p(f"المخالف صاحب أكبر عدد من القضايا: {infringers[ranked[0][0]]['infringer_name_ar']}، بواقع {ar_cases(top_n)}.")
    else:
        names_ar = " و".join(infringers[i]["infringer_name_ar"] for i, n in ranked if n == top_n)
        doc.p(f"{' and '.join(leaders)} are tied for the most cases, with {top_n} cases each.")
        doc.p(f"المخالفون أصحاب أكبر عدد من القضايا: {names_ar}، بواقع {ar_cases(top_n)} لكل منهم.")
    for i, n in ranked[:10]:
        inf = infringers[i]
        doc.bullet(f"{inf['infringer_name_en']} ({inf['infringer_name_ar']}; {inf['infringer_type']}, {inf['country']}): {n} cases.")
    repeat = sum(1 for _, n in ranked if n >= 2)
    doc.p(f"Repeat offenders (infringers with two or more cases): {repeat}. Infringers with at least one case: {len(ranked)}.")

    # ---------- amounts by year closed ----------
    doc.h("Amounts by year of closing (المبالغ حسب سنة الإغلاق)", 1)
    by_year: dict[int, list[dict[str, str]]] = defaultdict(list)
    for x in closed_cases:
        by_year[day(x["closed_date"]).year].append(x)
    for year in sorted(by_year):
        rows = by_year[year]
        awarded = sum(num(x["awarded_amount_aed"]) for x in rows)
        settled = sum(num(x["settlement_amount_aed"]) for x in rows)
        recovered = sum(num(x["recovered_amount_aed"]) for x in rows)
        rate = recovered / (awarded + settled) if awarded + settled else 0
        doc.bullet(
            f"Cases closed in {year}: {len(rows)}. Damages awarded: {money(awarded)}. Settlements: {money(settled)}. "
            f"Recovered: {money(recovered)}. Recovery rate: {rate:.1%}."
        )
        doc.bullet(f"إجمالي التعويضات المحكوم بها في القضايا المغلقة في عام {year}: {awarded:,.0f} درهم إماراتي.")
    total_awarded = sum(num(x["awarded_amount_aed"]) for x in cases)
    total_claimed = sum(num(x["claim_amount_aed"]) for x in cases)
    doc.p(f"All cases: claimed {money(total_claimed)}; awarded {money(total_awarded)}.")

    # ---------- win rate ----------
    doc.h("Win rate by country (نسبة الفوز حسب الدولة)", 1)
    doc.p("Win rate = cases won, partially won, settled or with a takedown achieved, divided by decided cases "
          "(the same plus lost cases). Withdrawn and pending cases are not decided.")
    rates = {}
    for c in countries:
        rows = [x for x in cases if x["country"] == c and x["outcome"] in DECIDED]
        wins = sum(x["outcome"] in WINS for x in rows)
        if rows:
            rates[c] = wins / len(rows)
            doc.bullet(f"{country_en(c)}: win rate {rates[c]:.1%} ({wins} of {len(rows)} decided cases).")
    low = min(rates.values())
    doc.p(f"Lowest win rate: {', '.join(country_en(c) for c, r in rates.items() if r == low)} ({low:.1%}).")

    # ---------- legal spend ----------
    doc.h("External legal spend by country (المصاريف القانونية الخارجية)", 1)
    spend = defaultdict(float)
    for inv in invoices:
        if inv["case_id"] in by_id:
            spend[by_id[inv["case_id"]]["country"]] += num(inv["amount_aed"])
    for c in countries:
        doc.bullet(f"{country_en(c)}: {money(spend[c])} in external fees.")
    doc.p(f"Total external legal spend: {money(sum(spend.values()))} across {len(invoices)} invoices.")

    # ---------- intake ----------
    doc.h("Reports, intake forms and app-store takedowns", 1)
    since = DEMO_TODAY - timedelta(days=30)
    recent = sum(1 for r in mailbox if since <= datetime.fromisoformat(r["received_at"]).date() <= DEMO_TODAY)
    doc.p(f"Infringement mailbox: {len(mailbox)} reports in total, {recent} received in the last 30 days (since {fdate(since)}).")
    for status, n in Counter(r["triage_status"] for r in mailbox).most_common():
        doc.bullet(f"Mailbox reports – {status}: {n}.")
    doc.p(f"Intake forms: {len(intake)} submitted.")
    for status, n in Counter(r["status"] for r in intake).most_common():
        doc.bullet(f"Intake forms – {status}: {n}.")
    doc.p(f"App-store listings tracked: {len(appstore)}.")
    for status, n in Counter(r["status"] for r in appstore).most_common():
        doc.bullet(f"App-store listings – {status}: {n}.")

    # ---------- one section per case ----------
    doc.h("Case details (تفاصيل القضايا)", 1)
    for x in cases:
        mark, inf, court = marks[x["mark_id"]], infringers[x["infringer_id"]], courts[x["court_id"]]
        opened, closed = day(x["opened_date"]), day(x["closed_date"])
        parts = [
            f"{x['title']}.",
            f"Case type: {x['case_type']}.",
            f"Country: {country_en(x['country'])} – {COUNTRY_AR[x['country']]}.",
            f"Court: {court['court_name_en']} ({court['court_name_ar']}).",
            f"Trademark: {mark['mark_name']} ({mark['mark_name_ar']}).",
            f"Infringer: {inf['infringer_name_en']} ({inf['infringer_name_ar']}), {x['infringer_type']}.",
            f"Status: {x['status']}; stage: {x['stage']}; outcome: {x['outcome']}.",
            f"Opened {fdate(opened)}" + (f"; closed {fdate(closed)} after {(closed - opened).days} days." if closed
                                         else f"; open for {(DEMO_TODAY - opened).days} days."),
            f"Lead counsel: {x['lead_counsel']}" + (f"; external firm: {x['external_firm']}." if x["external_firm"] else "."),
            f"Source: {x['source_channel']}. Priority: {x['priority']}" + (f"; risk rating: {x['risk_rating']}." if x["risk_rating"] else "."),
            f"Claim amount: {local_and_aed(x, 'claim_amount')}.",
        ]
        if x["status"] == "Closed":
            parts.append(f"Awarded: {local_and_aed(x, 'awarded_amount')}. Settlement: {local_and_aed(x, 'settlement_amount')}. "
                         f"Recovered: {local_and_aed(x, 'recovered_amount')}.")
        if fees[x["case_id"]]:
            parts.append(f"External fees invoiced: {money(fees[x['case_id']])}.")
        if x["next_action"]:
            due = day(x["next_action_due"])
            parts.append(f"Next action: {x['next_action']}" + (f", due {fdate(due)}." if due else "."))
        if x["next_hearing_date"]:
            parts.append(f"Next hearing: {fdate(day(x['next_hearing_date']))}.")
        if x["last_action_date"]:
            parts.append(f"Last action: {fdate(day(x['last_action_date']))}.")
        doc.h(f"{x['case_id']} – {mark['mark_name']} – {x['country']} – {x['status']}", 2)
        doc.p(" ".join(parts))
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--csv-dir", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    build(args.csv_dir).save(args.out)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
