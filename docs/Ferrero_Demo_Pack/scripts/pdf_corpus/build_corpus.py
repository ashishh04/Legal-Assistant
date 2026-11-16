"""Build the 150-PDF demo corpus.

    python scripts/pdf_corpus/build_corpus.py            # full build -> documents_150/ + documents_150_meta/
    python scripts/pdf_corpus/build_corpus.py --test     # a few documents per type -> scripts/out/pdf_corpus/test/

The 12 pack DOCX are converted as they are (their Arabic font is switched to Segoe UI so the
PDF text layer is correct). 138 further fact_document rows become new PDFs written from the
case data. Scanned rows become image-only PDFs, password rows are AES-256 encrypted, and the
'OCR below threshold' rows are degraded scans, so the files behave the way index_status says.
The user's own files in documents/ are never modified.
"""
import argparse, csv, hashlib, os, re, shutil, subprocess, sys, time, zipfile, datetime as dt
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pymupdf
from corpus_data import Data, PACK, DISCLAIMER, DOC_AR, SENS_AR, select, file_name, doc_date_for, d, rng
from corpus_docx import DocBuilder
from corpus_templates import TEMPLATES, X, author_for
import corpus_assets as A

WORK = PACK / 'scripts' / 'out' / 'pdf_corpus'
OUT = PACK / 'documents_150'
META = PACK / 'documents_150_meta'
PASSWORD = 'Demo#Locked2026'
PS1 = PACK / 'scripts' / 'docx_to_pdf.ps1'


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


# ----------------------------------------------------------------------------- plan
def plan(D):
    samples, chosen = select(D)
    taken = {n.lower() for n in os.listdir(PACK / 'documents')}      # never reuse a name of the user's files
    items = []
    for r in samples:
        name = Path(r['title']).stem + '.pdf'
        taken.add(name.lower())
        items.append(dict(row=r, source='pack sample', file=name, scanned=False, quality=None, password=False, doc_date=d(r['doc_date']), ocr=''))
    for r in chosen:
        c = D.ctx(r['case_id'])
        status, why = r['index_status'], r['skip_reason']
        scanned = r['scanned'] == 'True' or why == 'OCR confidence below threshold'
        R = rng('ocr', r['doc_id'])
        ocr = r['ocr_confidence']
        if why == 'OCR confidence below threshold':
            quality, ocr = 'poor', f'{R.uniform(0.58, 0.76):.2f}'
        elif status == 'Indexed (flagged)':
            quality = 'fair'; ocr = ocr or f'{R.uniform(0.82, 0.849):.2f}'
        elif scanned:
            ocr = ocr or f'{R.uniform(0.88, 0.97):.2f}'
            quality = 'good' if float(ocr) >= 0.9 else 'fair'
        else:
            quality, ocr = None, ''
        dd = doc_date_for(r['doc_type'], c)
        name = file_name(r, c, scanned, taken, dd)
        items.append(dict(row=r, source='generated', file=name, scanned=scanned, quality=quality, password=why == 'Password-protected PDF', doc_date=dd, ocr=ocr))
    return items


def test_subset(items):
    """One generated document per (type, language), plus two scans, one password file and one pack doc."""
    seen, out = set(), []
    for it in items:
        k = (it['row']['doc_type'], it['row']['language'])
        if it['source'] == 'generated' and k not in seen and not it['scanned']:
            seen.add(k); out.append(it)
    out += [it for it in items if it['scanned']][:2] + [it for it in items if it['password']][:1]
    out += [it for it in items if it['source'] == 'pack sample' and it['row']['language'] == 'AR'][:1]
    return out


# ----------------------------------------------------------------------------- docx
def write_docx(D, it, docx_dir, assets_dir):
    r = it['row']
    if it['source'] == 'pack sample':
        patch_pack_docx(PACK / 'documents' / r['title'], docx_dir / f'{r["doc_id"]}.docx')
        return
    c = D.ctx(r['case_id'])
    t, lang = r['doc_type'], r['language']
    if lang == 'AR':
        footer = f'{DOC_AR[t]} · {r["case_id"]} · {SENS_AR.get(r["sensitivity"], r["sensitivity"])} · {DISCLAIMER["ar"]}'
    else:
        footer = f'{t} · {r["case_id"]} · {r["sensitivity"]} · {DISCLAIMER["en"]}'
    meta = dict(title=f'{DOC_AR[t] if lang == "AR" else t} – {r["case_id"]}', subject=t, author=author_for(t, c),
                keywords=f'{r["case_id"]}; {c["mark"]}; {t}; {c["country"]}', comments=DISCLAIMER['en'],
                when=dt.datetime.combine(it['doc_date'], dt.time(10, 30)))
    b = DocBuilder(lang, footer, meta)
    TEMPLATES[t](b, X(r, c, assets_dir, it['doc_date']))
    b.save(docx_dir / f'{r["doc_id"]}.docx')


