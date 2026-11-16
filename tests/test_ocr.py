"""Text recognition for scans: model output parsing, the cache, the sync and the web viewer (no model needed)."""
import json
import math
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from ferrero.ocr.output import ocr_sections, page_blocks, table_rows
from ferrero.ocr.reader import OcrReader, recognize_pdf
from ferrero.ocr.results import OcrCache, OcrPage, OcrResult
from ferrero.ocr.scans import ScanError, page_images
from ferrero.ocr.server import UnlimitedOcrServer, confidence_from_logprobs
from ferrero.sync.extract import AWAITING_OCR, LOW_OCR_CONFIDENCE, ExtractionError, extract
from ferrero.sync.index import DocumentIndex
from ferrero.sync.runner import run_sync
from ferrero.sync.sources import LocalFolderSource

JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00page-image\xff\xd9"  # stands in for a scanner's JPEG (never decoded here)

# Unlimited-OCR-2's own markup: <BLOCK>label<LEVELn>[box]<FORK>text, <MERGE> when a paragraph continues.
PAGE_1 = """<PAGE><BLOCK>header[60, 20, 940, 40]<FORK>AL NOOR LEGAL CONSULTANTS
<BLOCK>title<LEVEL1>[300, 60, 700, 90]<FORK>JUDGMENT
<BLOCK>text[80, 100, 920, 160]<FORK>Case TM-2024-403 · VELORA v. Desert Rose Trading. The Court, having heard the parties,
<MERGE>
<BLOCK>text[80, 160, 920, 180]<FORK>finds that the defendant sold counterfeit goods bearing the VELORA mark.
<BLOCK>title<LEVEL2>[80, 190, 400, 205]<FORK>Operative part
<BLOCK>other[80, 210, 920, 270]<FORK>
<BLOCK>text[80, 210, 920, 240]<FORK>1. The defendant shall pay AED 120,000 in damages.
<BLOCK>text[80, 240, 920, 270]<FORK>2. The infringing goods shall be destroyed.
<BLOCK>table[80, 280, 920, 330]<FORK><table><tr><td>Item</td><td>Amount</td><td>Currency</td></tr><tr><td>Damages</td><td>120,000</td><td>AED</td></tr></table>
<BLOCK>title<LEVEL2>[80, 700, 300, 715]<FORK>For the Court
<BLOCK>image[80, 720, 200, 760]<FORK>
<BLOCK>title<LEVEL2>[80, 770, 300, 785]<FORK>Judge Hessa Al Mansouri
<BLOCK>text[80, 787, 300, 800]<FORK>Presiding Judge
<BLOCK>footer[60, 960, 940, 980]<FORK>Judgment · TM-2024-403 · Demo document – all parties and facts are fictional Page 1 of 2"""
PAGE_2 = """<PAGE><BLOCK>header[60, 20, 940, 40]<FORK>AL NOOR LEGAL CONSULTANTS
<BLOCK>text[80, 100, 920, 160]<FORK>The judgment is final and enforceable.
<BLOCK>page_number[480, 960, 520, 980]<FORK>2"""


def make_scan_pdf(pages: int = 2, image: bytes = JPEG) -> bytes:
    """A minimal image-only PDF: one full-page JPEG per page, no text layer (what a scanner writes)."""
    objects: list[bytes] = []
    kids = []
    for n in range(pages):
        img_no, content_no, page_no = 4 + 3 * n, 5 + 3 * n, 3 + 3 * n
        kids.append(f"{page_no} 0 R")
        content = b"q 595 0 0 842 0 0 cm /Im0 Do Q"
        objects += [
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /XObject << /Im0 {img_no} 0 R >> >>"
            f" /Contents {content_no} 0 R >>".encode(),
            f"<< /Type /XObject /Subtype /Image /Width 1406 /Height 1988 /ColorSpace /DeviceGray /BitsPerComponent 8"
            f" /Filter /DCTDecode /Length {len(image)} >>\nstream\n".encode() + image + b"\nendstream",
            f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream",
        ]
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {pages} >>".encode()] + objects
    out, offsets = bytearray(b"%PDF-1.7\n"), []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


