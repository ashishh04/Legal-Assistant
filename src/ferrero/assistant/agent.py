"""The Ferrero assistant: Claude in a tool-use loop, with server-side, append-only conversations.

A manual loop rather than the SDK's tool runner, because each turn needs to: return document passages as
``search_result`` blocks (native citations), run every tool with the conversation's principal, emit a
progress event per tool call for the UI, and force a final answer on the last round (``tool_choice: none``).

Conversations live on the server and are only ever appended to - the request history is never rebuilt,
trimmed or edited - which keeps Claude's thinking blocks valid across turns and the prompt cache warm.
"""
from __future__ import annotations

import os
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Iterator

import anthropic

from ..casemodel import CaseModel
from ..config import Settings
from ..security import Principal
from ..sync.index import DocumentIndex
from .prompts import context_message, system_prompt
from .tools import CASE_DATA_TOOLS, DOCUMENT_TOOLS, TOOLS, SourceRef, ToolBox

MAX_TOKENS = 16000
FALLBACK_BETA = "server-side-fallback-2026-07-01"


TRY_AGAIN = "Ferrero couldn't answer just now. Please try again in a moment."
UNAVAILABLE = "Ferrero isn't available right now. Please contact your administrator."
BUSY = "Ferrero is handling a lot of requests. Please try again in a minute."


class AssistantError(RuntimeError):
    """A failure with a technical detail (``str(e)``, for logs and operators) and a plain-language ``public`` message."""

    def __init__(self, detail: str, public: str = TRY_AGAIN):
        super().__init__(detail)
        self.public = public


def make_client(settings: Settings) -> Any:
    # Server-side `fallbacks` exist only on the first-party API; elsewhere the SDK middleware retries refusals.
    middleware = ([anthropic.BetaRefusalFallbackMiddleware([{"model": settings.fallback_model}])]
                  if settings.fallback_model else None)
    if settings.provider == "foundry":
        kwargs: dict[str, Any] = {"middleware": middleware}
        if settings.foundry_resource:
            kwargs["resource"] = settings.foundry_resource  # else ANTHROPIC_FOUNDRY_RESOURCE / _BASE_URL
        return anthropic.AnthropicFoundry(**kwargs)
    if settings.provider == "bedrock":
        env = os.environ.get
        if not settings.aws_region:
            raise AssistantError("Set AWS_REGION (for example us-east-1) to use Claude on Amazon Bedrock.", UNAVAILABLE)
        creds = {"aws_access_key": env("AWS_ACCESS_KEY_ID"), "aws_secret_key": env("AWS_SECRET_ACCESS_KEY"),
                 "aws_session_token": env("AWS_SESSION_TOKEN"), "aws_profile": env("AWS_PROFILE"),
                 "api_key": env("AWS_BEARER_TOKEN_BEDROCK")}
        return anthropic.AnthropicBedrockMantle(aws_region=settings.aws_region, middleware=middleware,
                                                **{k: v for k, v in creds.items() if v})
    return anthropic.Anthropic()  # ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN or an `ant auth login` profile


@dataclass
class Usage:
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0

    def add(self, usage: Any) -> None:
        self.requests += 1
        for name in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
            setattr(self, name, getattr(self, name) + (getattr(usage, name, 0) or 0))

    def as_dict(self) -> dict[str, int]:
        return dict(self.__dict__)


@dataclass
class Conversation:
    id: str
    principal: Principal
    case_focus: dict[str, Any] | None = None
    messages: list[Any] = field(default_factory=list)
    sources: dict[str, SourceRef] = field(default_factory=dict)  # search_result source -> passage, for citations
    context_sent: bool = False
    turns: int = 0
    fallback_state: Any = None
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    touched: float = field(default_factory=time.monotonic)


