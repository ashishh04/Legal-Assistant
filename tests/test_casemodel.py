import pytest

from ferrero.casemodel import QueryError


def rows(model, principal, sql):
    return model.query(principal, sql)["rows"]


def test_golden_set_counts(model, principals):
    ops = principals["ops"]
    assert rows(model, ops, "SELECT COUNT(*) FROM fact_case WHERE status = 'Open' AND country = 'KSA'") == [[9]]
    assert rows(model, ops, "SELECT COUNT(*) FROM fact_case WHERE status = 'Open' AND next_hearing_date "
                            "BETWEEN demo_today() AND date(demo_today(), '+30 days')") == [[8]]


def test_country_roles_see_only_their_rows(model, principals):
    ksa = principals["ksa"]
    assert rows(model, ksa, "SELECT DISTINCT country FROM fact_case") == [["KSA"]]
    assert rows(model, ksa, "SELECT DISTINCT country FROM fact_mailbox") == [["KSA"]]
    assert rows(model, ksa, "SELECT DISTINCT country FROM fact_appstore") == [["KSA"]]
    leaked = rows(model, ksa, "SELECT COUNT(*) FROM fact_case_event e JOIN fact_case c USING (case_id) WHERE c.country <> 'KSA'")
    assert leaked == [[0]]
    mena = rows(model, principals["mena"], "SELECT DISTINCT country FROM fact_case ORDER BY 1")
    assert ["UAE"] not in mena and ["KSA"] not in mena and len(mena) == 7


def test_infringer_counts_are_recomputed_within_scope(model, principals):
    top = rows(model, principals["ksa"], "SELECT infringer_name_en, case_count FROM dim_infringer ORDER BY case_count DESC LIMIT 1")
    assert top == [["Souq Al Hala Online", 7]]
    assert rows(model, principals["ksa"], "SELECT COUNT(*) FROM dim_infringer WHERE country = 'UAE'") == [[0]]


def test_procurement_has_no_document_catalogue(model, principals):
    with pytest.raises(QueryError, match="no such table"):
        model.query(principals["procurement"], "SELECT COUNT(*) FROM fact_document")
    assert rows(model, principals["procurement"], "SELECT COUNT(*) FROM fact_case") == [[120]]


@pytest.mark.parametrize("sql", [
    "DELETE FROM fact_case",
    "UPDATE fact_case SET status = 'Closed'",
    "SELECT 1; DROP TABLE fact_case",
    "ATTACH DATABASE 'x.db' AS x",
    "PRAGMA table_info(fact_case)",
    "CREATE TEMP TABLE t AS SELECT * FROM fact_case",
])
def test_only_reads_are_allowed(model, principals, sql):
    with pytest.raises(QueryError):
        model.query(principals["ops"], sql)


def test_runaway_queries_are_stopped(model, principals):
    with pytest.raises(QueryError, match="too long"):
        model.query(principals["ops"], "WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM r) SELECT COUNT(*) FROM r",
                    time_limit=0.5)


def test_results_are_capped(model, principals):
    result = model.query(principals["ops"], "SELECT * FROM fact_case_event", max_rows=50)
    assert result["row_count"] == 50 and result["truncated"]


def test_personal_email_is_not_exposed(model, principals):
    with pytest.raises(QueryError, match="email"):
        model.query(principals["ops"], "SELECT email FROM dim_user")


def test_case_summary_respects_access(model, principals):
    assert model.case_summary(principals["ksa"], "TM-2024-428") is None
    summary = model.case_summary(principals["ops"], "TM-2024-428")
    assert summary["awarded_amount_local"] == 2288000 and summary["currency"] == "AED"
    assert summary["timeline"][0]["event_type"] == "Case opened"
    assert model.case_summary(principals["procurement"], "TM-2024-428")["documents_on_file"].startswith("not available")
