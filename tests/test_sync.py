import shutil

import docx
from pypdf import PdfWriter

from ferrero.sync.extract import extract
from ferrero.sync.index import DocumentIndex
from ferrero.sync.runner import run_sync
from ferrero.sync.sources import LocalFolderSource, load_manifest, manifest_next_to

from conftest import PACK, catalogue_paths


def sections(file_name):
    return {s.heading: s.blocks for s in extract(file_name, (PACK / "documents" / file_name).read_bytes()).sections}


def test_docx_sections_numbered_items_and_tables():
    judgment = sections("TM-2024-428_Judgment_EN.docx")
    assert list(judgment)[:3] == ["Header", "Parties", "Facts"]
    assert judgment["Operative part"][1].startswith("1. To order the Defendant to pay the Claimant AED 2,288,000")
    report = sections("TM-2026-421_Investigation_Report_EN.docx")
    assert "Check: Security hologram; Genuine reference: Present, colour-shifting; Sample result: Absent; Outcome: Fail" \
        in report["3. Findings"]
    customs = sections("TM-2024-410_Customs_Seizure_Notice_AR.docx")
    assert "الكمية المحجوزة: 1,200 وحدة" in customs["Header"]


def test_pdf_text_recovers_headings_paragraphs_and_drops_footers():
    from ferrero.sync.extract import pdf_sections
    page1 = """Judgment · TM-2024-428 · Confidential · Demo document – all parties and facts are fictional   Page 1
DUBAI COURT OF FIRST INSTANCE – COMMERCIAL
Commercial Case No. 1506/2025
Parties
Claimant: Dolce Group International S.A., a company incorporated in Luxembourg, owner of the
registered trademark VELORA, represented by Gulf IP Partners.
Defendant: Zahrat Al Sahra Trading, represented by its manager.
Operative part
For these reasons, the Court rules:
1. To order the Defendant to pay the Claimant AED 2,288,000 as compensation for material and
moral damage."""
    page2 = """Judgment · TM-2024-428 · Confidential · Demo document – all parties and facts are fictional   Page 2
2. To order the Defendant to cease all use of the VELORA mark or any confusingly similar sign on
goods, packaging, advertising or online listings."""
    sections = {s.heading: s.blocks for s in pdf_sections([page1, page2])}
    assert list(sections) == ["Header", "Parties", "Operative part"]
    assert sections["Header"] == ["DUBAI COURT OF FIRST INSTANCE – COMMERCIAL Commercial Case No. 1506/2025"]
    assert len(sections["Parties"]) == 2 and sections["Parties"][0].endswith("represented by Gulf IP Partners.")
    assert sections["Operative part"][1].startswith("1. To order the Defendant to pay the Claimant AED 2,288,000")
    assert sections["Operative part"][2].startswith("2. To order the Defendant to cease")  # continues across the page break
    assert not any("Demo document" in b for blocks in sections.values() for b in blocks)


def test_pack_documents_get_their_case_access_group(index):
    by_file = {d["file_name"]: d for d in index.catalogue()}
    assert by_file["TM-2024-403_Judgment_AR.docx"]["access_group"] == "Legal-KSA"
    assert by_file["TM-2026-414_Cease_and_Desist_AR.docx"]["access_group"] == "Legal-MENA"
    assert by_file["TM-2024-428_Judgment_EN.docx"]["access_group"] == "Legal-UAE"
    assert all(d["index_status"] == "Indexed" for d in by_file.values())


def write_docx(path, heading, paragraphs):
    d = docx.Document()
    d.add_paragraph(heading)
    d.add_heading("Operative part", level=1)
    for p in paragraphs:
        d.add_paragraph(p)
    d.save(path)


