import json

from ferrero.assistant.tools import NO_DOCUMENT_ACCESS, TOOLS, ToolBox


def test_search_ranks_the_operative_part_first(index, principals):
    hits = index.search(principals["ops"], "damages awarded compensation", case_id="TM-2024-428")
    assert hits[0].section == "Operative part"
    assert any("AED 2,288,000" in b for b in hits[0].blocks)


def test_arabic_search(index, principals):
    hits = index.search(principals["ops"], "التعويض المحكوم به منطوق الحكم", case_id="TM-2024-403")
    assert any("1,694,000" in b for h in hits for b in h.blocks)


def test_search_never_crosses_access_groups(index, principals):
    assert index.search(principals["ksa"], "damages awarded", case_id="TM-2024-428") == []
    assert {h.case_id for h in index.search(principals["ksa"], "trademark")} <= {"TM-2024-403", "TM-2024-438"}
    assert index.search(principals["procurement"], "settlement") == []


def test_tool_definitions_are_well_formed():
    assert [t["name"] for t in TOOLS] == ["search_case_documents", "read_case_document", "get_case", "query_case_data"]
    for t in TOOLS:
        assert t["input_schema"]["type"] == "object" and t["input_schema"]["required"]
    json.dumps(TOOLS)  # serialisable, so it can be sent (and cached) unchanged on every request


def test_search_tool_returns_citable_search_results(model, index, principals):
    out = ToolBox(principals["ops"], model, index).run("search_case_documents", {"query": "royalty", "case_id": "tm-2025-414"})
    assert not out.is_error and isinstance(out.content, list)
    for block in out.content:
        assert block["type"] == "search_result" and block["citations"] == {"enabled": True}
        assert block["content"] and all(b["type"] == "text" and b["text"] for b in block["content"])
    assert out.sources[0].file_name == "TM-2025-414_Licence_Agreement_EN.docx"
    assert out.content[0]["source"] == out.sources[0].source


def test_unavailable_and_missing_cases_look_the_same(model, index, principals):
    box = ToolBox(principals["ksa"], model, index)
    forbidden = box.run("get_case", {"case_id": "TM-2024-428"}).content
    missing = box.run("get_case", {"case_id": "TM-2099-999"}).content
    assert forbidden.replace("TM-2024-428", "X") == missing.replace("TM-2099-999", "X")
    assert box.run("read_case_document", {"file_name": "TM-2024-428_Judgment_EN.docx"}).content.startswith("No searchable document")


def test_procurement_gets_case_data_but_no_documents(model, index, principals):
    box = ToolBox(principals["procurement"], model, index)
    assert box.run("search_case_documents", {"query": "settlement"}).content == NO_DOCUMENT_ACCESS
    case = json.loads(box.run("get_case", {"case_id": "TM-2024-421"}).content)
    assert case["settlement_amount_aed"] == 49000 and isinstance(case["documents_on_file"], str)


def test_get_case_reports_which_documents_are_searchable(model, index, principals):
    case = json.loads(ToolBox(principals["ops"], model, index).run("get_case", {"case_id": "TM-2024-428"}).content)
    searchable = {d.get("file_name", d.get("title")): d["text_searchable"] for d in case["documents_on_file"]}
    assert searchable["TM-2024-428_Judgment_EN.docx"] is True
    assert list(searchable.values()).count(True) == 1  # the other catalogue entries have no file


def test_read_tool_returns_every_section(model, index, principals):
    out = ToolBox(principals["ops"], model, index).run("read_case_document", {"file_name": "TM-2024-421_Settlement_Agreement_EN.docx"})
    titles = [b["title"] for b in out.content]
    assert any("2. Settlement payment" in t for t in titles) and any("7. Liquidated damages" in t for t in titles)


def test_bad_input_and_sql_errors_are_tool_errors(model, index, principals):
    box = ToolBox(principals["ops"], model, index)
    assert box.run("get_case", {"case_id": "428"}).is_error
    assert box.run("search_case_documents", {}).is_error
    assert box.run("query_case_data", {"sql": "DROP TABLE fact_case"}).is_error
    assert box.run("no_such_tool", {}).is_error
    ok = box.run("query_case_data", {"sql": "SELECT COUNT(*) AS n FROM fact_case"})
    assert json.loads(ok.content)["rows"] == [[120]]
