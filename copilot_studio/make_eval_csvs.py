"""Build the Copilot Studio evaluation files (columns: Question, Expected response) from the pack's golden_set.csv.

    python make_eval_csvs.py          # writes eval_documents.csv and eval_analytics.csv next to this script

Four expected answers are rewritten because the golden set's text isn't an answer the agent could match:
GS-017 only names the route, GS-025/GS-026 are "Refusal:" labels, and GS-028 ignores a tie in the data.
"""
from __future__ import annotations

import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOLDEN = HERE.parent / "docs" / "Ferrero_Demo_Pack" / "csv" / "golden_set.csv"
OVERRIDES = {
    "GS-017": "The next action on TM-2026-421 is to prepare the hearing bundle, due 27 December 2026 (case tracker).",
    "GS-025": "I can't find case TM-2023-150 in the case files available to you, so I can't give its claim amount.",
    "GS-026": "I can only help with the legal team's cases and documents, so I can't answer questions about the weather.",
    "GS-028": "DealHub Marketplace Seller 4471 and Souq Al Hala Online are tied for the most cases, with 7 cases each (case tracker).",
}


def main() -> None:
    with GOLDEN.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    sets: dict[str, list[tuple[str, str]]] = {"eval_documents.csv": [], "eval_analytics.csv": []}
    for r in rows:
        name = "eval_analytics.csv" if r["route"] == "analytics" else "eval_documents.csv"
        sets[name].append((r["question"], OVERRIDES.get(r["gs_id"], r["expected_answer"])))
    for name, items in sets.items():
        with (HERE / name).open("w", encoding="utf-8-sig", newline="") as f:  # BOM: Excel then shows Arabic correctly
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(["Question", "Expected response"])
            writer.writerows(items)
        print(f"{name}: {len(items)} questions")


if __name__ == "__main__":
    main()
