from dataclasses import replace

from ferrero.assistant.agent import Assistant
from ferrero.config import base_model_id, bedrock_model_id, detect_provider

from conftest import message, text, thinking


def test_provider_detection():
    env = lambda values: values.get  # noqa: E731
    assert detect_provider(env({"BEDROCK_MODEL_ID": "anthropic.claude-sonnet-5", "AWS_REGION": "us-east-1"})) == "bedrock"
    assert detect_provider(env({"ANTHROPIC_API_KEY": "k", "BEDROCK_MODEL_ID": "x"})) == "anthropic"
    assert detect_provider(env({"FERRERO_LLM_PROVIDER": "Foundry"})) == "foundry"
    assert detect_provider(env({})) == "anthropic"


def test_model_ids():
    assert bedrock_model_id("claude-sonnet-5") == "anthropic.claude-sonnet-5"
    assert bedrock_model_id("us.anthropic.claude-opus-5-5") == "us.anthropic.claude-opus-5-5"
    assert base_model_id("anthropic.claude-sonnet-5") == "claude-sonnet-5"
    assert base_model_id("arn:aws:bedrock:us-east-1:123:inference-profile/global.anthropic.claude-opus-5-5") == "claude-opus-5-5"


def test_where_the_user_context_goes(settings):
    assert settings.mid_conversation_system  # claude-opus-5-5 on the first-party API
    assert not replace(settings, provider="bedrock", model="anthropic.claude-sonnet-5").mid_conversation_system
    assert replace(settings, provider="bedrock", model="anthropic.claude-opus-5-5").mid_conversation_system
    assert not replace(settings, provider="foundry").mid_conversation_system


def test_context_leads_the_first_message_when_system_messages_are_unsupported(fake_claude, settings, model, index):
    fake_claude.responses = [message([thinking(), text("First.")]), message([thinking("sig-2"), text("Second.")])]
    sonnet5 = replace(settings, model="claude-sonnet-5")
    assistant = Assistant(sonnet5, model, index, client=fake_claude.client())
    conv = assistant.start("U-05")
    list(assistant.ask(conv, "How many open cases?"))
    list(assistant.ask(conv, "And closed?"))
    first, second = (r["body"]["messages"] for r in fake_claude.requests)
    assert all(m["role"] != "system" for m in second)
    context, question = first[0]["content"]
    assert "Omar Al Qahtani" in context["text"] and "not written by the user" in context["text"]
    assert question == {"type": "text", "text": "How many open cases?"}
    assert second[:2] == first[:1] + [second[1]] and second[2] == {"role": "user", "content": "And closed?"}
