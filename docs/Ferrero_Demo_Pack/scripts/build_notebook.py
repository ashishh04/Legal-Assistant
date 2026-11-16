import json
from specs import RELATIONSHIPS, DAX, RLS

def md(src): return {"cell_type": "markdown", "metadata": {}, "source": src}
def code(src): return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": src}

cells = [
md("""# Ferrero demo – load the case-intelligence lakehouse

Loads the synthetic demo data pack into Delta tables in the attached Lakehouse, adds a date dimension and the derived columns the dashboards use, and checks referential integrity.

**Before you run**
1. Create a Lakehouse (e.g. `lh_ferrero_demo`) in the demo workspace on the F4 capacity and attach it to this notebook as the default lakehouse.
2. Upload the `csv/` folder from the data pack to `Files/ferrero_demo/csv` (Lakehouse explorer → Files → Upload folder).
3. Run all cells. Re-running is safe: every table is overwritten.

All data is fictional. Marks, parties, people, amounts and outcomes are invented for the demo."""),
code("""BASE = "Files/ferrero_demo/csv"
TABLES = ["dim_mark", "dim_court", "dim_infringer", "dim_user", "fact_case", "fact_case_event", "fact_document",
          "fact_mailbox", "fact_intake_form", "fact_appstore", "fact_invoice", "golden_set"]
DATE_COLS = {"opened_date", "closed_date", "next_hearing_date", "next_action_due", "last_action_date", "event_date", "doc_date",
             "submitted_at", "detected_date", "takedown_requested_date", "removed_date", "invoice_date", "first_seen"}
TS_COLS = {"received_at", "triaged_at"}
DEMO_TODAY = "2026-11-05"   # frozen 'today' so the demo numbers never drift"""),
code("""from pyspark.sql import functions as F
from pyspark.sql.types import DateType, TimestampType

def load(name):
    df = spark.read.option("header", True).option("inferSchema", True).option("multiLine", True).option("escape", '"').csv(f"{BASE}/{name}.csv")
    for c in df.columns:
        if c in DATE_COLS:
            df = df.withColumn(c, F.to_date(F.col(c).cast("string").substr(1, 10)))
        elif c in TS_COLS:
            df = df.withColumn(c, F.to_timestamp(F.col(c).cast("string")))
    return df

for name in TABLES:
    df = load(name)
    df.write.mode("overwrite").option("overwriteSchema", "true").format("delta").saveAsTable(name)
    print(f"{name:18s} {df.count():5d} rows, {len(df.columns):2d} columns")"""),
md("""## Date dimension and derived columns"""),
code("""# dim_date: 2024-01-01 .. 2027-12-31, marked as the date table in the semantic model
dates = spark.sql("SELECT explode(sequence(to_date('2024-01-01'), to_date('2027-12-31'), interval 1 day)) AS Date")
dim_date = (dates
    .withColumn("Year", F.year("Date"))
    .withColumn("Quarter", F.concat(F.lit("Q"), F.quarter("Date")))
    .withColumn("YearQuarter", F.concat(F.year("Date"), F.lit(" Q"), F.quarter("Date")))
    .withColumn("MonthNumber", F.month("Date"))
    .withColumn("Month", F.date_format("Date", "MMM yyyy"))
    .withColumn("MonthStart", F.trunc("Date", "month"))
    .withColumn("Week", F.weekofyear("Date"))
    .withColumn("WeekStart", F.date_sub("Date", (F.dayofweek("Date") + 5) % 7))
    .withColumn("DayName", F.date_format("Date", "EEE"))
    .withColumn("IsWeekend", F.dayofweek("Date").isin([6, 7]))
    .withColumn("IsMonthEnd", F.col("Date") == F.last_day("Date")))
dim_date.write.mode("overwrite").option("overwriteSchema", "true").format("delta").saveAsTable("dim_date")
print("dim_date", dim_date.count())"""),
code("""# fact_case: age buckets and a frozen 'as of' date for the demo
fc = spark.table("fact_case")
fc = (fc.withColumn("as_of_date", F.to_date(F.lit(DEMO_TODAY)))
        .withColumn("age_bucket", F.when(F.col("days_open") <= 90, "0–90 days").when(F.col("days_open") <= 180, "91–180 days")
                                   .when(F.col("days_open") <= 365, "181–365 days").otherwise("> 365 days"))
        .withColumn("is_overdue", (F.col("status") == "Open") & (F.col("next_action_due") < F.to_date(F.lit(DEMO_TODAY))))
        .withColumn("hearing_next_30d", (F.col("status") == "Open") & F.col("next_hearing_date").between(F.to_date(F.lit(DEMO_TODAY)), F.date_add(F.to_date(F.lit(DEMO_TODAY)), 30))))
fc.write.mode("overwrite").option("overwriteSchema", "true").format("delta").saveAsTable("fact_case")

# fact_mailbox: a date key for dim_date and hours to triage
fm = spark.table("fact_mailbox")
fm = (fm.withColumn("received_date", F.to_date("received_at"))
        .withColumn("hours_to_triage", (F.unix_timestamp("triaged_at") - F.unix_timestamp("received_at")) / 3600.0))
fm.write.mode("overwrite").option("overwriteSchema", "true").format("delta").saveAsTable("fact_mailbox")

# fact_appstore: days to takedown
fa = spark.table("fact_appstore").withColumn("days_to_takedown", F.datediff("removed_date", "takedown_requested_date"))
fa.write.mode("overwrite").option("overwriteSchema", "true").format("delta").saveAsTable("fact_appstore")
print("derived columns written")"""),
md("""## Checks"""),
code("""checks = {
  "events without a case":     "SELECT COUNT(*) FROM fact_case_event e LEFT ANTI JOIN fact_case c ON e.case_id = c.case_id",
  "documents without a case":  "SELECT COUNT(*) FROM fact_document d LEFT ANTI JOIN fact_case c ON d.case_id = c.case_id",
  "invoices without a case":   "SELECT COUNT(*) FROM fact_invoice i LEFT ANTI JOIN fact_case c ON i.case_id = c.case_id",
  "cases without a mark":      "SELECT COUNT(*) FROM fact_case c LEFT ANTI JOIN dim_mark m ON c.mark_id = m.mark_id",
  "cases without a court":     "SELECT COUNT(*) FROM fact_case c LEFT ANTI JOIN dim_court k ON c.court_id = k.court_id",
  "closed before opened":      "SELECT COUNT(*) FROM fact_case WHERE closed_date < opened_date",
}
for label, sql in checks.items():
    print(f"{label:28s} {spark.sql(sql).first()[0]}")
display(spark.sql(\"\"\"SELECT status, COUNT(*) AS cases, SUM(claim_amount_aed) AS claimed_aed, SUM(recovered_amount_aed) AS recovered_aed
                     FROM fact_case GROUP BY status\"\"\"))"""),
md("""## Next steps (outside this notebook)

1. **Semantic model** – create a Direct Lake semantic model on this lakehouse with the tables above. Mark `dim_date` as the date table. Add the relationships and measures from the data pack (`Semantic_Model` and `DAX_Measures` sheets; also listed below).
2. **Row-level security** – create the roles below and map them to the Entra ID groups in `dim_user.entra_group`.
3. **Reports** – build the four dashboards from the `Dashboard_Specs` sheet (D1 Legal Case Overview, D2 Leadership Command View, D3 Infringement Intake and Triage, D4 Infringer and Enforcement Outcomes) and the drill-through pages DS-1 … DS-6.
4. **Documents** – upload `documents/` to the SharePoint libraries named in `fact_document.library_path`, so the Ferrero document sync and the golden set (`golden_set` table) line up with the dashboards.

### Relationships
| From | To | Cardinality | State |
|---|---|---|---|
""" + "\n".join(f"| {a}[{b}] | {c}[{d}] | {e} | {g} |" for a, b, c, d, e, f, g in RELATIONSHIPS) + """

### RLS roles
| Role | Table | Filter | Who |
|---|---|---|---|
""" + "\n".join(f"| {a} | {b} | `{c}` | {d} |" for a, b, c, d in RLS) + """

### Measures
""" + "\n".join(f"- **{m}** = `{x}`" for m, x, *_ in DAX)),
]
nb = {"cells": cells, "metadata": {"kernelspec": {"name": "synapse_pyspark", "display_name": "Synapse PySpark", "language": "Python"},
      "language_info": {"name": "python"}, "microsoft": {"language": "python"}}, "nbformat": 4, "nbformat_minor": 5}