class ConversationStore:
    """In-memory, least-recently-used store. A restart forgets conversations; the UI then starts a new one."""

    def __init__(self, max_size: int = 500, ttl_seconds: float = 8 * 3600):
        self._items: OrderedDict[str, Conversation] = OrderedDict()
        self._lock = threading.Lock()
        self.max_size, self.ttl = max_size, ttl_seconds

    def add(self, conv: Conversation) -> None:
        with self._lock:
            self._items[conv.id] = conv
            self._evict()

    def get(self, conv_id: str) -> Conversation | None:
        with self._lock:
            conv = self._items.get(conv_id)
            if conv is None or time.monotonic() - conv.touched > self.ttl:
                self._items.pop(conv_id, None)
                return None
            conv.touched = time.monotonic()
            self._items.move_to_end(conv_id)
            return conv

    def _evict(self) -> None:
        while len(self._items) > self.max_size:
            self._items.popitem(last=False)


class Assistant:
    def __init__(self, settings: Settings, model: CaseModel, index: DocumentIndex, client: Any = None):
        self.settings, self.model, self.index = settings, model, index
        self.system = system_prompt(settings, model)
        self._client = client
        self.conversations = ConversationStore()

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = make_client(self.settings)
        return self._client

    def start(self, user_id: str, case_id: str | None = None) -> Conversation:
        principal = self.model.principal(user_id)
        if principal is None:
            raise AssistantError(f"Unknown user {user_id}.", "Your user profile couldn't be found.")
        case = self.model.visible_case(principal, case_id.upper()) if case_id else None
        client_side_fallback = self.settings.provider != "anthropic" and self.settings.fallback_model
        conv = Conversation(uuid.uuid4().hex, principal, case_focus=case,
                            fallback_state=anthropic.BetaFallbackState() if client_side_fallback else None)
        self.conversations.add(conv)
        return conv

    def ask(self, conv: Conversation, text: str) -> Iterator[dict[str, Any]]:
        """Run one user turn. Yields ``{"type": "tool", ...}`` progress events, then one ``{"type": "answer", ...}``."""
        with conv.lock:
            yield from self._turn(conv, text)

    # ---------- internals ----------
    def _turn(self, conv: Conversation, text: str) -> Iterator[dict[str, Any]]:
        started = time.monotonic()
        checkpoint, context_was_sent = len(conv.messages), conv.context_sent
        trace: list[dict[str, Any]] = []
        usage = Usage()
        try:
            if conv.context_sent:
                conv.messages.append({"role": "user", "content": text})
            elif self.settings.mid_conversation_system:
                conv.messages.append({"role": "user", "content": text})
                conv.messages.append({"role": "system", "content": context_message(conv.principal, conv.case_focus)})
            else:  # models without mid-conversation system messages: the context leads the first user message
                conv.messages.append({"role": "user", "content": [
                    {"type": "text", "text": "[Context from the Ferrero application, not written by the user] "
                                             + context_message(conv.principal, conv.case_focus)},
                    {"type": "text", "text": text},
                ]})
            conv.context_sent = True
            toolbox = ToolBox(conv.principal, self.model, self.index)
            rounds = self.settings.max_tool_rounds
            response = None
            for round_no in range(rounds + 1):
                final_round = round_no == rounds
                response = self._create(conv, force_answer=final_round)
                usage.add(response.usage)
                conv.messages.append({"role": "assistant", "content": response.content})
                tool_uses = [b for b in response.content if getattr(b, "type", None) == "tool_use"]
                if response.stop_reason == "tool_use" and tool_uses and not final_round:
                    results = []
                    for block in tool_uses:
                        yield {"type": "tool", "name": block.name, "input": block.input}
                        outcome = toolbox.run(block.name, block.input)
                        for ref in outcome.sources:
                            conv.sources[ref.source] = ref
                        trace.append({"name": block.name, "input": block.input, "summary": outcome.summary,
                                      "is_error": outcome.is_error})
                        results.append(outcome.as_tool_result(block.id))
                    conv.messages.append({"role": "user", "content": results})  # all results of a round in one message
                    continue
                if tool_uses:  # calls that will not run (output cut short): answer them so the history stays valid
                    conv.messages.append({"role": "user", "content": [
                        {"type": "tool_result", "tool_use_id": b.id, "is_error": True,
                         "content": "Not run: the response ended before this call could be processed."} for b in tool_uses]})
                if response.stop_reason == "pause_turn" and not final_round:
                    continue
                break
        except BaseException:
            # The turn failed (API error, or the client went away): drop everything it appended. Removing a trailing
            # run of messages leaves the earlier prefix - and every earlier thinking block - unchanged.
            del conv.messages[checkpoint:]
            conv.context_sent = context_was_sent
            raise
        conv.turns += 1
        yield {"type": "answer", **build_answer(response, conv.sources, trace, usage, time.monotonic() - started)}

    def _create(self, conv: Conversation, force_answer: bool) -> Any:
        params: dict[str, Any] = {
            "model": self.settings.model,
            "max_tokens": MAX_TOKENS,
            "system": self.system,
            "tools": TOOLS,
            "messages": conv.messages,
            "output_config": {"effort": self.settings.effort},
            "cache_control": {"type": "ephemeral"},  # caches the whole prefix up to the latest block, every round
        }
        if force_answer:
            params["tool_choice"] = {"type": "none"}
        try:
            if self.settings.provider == "anthropic":
                return self.client.beta.messages.create(betas=[FALLBACK_BETA], fallbacks="default", **params)
            if conv.fallback_state is not None:
                with conv.fallback_state:  # pins a fallback model to this conversation once one is used
                    return self.client.beta.messages.create(**params)
            return self.client.beta.messages.create(**params)
        except TypeError as e:
            if "authentication" in str(e).lower() or "credential" in str(e).lower():
                raise AssistantError("No Claude credentials found. Set ANTHROPIC_API_KEY, or configure Amazon Bedrock or "
                                     "Microsoft Foundry (see .env.example), and restart.", UNAVAILABLE) from None
            raise
        except anthropic.AuthenticationError as e:
            raise AssistantError(f"The {self.settings.provider} credentials were rejected (401): {e.message}", UNAVAILABLE) from None
        except anthropic.PermissionDeniedError as e:
            raise AssistantError(f"The credentials cannot use model {self.settings.model} (403): {e.message}", UNAVAILABLE) from None
        except anthropic.NotFoundError as e:
            raise AssistantError(f"Model {self.settings.model} was not found on {self.settings.provider} (404): "
                                 f"{e.message}", UNAVAILABLE) from None
        except anthropic.RateLimitError:
            raise AssistantError("Claude is rate-limiting requests right now.", BUSY) from None
        except anthropic.APIStatusError as e:
            raise AssistantError(f"Claude API error {e.status_code}: {e.message}") from None
        except anthropic.APIConnectionError:
            raise AssistantError("Could not reach the Claude API (network error).") from None