def test_files_are_tied_to_cases_only_when_the_content_agrees(tmp_path, model):
    folder = tmp_path / "docs"
    folder.mkdir()
    shutil.copy2(PACK / "documents" / "TM-2024-428_Judgment_EN.docx", folder)
    case = model.case("TM-2024-412")  # a real tracker case; its mark and infringer must appear in a genuine document
    write_docx(folder / "judgment TM-2024-412.docx", "JUDGMENT IN CASE TM-2024-412",
               [f"{case['mark_name']} v. {case['infringer_name']}: the Defendant shall pay AED 100,000."])
    write_docx(folder / "TM-2024-412_judgment (1).docx", "JUDGMENT IN CASE TM-2024-412",
               ["Contoso Holding v. Al Yamama Holding Group: 1,200,000 AED."])            # reuses the number, other parties
    write_docx(folder / "scan0001.docx", "JUDGMENT IN CASE TM-2024-412 and TM-2024-413", ["Mixed references."])
    write_docx(folder / "TM-2024-412_claim.docx", "STATEMENT OF CLAIM TM-2024-413", ["Wrong case in the text."])
    write_docx(folder / "TM-2099-999_judgment.docx", "JUDGMENT IN CASE TM-2099-999", ["Unknown case."])
    write_docx(folder / "notes.docx", "Meeting notes", ["No case reference at all."])
    blank = PdfWriter()
    blank.add_blank_page(595, 842)
    with open(folder / "TM-2024-403_judgment.pdf", "wb") as f:
        blank.write(f)
    locked = PdfWriter()
    locked.add_blank_page(595, 842)
    locked.encrypt(user_password="secret", algorithm="RC4-128")
    with open(folder / "TM-2024-403_licence.pdf", "wb") as f:
        locked.write(f)
    shutil.copy2(folder / "TM-2024-428_Judgment_EN.docx", folder / "copy of judgment TM-2024-428.docx")

    ix = DocumentIndex(tmp_path / "index.sqlite")
    result = run_sync(LocalFolderSource(folder, library_path_for=catalogue_paths(model)), ix, model)
    reasons = dict(result.skipped)
    assert sorted(result.indexed) == ["TM-2024-428_Judgment_EN.docx", "judgment TM-2024-412.docx"]
    assert reasons["TM-2024-412_judgment (1).docx"].startswith("Content does not match TM-2024-412")
    assert reasons["scan0001.docx"] == "The text refers to several cases (TM-2024-412, TM-2024-413)"
    assert reasons["TM-2024-412_claim.docx"] == "File name refers to TM-2024-412 but the text refers to TM-2024-413"
    assert reasons["TM-2099-999_judgment.docx"] == "Case TM-2099-999 is not in the case tracker"
    assert reasons["notes.docx"] == "No case number in the file name or text"
    assert reasons["TM-2024-403_licence.pdf"] == "Password-protected PDF"
    assert reasons["copy of judgment TM-2024-428.docx"] == "Duplicate of TM-2024-428_Judgment_EN.docx"
    assert result.awaiting_ocr == ["TM-2024-403_judgment.pdf"]  # image-only: waits for text recognition
    statuses = {d["file_name"]: d for d in ix.catalogue()}
    scan = statuses["TM-2024-403_judgment.pdf"]
    assert (scan["case_id"], scan["index_status"], scan["extraction"]) == ("TM-2024-403", "Pending", "ocr")
    assert scan["skip_reason"] == "Scanned PDF – waiting for text recognition"
    assert statuses["notes.docx"]["access_group"] == ""                       # never searchable by anyone


def test_incremental_runs_reprocess_only_changes(tmp_path, model, pack_docs):
    folder = tmp_path / "docs"
    shutil.copytree(pack_docs, folder)
    ix = DocumentIndex(tmp_path / "index.sqlite")
    source = LocalFolderSource(folder, library_path_for=catalogue_paths(model))
    assert len(run_sync(source, ix, model).indexed) == 12
    again = run_sync(source, ix, model)
    assert (again.unchanged, again.indexed, again.deleted) == (12, [], 0)
    (folder / "TM-2026-408_Cease_and_Desist_EN.docx").unlink()
    write_docx(folder / "TM-2024-407_Judgment_EN.docx", "SHARJAH FEDERAL COURT", ["VELORA v. Bright Star Foodstuff LLC: amended."])
    third = run_sync(source, ix, model)
    assert (third.unchanged, third.indexed, third.deleted) == (10, ["TM-2024-407_Judgment_EN.docx"], 1)
    assert ix.stats()["indexed"] == 11


def test_manifest_maps_messy_names_to_cases(tmp_path, model):
    folder = tmp_path / "documents_150"
    folder.mkdir()
    shutil.copy2(PACK / "documents" / "TM-2024-428_Judgment_EN.docx", folder / "scan1234.docx")
    shutil.copy2(PACK / "documents" / "TM-2024-407_Judgment_EN.docx", folder / "judgment TM-2024-999 (final).docx")
    meta = tmp_path / "documents_150_meta"
    meta.mkdir()
    (meta / "manifest.csv").write_text(
        "file,doc_id,case_id,doc_type,language,pages,scanned,index_status,password,library_path,source\n"
        "scan1234.docx,DOC-0126,TM-2024-428,Judgment,EN,3,False,Indexed,,/sites/Legal/Cases/UAE/TM-2024-428/scan1234.docx,pack\n"
        "judgment TM-2024-999 (final).docx,DOC-0031,TM-2024-407,Judgment,EN,2,False,Indexed,hunter2,"
        "/sites/Legal/Cases/UAE/TM-2024-407/judgment TM-2024-999 (final).docx,pack\n", encoding="utf-8")
    manifest = load_manifest(manifest_next_to(folder))
    assert len(manifest) == 2 and all("password" not in row for row in manifest.values())

    ix = DocumentIndex(tmp_path / "ix.sqlite")
    result = run_sync(LocalFolderSource(folder, manifest=manifest), ix, model)
    assert sorted(result.indexed) == ["judgment TM-2024-999 (final).docx", "scan1234.docx"]
    docs = {d["file_name"]: d for d in ix.catalogue()}
    assert docs["judgment TM-2024-999 (final).docx"]["case_id"] == "TM-2024-407"  # the manifest wins over the name
    assert docs["scan1234.docx"]["doc_id"] == "DOC-0126"
    assert docs["scan1234.docx"]["library_path"] == "/sites/Legal/Cases/UAE/TM-2024-428/scan1234.docx"


def test_status_file_matches_fact_document_shape(tmp_path, model, pack_docs):
    out = tmp_path / "status.csv"
    run_sync(LocalFolderSource(pack_docs, library_path_for=catalogue_paths(model)), DocumentIndex(tmp_path / "ix.sqlite"),
             model, status_csv=out)
    header = out.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert header[:3] == ["doc_id", "case_id", "file_name"] and "index_status" in header and "skip_reason" in header