def patch_pack_docx(src, dst):
    """Copy a pack DOCX, switching the complex-script (Arabic) font from Arial to Segoe UI."""
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename.startswith('word/') and info.filename.endswith('.xml'):
                data = data.replace(b'w:cs="Arial"', b'w:cs="Segoe UI"')
            zout.writestr(info, data)


# ----------------------------------------------------------------------------- Word conversion with a watchdog
def word_pids():
    out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq WINWORD.EXE', '/FO', 'CSV', '/NH'], capture_output=True, text=True).stdout
    return {int(m.group(1)) for m in re.finditer(r'"WINWORD\.EXE","(\d+)"', out)}


def convert(docx_dir, pdf_dir):
    before = word_pids()        # Word windows the user already has open are never touched
    for attempt in range(1, 4):
        todo = [p for p in docx_dir.glob('*.docx') if not (pdf_dir / (p.stem + '.pdf')).exists()]
        if not todo:
            return
        log(f'Word conversion attempt {attempt}: {len(todo)} documents')
        try:
            res = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(PS1), '-InDir', str(docx_dir), '-OutDir', str(pdf_dir)],
                                 capture_output=True, text=True, timeout=90 + 12 * len(todo))
            log(res.stdout.strip()[-800:])
        except subprocess.TimeoutExpired:
            log('Word conversion timed out; stopping the Word instance started by this build')
        for pid in word_pids() - before:
            subprocess.run(['taskkill', '/F', '/PID', str(pid)], capture_output=True)
    missing = [p.name for p in docx_dir.glob('*.docx') if not (pdf_dir / (p.stem + '.pdf')).exists()]
    if missing:
        raise SystemExit(f'Word could not convert: {missing}')


# ----------------------------------------------------------------------------- post-processing
def finalize(D, it, pdf_dir, out_dir, work):
    r = it['row']
    src, out = pdf_dir / f'{r["doc_id"]}.pdf', out_dir / it['file']
    if it['scanned']:
        target = work / f'{r["doc_id"]}_scan.pdf' if it['password'] else out
        flagged = 1 if r['index_status'] == 'Indexed (flagged)' else 0
        pages = A.scanify(src, target, it['quality'], r['doc_id'], it['doc_date'], flagged_pages=flagged)
        if it['password']:
            A.encrypt_pdf(target, out, PASSWORD)
            target.unlink()
    else:
        c = D.ctx(r['case_id'])
        t = r['doc_type']
        meta = dict(title=f'{DOC_AR[t] if r["language"] == "AR" else t} – {r["case_id"]}', subject=t, keywords=f'{r["case_id"]}; {c["mark"]}; {t}; {c["country"]}')
        if it['source'] == 'generated':
            meta['author'] = author_for(t, c)
        pages = A.finalize_text_pdf(src, out, meta, it['doc_date'], PASSWORD if it['password'] else None)
    it['pages'] = pages


