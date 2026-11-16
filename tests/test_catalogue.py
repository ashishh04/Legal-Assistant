"""The document corpus's own catalogue (<corpus>_meta/fact_document.csv) and the default corpus folder."""
from __future__ import annotations

import csv
import shutil

from ferrero.casemodel import CaseModel
from ferrero.config import Settings

from conftest import DEMO_TODAY, PACK


def _copy_catalogue(tmp_path, change: dict[str, dict[str, str]]):
    rows = list(csv.DictReader(open(PACK / "csv" / "fact_document.csv", encoding="utf-8-sig")))
    for r in rows:
        r.update(change.get(r["doc_id"], {}))
    path = tmp_path / "fact_document.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return path, rows


def test_case_model_uses_the_corpus_catalogue_when_given(tmp_path, principals):
    pack_rows = list(csv.DictReader(open(PACK / "csv" / "fact_document.csv", encoding="utf-8-sig")))
    target = next(r for r in pack_rows if r["case_id"] == "TM-2024-428")
    path, _ = _copy_catalogue(tmp_path, {target["doc_id"]: {"doc_date": "2024-12-01", "title": "renamed scan.pdf"}})
    model = CaseModel(PACK / "csv", DEMO_TODAY, catalogue=path)
    docs = model.case_summary(principals["ops"], "TM-2024-428")["documents_on_file"]
    mine = next(d for d in docs if d["doc_id"] == target["doc_id"])
    assert mine["doc_date"] == "2024-12-01" and mine["title"] == "renamed scan.pdf"
    assert model.catalogue_entry("renamed scan.pdf")["doc_id"] == target["doc_id"]
    plain = CaseModel(PACK / "csv", DEMO_TODAY)
    assert plain.catalogue_by_id(target["doc_id"])["title"] == target["title"]
    assert CaseModel(PACK / "csv", DEMO_TODAY, catalogue=tmp_path / "missing.csv").catalogue_by_id(target["doc_id"])["title"] == target["title"]


def test_default_corpus_prefers_the_full_one_once_built(tmp_path):
    pack = tmp_path / "pack"
    (pack / "documents").mkdir(parents=True)
    (pack / "documents_150").mkdir()
    settings = Settings(pack_dir=pack, data_dir=tmp_path, demo_today=DEMO_TODAY)
    assert settings.documents_dir == pack / "documents_150" and settings.catalogue_path is None
    (pack / "documents_full").mkdir()
    assert settings.documents_dir == pack / "documents_150"          # no manifest yet: still being built
    meta = pack / "documents_full_meta"
    meta.mkdir()
    (meta / "manifest.csv").write_text("file,doc_id\n", encoding="utf-8")
    shutil.copy(PACK / "csv" / "fact_document.csv", meta / "fact_document.csv")
    assert settings.documents_dir == pack / "documents_full"
    assert settings.catalogue_path == meta / "fact_document.csv"