def build_answer(response: Any, sources: dict[str, SourceRef], trace: list[dict[str, Any]], usage: Usage,
                 latency: float) -> dict[str, Any]:
    """Turn Claude's final message into answer text, citation-tagged segments and a numbered source list."""
    segments: list[dict[str, Any]] = []
    citations: list[dict[str, Any]] = []
    numbers: dict[tuple, int] = {}
    for block in response.content:
        if getattr(block, "type", None) != "text":
            continue
        marks = []
        for c in getattr(block, "citations", None) or []:
            if getattr(c, "type", None) != "search_result_location":
                continue
            key = (c.source, c.start_block_index, c.end_block_index)
            if key not in numbers:
                numbers[key] = len(citations) + 1
                ref = sources.get(c.source)
                citations.append({"n": numbers[key], "source": c.source, "title": c.title, "cited_text": c.cited_text,
                                  **(ref.to_dict() if ref else {})})
            marks.append(numbers[key])
        segments.append({"text": block.text, "citations": sorted(set(marks))})
    text = "".join(s["text"] for s in segments).strip()
    stop = response.stop_reason
    if stop == "refusal" and not text:
        text = "I can't help with that request."
        segments = [{"text": text, "citations": []}]
    elif stop == "max_tokens":
        segments.append({"text": "\n\n[The answer was cut off at the length limit.]", "citations": []})
    used = {t["name"] for t in trace}
    route = [name for name, tools in (("documents", DOCUMENT_TOOLS), ("case_data", CASE_DATA_TOOLS)) if used & tools]
    return {
        "text": text, "segments": segments, "citations": citations, "tools": trace, "route": route,
        "stop_reason": stop, "model": getattr(response, "model", None), "usage": usage.as_dict(),
        "latency_s": round(latency, 2),
    }
