# Ferrero case-intelligence demo – data pack

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
