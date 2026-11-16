"""Complete the corpus: one file for every fact_document row -> documents_full/ (508 PDFs) + documents_full_meta/.

    python scripts/pdf_corpus/extend_corpus.py              # build documents_full/
    python scripts/pdf_corpus/extend_corpus.py --skip-convert   # reuse PDFs Word already converted

The 150 files of documents_150/ are copied byte for byte, so scans that were already recognised keep their
cached OCR results (data/ocr is keyed by content hash). The catalogue rows with no file yet are written from
the case data with the same templates as build_corpus.py, as text PDFs, so every case's documents are
searchable as soon as they are synced. documents_150/ itself is not changed.
"""
import argparse, csv, shutil, sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_corpus import PACK, WORK, write_docx, convert, finalize, validate, sha256, log
from corpus_data import Data, file_name, doc_date_for

SRC = PACK / 'documents_150'
SRC_META = PACK / 'documents_150_meta'
OUT = PACK / 'documents_full'
META = PACK / 'documents_full_meta'
FIELDS = ['file', 'doc_id', 'case_id', 'doc_type', 'doc_type_ar', 'language', 'doc_date', 'pages', 'scanned', 'ocr_confidence',
          'index_status', 'skip_reason', 'password', 'sensitivity', 'access_group', 'country', 'mark', 'library_path', 'source',
          'bytes', 'sha256']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--skip-convert', action='store_true', help='reuse PDFs already converted by Word')
    args = ap.parse_args()
    D = Data()
    existing = list(csv.DictReader(open(SRC_META / 'manifest.csv', encoding='utf-8')))
    have = {r['doc_id'] for r in existing}
    taken = {r['file'].lower() for r in existing} | {p.name.lower() for p in (PACK / 'documents').iterdir()}
    items = []
    for r in sorted((r for r in D.docs if r['doc_id'] not in have), key=lambda r: r['doc_id']):
        c = D.ctx(r['case_id'])
        dd = doc_date_for(r['doc_type'], c)
        items.append(dict(row=r, source='generated', file=file_name(r, c, False, taken, dd), scanned=False, quality=None,
                          password=False, doc_date=dd, ocr=''))
    log(f'{len(existing)} files to copy, {len(items)} to write:', dict(Counter(it['row']['doc_type'] for it in items)))

    work = WORK / 'extend'
    docx_dir, pdf_dir, assets_dir = work / 'docx', work / 'pdf', work / 'assets'
    if not args.skip_convert:
        for p in (docx_dir, pdf_dir, assets_dir):
            shutil.rmtree(p, ignore_errors=True)
    for p in (docx_dir, pdf_dir, assets_dir, OUT, META):
        p.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob('*.pdf'):                       # documents_full is owned by this script
        old.unlink()
    for r in existing:
        shutil.copy2(SRC / r['file'], OUT / r['file'])
    log(f'copied {len(existing)} files from {SRC.name}')

    failed = []
    if not args.skip_convert:
        for k, it in enumerate(items, 1):
            try:
                write_docx(D, it, docx_dir, assets_dir)
            except Exception as e:                       # a template that cannot render this row: report, don't stop
                failed.append(f'{it["row"]["doc_id"]} {it["row"]["doc_type"]}: {e!r}')
            if k % 50 == 0:
                log(f'docx {k}/{len(items)}')
        log(f'wrote {len(items) - len(failed)} docx' + (f', {len(failed)} failed' if failed else ''))
    convert(docx_dir, pdf_dir)
    done = []
    for it in items:
        if not (pdf_dir / f'{it["row"]["doc_id"]}.pdf').exists():
            continue
        finalize(D, it, pdf_dir, OUT, work)
        done.append(it)
    log(f'post-processing done: {len(done)} new PDFs')
    problems = validate(D, done, OUT, full=False)

    rows = [dict(r) for r in existing]
    for it in done:
        r, c, p = it['row'], D.ctx(it['row']['case_id']), OUT / it['file']
        rows.append(dict(file=it['file'], doc_id=r['doc_id'], case_id=r['case_id'], doc_type=r['doc_type'], doc_type_ar=r['doc_type_ar'],
                         language=r['language'], doc_date=it['doc_date'].isoformat(), pages=it['pages'], scanned=False, ocr_confidence='',
                         index_status='Indexed', skip_reason='', password='', sensitivity=r['sensitivity'], access_group=r['access_group'],
                         country=c['country'], mark=c['mark'], library_path=f'{c["library"]}/{it["file"]}', source='generated',
                         bytes=p.stat().st_size, sha256=sha256(p)))
    rows.sort(key=lambda x: (x['case_id'], x['doc_id']))
    with open(META / 'manifest.csv', 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    shutil.copy2(SRC_META / 'golden_set.csv', META / 'golden_set.csv')
    by_id = {x['doc_id']: x for x in rows}
    base = {r['doc_id']: r for r in csv.DictReader(open(SRC_META / 'fact_document.csv', encoding='utf-8'))}
    with open(META / 'fact_document.csv', 'w', encoding='utf-8', newline='') as f:      # drop-in catalogue with the real names
        w = csv.DictWriter(f, fieldnames=D.doc_fields); w.writeheader()
        for r in D.docs:
            if r['doc_id'] in have:                     # as documents_150 described it
                w.writerow(base[r['doc_id']]); continue
            r, m = dict(r), by_id.get(r['doc_id'])
            if m:
                r.update(title=m['file'], library_path=m['library_path'], sample_file='True', pages=str(m['pages']),
                         doc_date=m['doc_date'], scanned='False', ocr_confidence='', index_status='Indexed', skip_reason='',
                         chunks=str(int(m['pages']) * 5))
            w.writerow(r)
    (META / 'README.md').write_text(
        '# documents_full\n\nOne PDF for every row of fact_document (508), built by `scripts/pdf_corpus/extend_corpus.py`.\n\n'
        f'- {len(existing)} files copied byte for byte from documents_150 (scans, password-protected and flagged files included)\n'
        f'- {len(done)} files written from the case data as text PDFs (status Indexed)\n\n'
        '`manifest.csv` maps each file to its case and library path; the sync reads it automatically. '
        '`fact_document.csv` is a drop-in catalogue with the real file names; `golden_set.csv` is unchanged.\n', encoding='utf-8')

    pdfs = len(list(OUT.glob('*.pdf')))
    print('\n'.join(['PROBLEMS:'] + failed + problems) if failed or problems else 'Validation passed')
    print(f'output: {OUT} ({pdfs} PDFs, {len(rows)} manifest rows, {len({x["case_id"] for x in rows})} cases)')


if __name__ == '__main__':
    main()
