# documents_150 – demo document corpus (150 PDFs)

`../documents_150/` holds exactly 150 PDFs for the SharePoint library and the Ferrero document sync. Every file is one row of `fact_document`, and its facts (parties, marks, courts, amounts, dates) come from `fact_case`, `fact_case_event` and the dimension tables. Each page carries the footer *"Demo document – all parties and facts are fictional"*.

| | |
|---|---|
| Pack samples | 12 (the pack DOCX converted with Word; same names, `.pdf`) |
| Generated | 138 |
| Document types | all 12: cease-and-desist 24, judgment 18, statement of claim 18, test-purchase evidence 18, investigation report 14, power of attorney 14, takedown notice 13, settlement 10, expert report 10, customs seizure notice 7, licence agreement 2, trademark office decision 2 |
| Languages | 78 Arabic, 72 English |
| Cases covered | 57 (whole case files where possible: letter → evidence → claim → expert → judgment) |
| Image-only scans | 41 (no text layer, so OCR is required) |

## Files in this folder

- **manifest.csv**: one row per PDF (file, doc_id, case_id, doc_type, language, doc_date, pages, scanned, ocr_confidence, index_status, skip_reason, password, sensitivity, access_group, country, mark, library_path, source, bytes, sha256). Map files to cases with `case_id` / `library_path`, **never by file name**: names are deliberately messy (`scan4821.pdf`, `… (final).pdf`, Arabic names).
- **fact_document.csv**: drop-in replacement for `csv/fact_document.csv`. Same 508 rows and columns. The 150 rows that now have a real file get `title`/`library_path` set to the PDF name, `sample_file=True`, and the actual `doc_date`, `pages`, `chunks`, `scanned` and `ocr_confidence`.
- **golden_set.csv**: the pack golden set with document sources renamed `.docx` → `.pdf`.

## Files that behave like their index status

| index_status | Files | What the file is |
|---|---|---|
| Skipped – Password-protected PDF | 4 | AES-256 encrypted; the password is in `manifest.csv` |
| Skipped – OCR confidence below threshold | 3 | heavily degraded scans |
| Indexed (flagged) – low-confidence pages | 5 | scans with one poor page |
| Pending – queued for reindex | 8 | normal files |

## Notes

- Arabic text PDFs use **Segoe UI**. With Arial, Tahoma or Times, Word's PDF text layer reverses the lam-alef ligature (`العالمة` instead of `العلامة`), which breaks search. The 4 Arabic pack documents were converted with the same font switch; their content is unchanged.
- The 60 "Contoso Holding" files in `../documents/` are **not** part of this corpus and were not modified.
- Known pack defects remain inside the 12 pack documents (e.g. the TM-2024-409 takedown names Google Play/ChocoApp while `fact_appstore` says Apple/AppWorks, and some pack document dates differ from `fact_case_event`).
- Hijri dates on Saudi documents use the arithmetic calendar and can differ from Umm al-Qura by a day.

## Regenerate

```
python scripts/pdf_corpus/build_corpus.py          # needs Microsoft Word, python-docx, PyMuPDF, Pillow, numpy
python scripts/pdf_corpus/build_corpus.py --test   # small sample in scripts/out/pdf_corpus/test
```

The build is deterministic and reads the pack CSVs. It writes `documents_150/` and this folder, and checks every file: case ID present in the text layer, scans without text, password files locked, no reversed lam-alef, no zero amounts.
