from ferrero.eval.golden import PROBES, check, load_golden

from conftest import PACK


def test_overrides_fix_the_two_flawed_golden_rows():
    rows = {r["gs_id"]: r for r in load_golden(PACK / "csv" / "golden_set.csv")}
    assert len(rows) == 30
    assert "27 December 2026" in rows["GS-017"]["expected_answer"]
    assert "Souq Al Hala Online" in rows["GS-028"]["expected_answer"]


def test_checks_route_source_language_and_leaks():
    row = {"route": "documents", "language": "AR", "expected_answer": "2,288,000 درهم",
           "source": "TM-2024-428_Judgment_EN.docx", "must_not_contain": ["3,334,000"]}
    answer = {"text": "حكمت المحكمة بتعويض قدره 2,288,000 درهم إماراتي.", "route": ["documents"],
              "citations": [{"file_name": "TM-2024-428_Judgment_EN.docx"}], "tools": []}
    assert check(row, answer) == {"route_used": ["documents"], "files_used": ["TM-2024-428_Judgment_EN.docx"],
                                  "route_ok": True, "source_ok": True, "language_ok": True, "leak": []}
    wrong = check({**row, "language": "EN"}, {**answer, "route": ["case_data"], "citations": [], "text": "3,334,000 claimed"})
    assert (wrong["route_ok"], wrong["source_ok"], wrong["language_ok"], wrong["leak"]) == (False, False, True, ["3,334,000"])


def test_refusals_skip_the_route_check():
    out = check({"route": "documents", "language": "EN", "expected_answer": "Refusal: off-topic", "source": ""},
                {"text": "I can only help with case files.", "route": [], "citations": [], "tools": []})
    assert "route_ok" not in out and out["language_ok"]


def test_probes_run_as_restricted_users():
    assert {p["user_id"] for p in PROBES} == {"U-05", "U-10", "U-06"}