json.dump(nb, open('out/Ferrero_Demo_Load.ipynb', 'w'), indent=1, ensure_ascii=False)

README = """# Ferrero case-intelligence demo – data pack

Synthetic, internally consistent data for the Fabric lakehouse, the four Power BI dashboards and the Ferrero assistant demo.
**All marks, parties, people, case numbers, amounts and outcomes are fictional.** "Dolce Group International S.A." stands in for the customer entity.

## Contents
- `Ferrero_Demo_Data_Pack.xlsx` – the data (one sheet per table), a live Summary, Dashboard_Specs, DAX_Measures, Semantic_Model (relationships + RLS), Data_Dictionary, golden_set
- `csv/` – the same tables as CSV (what the notebook loads)
- `Ferrero_Demo_Load.ipynb` – Fabric PySpark notebook: CSV → Delta tables, dim_date, derived columns, integrity checks
- `documents/` – 12 sample case documents (DOCX, 8 EN + 4 AR) whose facts match the data: judgments, cease-and-desist letters, settlement, licence, investigation report, customs notice, statement of claim, takedown notice, trademark-office decision
- `gen_data.py`, `prep_docs.py`, `build_docs.js`, `build_workbook.py`, `build_notebook.py`, `specs.py` – regenerate everything (`python3 gen_data.py && python3 prep_docs.py && node build_docs.js && python3 build_workbook.py && python3 build_notebook.py`)

## Stand up the demo environment
1. Fabric workspace on the F4 capacity → new Lakehouse `lh_ferrero_demo`.
2. Upload `csv/` to `Files/ferrero_demo/csv`; import and run `Ferrero_Demo_Load.ipynb`.
3. Direct Lake semantic model: relationships and RLS from `Semantic_Model`, measures from `DAX_Measures`, `dim_date` marked as date table.
4. Build D1–D4 and DS-1–DS-6 from `Dashboard_Specs`; publish; test RLS with the groups in `dim_user`.
5. Upload `documents/` to the SharePoint paths in `fact_document.library_path`; run the Ferrero document sync; load `golden_set` as the evaluation set.

Demo "today" is frozen at 2026-11-05 (`DEMO_TODAY` in the notebook; replace `TODAY()` in the measures with a parameter if you want the same).
"""
open('out/README.md', 'w').write(README)
print('notebook and README written')