class FakeEngine:
    engine, model, mode = "Unlimited-OCR-2", "baidu/Unlimited-OCR-2@test", "gundam"

    def __init__(self, pages: list[str], confidence: list[float], fail_on: int | None = None):
        self.pages, self.confidence, self.fail_on, self.calls = pages, confidence, fail_on, []

    def recognize_page(self, image: bytes, number: int = 1) -> OcrPage:
        self.calls.append(number)
        if number == self.fail_on:
            self.fail_on = None
            raise RuntimeError("out of memory")
        return OcrPage(number=number, text=self.pages[number - 1], confidence=self.confidence[number - 1], tokens=100,
                       seconds=1.5)


def test_layout_blocks_become_sections_with_titles_tables_and_no_furniture():
    blocks = page_blocks(PAGE_1)
    assert [b.label for b in blocks][:5] == ["header", "title", "text", "text", "title"]
    assert blocks[1].level == 1 and blocks[3].continues and not blocks[2].continues
    sections = {s.heading: s.blocks for s in ocr_sections([PAGE_1, PAGE_2])}
    assert list(sections) == ["JUDGMENT", "Operative part"]
    assert sections["JUDGMENT"] == ["Case TM-2024-403 · VELORA v. Desert Rose Trading. The Court, having heard the parties, "
                                    "finds that the defendant sold counterfeit goods bearing the VELORA mark."]  # merged
    op = sections["Operative part"]
    assert op[:2] == ["1. The defendant shall pay AED 120,000 in damages.", "2. The infringing goods shall be destroyed."]
    assert "Item: Damages; Amount: 120,000; Currency: AED" in op
    assert op[-4:] == ["For the Court", "Judge Hessa Al Mansouri", "Presiding Judge", "The judgment is final and enforceable."]
    text = json.dumps(sections, ensure_ascii=False)
    assert "AL NOOR" not in text and "fictional" not in text and '"2"' not in text and "<" not in text


def test_real_model_output_reads_as_a_document():
    """Page 1 of 'power-of-attorney - Amman (final).pdf' exactly as Unlimited-OCR-2 returned it on this machine."""
    raw = (Path(__file__).parent / "data" / "unlimited_ocr_poa.txt").read_text(encoding="utf-8")
    sections = {s.heading: s.blocks for s in ocr_sections([raw])}
    assert list(sections) == ["SPECIAL POWER OF ATTORNEY", "Notarial certification"]
    poa = sections["SPECIAL POWER OF ATTORNEY"]
    assert poa[0] == "No. POA-2025-415-2025 · 05 July 2025"
    assert poa[1].startswith("Dolce Group International S.A., a société anonyme") and "hereby appoints Tariq Haddadin" in poa[1]
    assert [b[:2] for b in poa[2:7]] == ["a)", "b)", "c)", "d)", "e)"]
    assert "Signed before me, Maître Anne Schmit" in sections["Notarial certification"][0]
    assert "fictional" not in json.dumps(sections, ensure_ascii=False)


def test_deepseek_style_markup_and_plain_text_are_understood():
    raw = "<|ref|>title<|/ref|><|det|>[[10, 10, 500, 40]]<|/det|>\n# STATEMENT OF CLAIM\n\n" \
          "<|ref|>text<|/ref|><|det|>[[10, 50, 900, 120]]<|/det|>\nThe Claimant owns the **VELORA** mark in the UAE."
    sections = ocr_sections([raw])
    assert [(s.heading, s.blocks) for s in sections] == [("STATEMENT OF CLAIM", ["The Claimant owns the VELORA mark in the UAE."])]
    plain = ocr_sections(["JUDGMENT\nThe Court finds for the claimant in full and awards damages of AED 50,000 today."])
    assert plain and plain[0].blocks
    assert table_rows("<table><tr><td>Court</td><td>Dubai Courts</td></tr></table>") == ["Court: Dubai Courts"]


def test_cache_round_trip_partials_and_page_images(tmp_path):
    cache = OcrCache(tmp_path)
    sha = "a" * 64
    with pytest.raises(ValueError):
        cache.get("../../etc/passwd")
    pages = [OcrPage(1, "one", 0.97), OcrPage(2, "two", 0.71)]
    cache.put_partial(sha, "m", "gundam", pages[:1])
    assert cache.partial(sha, "m", "gundam") == pages[:1] and cache.partial(sha, "m", "base") == []
    cache.put(OcrResult(sha, "Unlimited-OCR-2", "m", pages, mode="gundam", file_name="scan.pdf"))
    got = cache.get(sha)
    assert got.pages == pages and got.confidence == pytest.approx(0.84) and cache.partial(sha, "m", "gundam") == []
    cache.save_page_images(sha, [JPEG, b"\x89PNG\r\n\x1a\n...."])
    assert cache.page_image(sha, 1) == (JPEG, "image/jpeg") and cache.page_image(sha, 2)[1] == "image/png"
    assert cache.page_image(sha, 3) is None and [r.sha256 for r in cache] == [sha]


