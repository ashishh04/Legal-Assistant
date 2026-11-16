# documents_full

One PDF for every row of fact_document (508), built by `scripts/pdf_corpus/extend_corpus.py`.

- 150 files copied byte for byte from documents_150 (scans, password-protected and flagged files included)
- 358 files written from the case data as text PDFs (status Indexed)

`manifest.csv` maps each file to its case and library path; the sync reads it automatically. `fact_document.csv` is a drop-in catalogue with the real file names; `golden_set.csv` is unchanged.
