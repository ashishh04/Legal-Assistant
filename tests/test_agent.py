from dataclasses import replace

import pytest

from ferrero.assistant.agent import Assistant, AssistantError

from conftest import message, text, thinking, tool_use

QUESTION = "What damages were awarded in TM-2024-428?"


def cite_awarded_amount(body):
    """Answer the way Claude would: cite the operative-part item of the returned search results that orders payment."""
    results = body["messages"][-1]["content"][0]["content"]
    for i, result in enumerate(results):
        for j, block in enumerate(result["content"]):
            if "pay the Claimant AED 2,288,000" in block["text"]:
                citation = {"type": "search_result_location", "source": result["source"], "title": result["title"],
                            "cited_text": block["text"], "search_result_index": i,
                            "start_block_index": j, "end_block_index": j + 1}
                return message([thinking("sig-2"), text("The court awarded AED 2,288,000", [citation]),
                                text(" in compensation for material and moral damage.")])
    raise AssertionError("award passage not returned by the search tool")


def test_document_question_end_to_end(fake_claude, settings, model, index):
    fake_claude.responses = [
        message([thinking(), tool_use("search_case_documents", {"query": "damages awarded", "case_id": "TM-2024-428"})],
                stop_reason="tool_use"),
        cite_awarded_amount,
    ]
    assistant = Assistant(settings, model, index, client=fake_claude.client())
    events = list(assistant.ask(assistant.start("U-08"), QUESTION))

    assert [e["type"] for e in events] == ["tool", "answer"]
    answer = events[-1]
    assert answer["text"].startswith("The court awarded AED 2,288,000")
    assert answer["route"] == ["documents"]
    assert answer["segments"][0]["citations"] == [1] and answer["segments"][1]["citations"] == []
    cited = answer["citations"][0]
    assert (cited["file_name"], cited["section"]) == ("TM-2024-428_Judgment_EN.docx", "Operative part")
    assert cited["library_path"] == "/sites/Legal/Cases/UAE/TM-2024-428/TM-2024-428_Judgment_EN.docx"
    assert answer["usage"]["requests"] == 2

    first = fake_claude.requests[0]
    body = first["body"]
    assert first["path"].startswith("/v1/messages")
    assert "server-side-fallback-2026-07-01" in first["headers"]["anthropic-beta"]
    assert body["model"] == "claude-opus-5-5" and body["fallbacks"] == "default"
    assert body["output_config"] == {"effort": "medium"} and body["cache_control"] == {"type": "ephemeral"}
    assert not {"temperature", "top_p", "top_k", "thinking", "tool_choice"} & body.keys()
    assert [t["name"] for t in body["tools"]] == ["search_case_documents", "read_case_document", "get_case", "query_case_data"]
    assert body["messages"][0] == {"role": "user", "content": QUESTION}
    assert body["messages"][1]["role"] == "system" and "Priya Menon" in body["messages"][1]["content"]

    second = fake_claude.requests[1]["body"]
    assert second["system"] == body["system"] and second["tools"] == body["tools"]
    assert second["messages"][:2] == body["messages"]          # history only ever grows
    replayed = second["messages"][2]["content"][0]
    assert replayed["type"] == "thinking" and replayed["signature"] == "sig-abc"  # thinking replayed unchanged
    tool_result = second["messages"][3]["content"][0]
    assert tool_result["type"] == "tool_result" and tool_result["content"][0]["type"] == "search_result"


def test_follow_up_turns_append_to_the_same_history(fake_claude, settings, model, index):
    fake_claude.responses = [message([thinking(), text("Hello.")]), message([thinking("sig-3"), text("Again.")])]
    assistant = Assistant(settings, model, index, client=fake_claude.client())
    conv = assistant.start("U-04", case_id="TM-2024-428")
    list(assistant.ask(conv, "First question"))
    list(assistant.ask(conv, "Second question"))
    first, second = (r["body"]["messages"] for r in fake_claude.requests)
    assert second[: len(first)] == first[:2] and len(second) == 4
    assert sum(m["role"] == "system" for m in second) == 1      # the context message is sent once
    assert "TM-2024-428" in first[1]["content"] and "Sara Haddad" in first[1]["content"]


def test_a_failed_turn_leaves_the_conversation_clean(fake_claude, settings, model, index):
    fake_claude.responses = [("status", 500), message([thinking(), text("Recovered.")])]
    assistant = Assistant(settings, model, index, client=fake_claude.client())
    conv = assistant.start("U-08")
    with pytest.raises(AssistantError, match="500"):
        list(assistant.ask(conv, "Question"))
    assert conv.messages == [] and not conv.context_sent
    answer = list(assistant.ask(conv, "Question"))[-1]
    assert answer["text"] == "Recovered."
    assert [m["role"] for m in fake_claude.requests[1]["body"]["messages"]] == ["user", "system"]


def test_the_last_round_must_answer(fake_claude, settings, model, index):
    fake_claude.responses = [
        message([thinking(), tool_use("get_case", {"case_id": "TM-2026-421"})], stop_reason="tool_use"),
        message([thinking(), text("Prepare hearing bundle, due 27 December 2026.")]),
    ]
    assistant = Assistant(replace(settings, max_tool_rounds=1), model, index, client=fake_claude.client())
    answer = list(assistant.ask(assistant.start("U-08"), "What is the next action on TM-2026-421?"))[-1]
    assert fake_claude.requests[1]["body"]["tool_choice"] == {"type": "none"}
    assert answer["route"] == ["case_data"] and "27 December 2026" in answer["text"]


def test_tools_run_as_the_conversation_user(fake_claude, settings, model, index):
    fake_claude.responses = [
        message([thinking(), tool_use("get_case", {"case_id": "TM-2024-428"})], stop_reason="tool_use"),
        lambda body: message([text(body["messages"][-1]["content"][0]["content"])]),  # echo the tool result
    ]
    assistant = Assistant(settings, model, index, client=fake_claude.client())
    answer = list(assistant.ask(assistant.start("U-05"), "Tell me about TM-2024-428"))[-1]
    assert answer["text"] == "No case TM-2024-428 is available to the signed-in user."


def test_refusals_and_missing_credentials(fake_claude, settings, model, index):
    fake_claude.responses = [message([], stop_reason="refusal")]
    assistant = Assistant(settings, model, index, client=fake_claude.client())
    assert list(assistant.ask(assistant.start("U-08"), "…"))[-1]["text"] == "I can't help with that request."

    class NoCredentials:
        class beta:  # noqa: N801
            class messages:  # noqa: N801
                @staticmethod
                def create(**_):
                    raise TypeError('"Could not resolve authentication method. Expected one of api_key, auth_token"')

    assistant = Assistant(settings, model, index, client=NoCredentials())
    with pytest.raises(AssistantError, match="ANTHROPIC_API_KEY"):
        list(assistant.ask(assistant.start("U-08"), "Hi"))