def test_recognition_resumes_after_a_failure_and_keeps_the_scan_pages(tmp_path):
    pdf = make_scan_pdf(2)
    from pypdf import PdfReader
    import io

    assert page_images(PdfReader(io.BytesIO(pdf))) == [JPEG, JPEG]  # the stored JPEG, byte for byte
    cache, sha = OcrCache(tmp_path), "b" * 64
    engine = FakeEngine([PAGE_1, PAGE_2], [0.96, 0.93], fail_on=2)
    with pytest.raises(RuntimeError):
        recognize_pdf(engine, pdf, sha, "scan.pdf", cache)
    assert [p.number for p in cache.partial(sha, engine.model, engine.mode)] == [1]
    result = recognize_pdf(engine, pdf, sha, "scan.pdf", cache)
    assert engine.calls == [1, 2, 2] and [p.number for p in result.pages] == [1, 2]  # page 1 was not read twice
    assert cache.page_image(sha, 2) == (JPEG, "image/jpeg")
    with pytest.raises(ScanError):
        page_images(PdfReader(io.BytesIO(_blank_pdf())))


def _blank_pdf() -> bytes:
    import io
    from pypdf import PdfWriter

    w = PdfWriter()
    w.add_blank_page(595, 842)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def test_scans_are_indexed_flagged_or_skipped_by_confidence(tmp_path):
    pdf = make_scan_pdf(2)
    with pytest.raises(ExtractionError) as waiting:
        extract("scan.pdf", pdf)
    assert (waiting.value.reason, waiting.value.status) == (AWAITING_OCR, "Pending")

    def run(confidence):
        reader = OcrReader(OcrCache(tmp_path / str(confidence)), FakeEngine([PAGE_1, PAGE_2], confidence))
        return extract("scan.pdf", pdf, ocr=reader)

    clean = run([0.97, 0.95])
    assert (clean.extraction, clean.flag, clean.pages) == ("ocr", None, 2) and clean.ocr_confidence == pytest.approx(0.96)
    assert run([0.97, 0.84]).flag == "Low-confidence pages flagged for review (page 2)"
    with pytest.raises(ExtractionError) as faint:
        run([0.70, 0.66])
    assert (faint.value.reason, faint.value.status, faint.value.ocr_confidence) == (LOW_OCR_CONFIDENCE, "Skipped", 0.68)


def test_sync_waits_for_recognition_then_indexes_the_recognised_text(tmp_path, model, principals):
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "scan4821.pdf").write_bytes(make_scan_pdf(2))  # a messy scanner name: the text names the case
    ix = DocumentIndex(tmp_path / "ix.sqlite")
    cache = OcrCache(tmp_path / "ocr")
    first = run_sync(LocalFolderSource(folder), ix, model, ocr=OcrReader(cache))
    assert first.awaiting_ocr == ["scan4821.pdf"] and ix.catalogue()[0]["index_status"] == "Pending"

    # The OCR batch fills the cache; the next sync picks the scan up although the file itself did not change.
    data = (folder / "scan4821.pdf").read_bytes()
    import hashlib

    recognize_pdf(FakeEngine([PAGE_1, PAGE_2], [0.97, 0.95]), data, hashlib.sha256(data).hexdigest(), "scan4821.pdf", cache)
    second = run_sync(LocalFolderSource(folder), ix, model, ocr=OcrReader(cache))
    assert second.recognised == 1 and second.indexed == ["scan4821.pdf"]
    doc = ix.catalogue()[0]
    assert (doc["case_id"], doc["extraction"], doc["pages"]) == ("TM-2024-403", "ocr", 2)
    hits = ix.search(principals["ksa"], "damages destroyed", case_id="TM-2024-403")
    assert hits and hits[0].extraction == "ocr" and hits[0].section == "Operative part"
    from ferrero.assistant.tools import _title

    assert _title(hits[0]).endswith("text recognised from a scanned copy)")