# ----------------------------------------------------------------------------- metadata
def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def write_meta(D, items):
    META.mkdir(parents=True, exist_ok=True)
    by_id = {it['row']['doc_id']: it for it in items}
    rows = []
    for r in D.docs:
        r = dict(r)
        it = by_id.get(r['doc_id'])
        if it:
            c = D.ctx(r['case_id'])
            r['title'] = it['file']
            r['library_path'] = f'{c["library"]}/{it["file"]}'
            r['sample_file'] = 'True'
            r['pages'] = str(it['pages'])
            if it['source'] == 'generated':
                r['doc_date'] = it['doc_date'].isoformat()
                r['scanned'] = str(bool(it['scanned']))
                r['ocr_confidence'] = it['ocr']
            r['chunks'] = '0' if r['index_status'].startswith(('Skipped', 'Pending')) else str(it['pages'] * 5)
        else:
            r['sample_file'] = 'False'
        rows.append(r)
    with open(META / 'fact_document.csv', 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=D.doc_fields); w.writeheader(); w.writerows(rows)
    fields = ['file', 'doc_id', 'case_id', 'doc_type', 'doc_type_ar', 'language', 'doc_date', 'pages', 'scanned', 'ocr_confidence', 'index_status', 'skip_reason',
              'password', 'sensitivity', 'access_group', 'country', 'mark', 'library_path', 'source', 'bytes', 'sha256']
    with open(META / 'manifest.csv', 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for it in sorted(items, key=lambda i: (i['row']['case_id'], i['row']['doc_id'])):
            r = it['row']; c = D.ctx(r['case_id']); p = OUT / it['file']
            w.writerow(dict(file=it['file'], doc_id=r['doc_id'], case_id=r['case_id'], doc_type=r['doc_type'], doc_type_ar=r['doc_type_ar'], language=r['language'],
                            doc_date=it['doc_date'].isoformat(), pages=it['pages'], scanned=it['scanned'], ocr_confidence=it['ocr'], index_status=r['index_status'],
                            skip_reason=r['skip_reason'], password=PASSWORD if it['password'] else '', sensitivity=r['sensitivity'], access_group=r['access_group'],
                            country=c['country'], mark=c['mark'], library_path=f'{c["library"]}/{it["file"]}', source=it['source'], bytes=p.stat().st_size, sha256=sha256(p)))
    golden = []
    samples = {Path(it['row']['title']).name: it['file'] for it in items if it['source'] == 'pack sample'}
    for g in D.golden:
        g = dict(g)
        g['source'] = '; '.join(samples.get(s.strip(), s.strip()) for s in g['source'].split(';')) if g['source'] else ''
        golden.append(g)
    with open(META / 'golden_set.csv', 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=D.golden_fields); w.writeheader(); w.writerows(golden)


# ----------------------------------------------------------------------------- validation
def validate(D, items, out_dir, full=True):
    problems = []
    pdfs = sorted(out_dir.glob('*.pdf'))
    if full and len(pdfs) != 150:
        problems.append(f'{len(pdfs)} PDFs in {out_dir}, expected 150')
    types = Counter(it['row']['doc_type'] for it in items)
    if full and len(types) != 12:
        problems.append(f'only {len(types)} document types')
    for it in items:
        p = out_dir / it['file']
        if not p.exists():
            problems.append(f'missing {it["file"]}'); continue
        doc = pymupdf.open(p)
        if it['password']:
            if not doc.needs_pass:
                problems.append(f'{it["file"]}: should be password-protected')
            elif not doc.authenticate(PASSWORD):
                problems.append(f'{it["file"]}: password does not open it')
        text = ''.join(pg.get_text() for pg in doc)
        if it['scanned']:
            if text.strip():
                problems.append(f'{it["file"]}: scan has a text layer')
        elif it['row']['case_id'] not in text and not (it['source'] == 'pack sample'):
            problems.append(f'{it["file"]}: case id not found in text layer')
        if it['row']['language'] == 'AR' and not it['scanned'] and 'العالمة' in text:
            problems.append(f'{it["file"]}: reversed lam-alef in text layer')
        if re.search(r'\b(AED|SAR|EGP|JOD|KWD|QAR|OMR|TRY|INR) 0(?![.,\d])|(?<![\d,.])0 (درهم|ريال|جنيه|دينار|ليرة|روبية)|approximately 0 units|\b1 sessions\b', text):
            problems.append(f'{it["file"]}: zero amount in text')
        if it['source'] == 'generated' and re.search(r'\(\([A-Za-z]|[A-Za-z0-9]\)\)', text):
            problems.append(f'{it["file"]}: doubled bracket next to Latin text')
        if it['source'] == 'generated' and it['row']['language'] == 'EN' and re.search(r'[؀-ۿ]{3,}', text):
            problems.append(f'{it["file"]}: Arabic text in an English document')
        doc.close()
    return problems


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--test', action='store_true', help='build a small sample into scripts/out/pdf_corpus/test')
    ap.add_argument('--skip-convert', action='store_true', help='reuse PDFs already converted by Word')
    args = ap.parse_args()
    D = Data()
    items = plan(D)
    log(f'planned {len(items)} documents:', dict(Counter(it['row']['doc_type'] for it in items)))
    work = WORK / ('test' if args.test else 'full')
    if args.test:
        items = test_subset(items)
    docx_dir, pdf_dir, assets_dir = work / 'docx', work / 'pdf', work / 'assets'
    out_dir = work / 'out' if args.test else OUT
    if not args.skip_convert:
        for p in (docx_dir, pdf_dir, assets_dir):
            shutil.rmtree(p, ignore_errors=True)
    for p in (docx_dir, pdf_dir, assets_dir, out_dir):
        p.mkdir(parents=True, exist_ok=True)
    if out_dir == OUT:
        for old in OUT.glob('*.pdf'):            # documents_150 is owned by this build
            old.unlink()
    if not args.skip_convert:
        for k, it in enumerate(items, 1):
            write_docx(D, it, docx_dir, assets_dir)
            if k % 25 == 0:
                log(f'docx {k}/{len(items)}')
        log(f'wrote {len(items)} docx')
    convert(docx_dir, pdf_dir)
    for it in items:
        finalize(D, it, pdf_dir, out_dir, work)
    log('post-processing done')
    problems = validate(D, items, out_dir, full=not args.test)
    if not args.test:
        write_meta(D, items)
    print('\n'.join(['VALIDATION PROBLEMS:'] + problems) if problems else 'Validation passed')
    print(f'output: {out_dir}')
    print(Counter(it['row']['doc_type'] for it in items))
    print('languages', Counter(it['row']['language'] for it in items), '| scanned', sum(bool(it['scanned']) for it in items),
          '| password', sum(it['password'] for it in items), '| pages', sum(it.get('pages', 0) for it in items))


if __name__ == '__main__':
    main()