def test_batch_finds_scans_and_allows_one_run_at_a_time(tmp_path):
    import io
    import os

    from pypdf import PdfWriter

    from ferrero.ocr.cli import _RunLock, is_scan

    assert is_scan(make_scan_pdf(1)) == (True, "")
    locked = PdfWriter()
    locked.add_blank_page(595, 842)
    locked.encrypt(user_password="secret", algorithm="RC4-128")
    buf = io.BytesIO()
    locked.write(buf)
    assert is_scan(buf.getvalue()) == (False, "password-protected")

    lock = _RunLock(tmp_path)
    assert lock.holder() is None and lock.acquire() and lock.holder() == os.getpid()
    assert not _RunLock(tmp_path).acquire()  # a second run is refused while this process holds the lock
    assert not lock.stop_requested()
    lock.stop_file.write_text("stop")
    assert lock.stop_requested()
    lock.release()
    assert lock.holder() is None and not lock.stop_requested()
    (tmp_path / ".running").write_text("999999")  # a stale lock from a run that died is ignored
    assert _RunLock(tmp_path).acquire()


def test_server_engine_sends_the_page_and_reads_confidence_from_logprobs():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        tokens = [{"token": "<|det|>", "logprob": -0.01}, {"token": "title [1, 2, 3, 4]", "logprob": -3.0},
                  {"token": "<|/det|>", "logprob": -0.01}, {"token": "JUDG", "logprob": math.log(0.9)},
                  {"token": "MENT", "logprob": math.log(0.7)}]
        return httpx.Response(200, json={"choices": [{"message": {"content": "<|det|>title [1, 2, 3, 4]<|/det|>JUDGMENT"},
                                                      "finish_reason": "stop", "logprobs": {"content": tokens}}]})

    engine = UnlimitedOcrServer("http://ocr.example:10000", transport=httpx.MockTransport(handler))
    page = engine.recognize_page(JPEG, 1)
    assert engine.base_url == "http://ocr.example:10000/v1"
    assert seen["temperature"] == 0 and seen["logprobs"] is True
    content = seen["messages"][0]["content"]
    assert content[0]["image_url"]["url"].startswith("data:image/jpeg;base64,") and content[1]["text"] == "Multi page parsing."
    # geometric mean of 0.9 and 0.7; the layout tokens (block label and box) are not counted
    assert page.confidence == pytest.approx(math.sqrt(0.63), abs=1e-4) and page.finish == "stop"
    assert page.text_token_probs == [0.9, 0.7] and page.score == page.confidence
    assert confidence_from_logprobs([]) is None


def test_document_viewer_serves_scan_pages_only_to_users_of_the_case(tmp_path, model, settings, fake_claude):
    import dataclasses
    import hashlib

    from ferrero.assistant.agent import Assistant
    from ferrero.web.app import create_app

    folder = tmp_path / "docs"
    folder.mkdir()
    data = make_scan_pdf(2)
    (folder / "scan4821.pdf").write_bytes(data)
    s = dataclasses.replace(settings, data_dir=tmp_path / "data")
    cache = OcrCache(s.ocr_dir)
    recognize_pdf(FakeEngine([PAGE_1, PAGE_2], [0.97, 0.86]), data, hashlib.sha256(data).hexdigest(), "scan4821.pdf", cache)
    ix = DocumentIndex(s.index_path)
    run_sync(LocalFolderSource(folder), ix, model, ocr=OcrReader(cache))
    doc_id = ix.catalogue()[0]["doc_id"]
    c = TestClient(create_app(s, Assistant(s, model, DocumentIndex(s.index_path, readonly=True), client=fake_claude.client())))

    view = c.get(f"/api/documents/{doc_id}", params={"user_id": "U-05"}).json()  # Legal-KSA: TM-2024-403 is a KSA case
    assert (view["extraction"], view["page_images"], view["index_status"]) == ("ocr", 2, "Indexed (flagged)")
    assert view["page_confidence"] == [0.97, 0.86] and "content_sha" not in view
    assert [s["section"] for s in view["sections"]] == ["JUDGMENT", "Operative part"]
    page = c.get(f"/api/documents/{doc_id}/pages/1", params={"user_id": "U-05"})
    assert page.status_code == 200 and page.headers["content-type"] == "image/jpeg" and page.content == JPEG
    for user in ("U-04",):  # Legal-UAE cannot open a KSA case's documents, scans included
        assert c.get(f"/api/documents/{doc_id}", params={"user_id": user}).status_code == 404
        assert c.get(f"/api/documents/{doc_id}/pages/1", params={"user_id": user}).status_code == 404
    assert c.get(f"/api/documents/{doc_id}/pages/9", params={"user_id": "U-05"}).status_code == 404
