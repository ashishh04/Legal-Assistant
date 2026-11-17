import clsx from "clsx";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowUp, BookOpenText, Check, Copy, Database, FileSearch, Lock, RotateCcw, ScanLine } from "lucide-react";
import { ApiError, api, streamMessage } from "../api";
import { Markdown, citeMark } from "../lib/markdown";
import { useSession } from "../session";
import type { Answer, ConversationInfo, ToolStep } from "../types";
import { Monogram } from "./Brand";

interface Msg {
  id: number;
  role: "user" | "assistant";
  text?: string;
  answer?: Answer;
  steps: ToolStep[];
  error?: string;
  pending?: boolean;
}

export function describeStep(s: ToolStep): string {
  const i = s.input ?? {};
  switch (s.name) {
    case "search_case_documents":
      return `Searched documents for “${String(i.query ?? "")}”${i.case_id ? ` in ${String(i.case_id)}` : ""}`;
    case "read_case_document":
      return `Read ${String(i.file_name ?? "a document")}`;
    case "get_case":
      return `Looked up case ${String(i.case_id ?? "")}`;
    case "query_case_data":
      return "Queried the case tracker";
    default:
      return s.name;
  }
}

const CASE_PROMPTS = [
  "Summarise this case and where it stands.",
  "What happens next, and by when?",
  "What do the documents on file say?",
  "لخّص هذه القضية وآخر مستجداتها",
];

export function Chat({ caseId = null, prompt = null, compact = false }: { caseId?: string | null; prompt?: string | null; compact?: boolean }) {
  const { user, meta } = useSession();
  const [conv, setConv] = useState<ConversationInfo | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState(prompt ?? "");
  const [busy, setBusy] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const threadRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const userId = user?.user_id;

  const start = useCallback(async () => {
    if (!userId) return;
    abortRef.current?.abort();
    setMessages([]);
    setConv(null);
    setStartError(null);
    try {
      setConv(await api.startConversation(caseId));
    } catch (e) {
      setStartError((e as Error).message);
    }
  }, [userId, caseId]);

  useEffect(() => { start(); return () => abortRef.current?.abort(); }, [start]);
  useEffect(() => { if (prompt) { setInput(prompt); inputRef.current?.focus(); } }, [prompt]);
  useEffect(() => {
    const el = threadRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages]);
  useEffect(() => {
    const el = inputRef.current;
    if (el) { el.style.height = "0px"; el.style.height = `${Math.min(160, el.scrollHeight)}px`; }
  }, [input]);

  async function send(raw: string) {
    const text = raw.trim();
    if (!text || busy || !conv) return;
    setBusy(true);
    setInput("");
    const id = Date.now();
    setMessages((m) => [...m, { id, role: "user", text, steps: [] }, { id: id + 1, role: "assistant", steps: [], pending: true }]);
    const update = (fn: (m: Msg) => Msg) => setMessages((ms) => ms.map((m) => (m.id === id + 1 ? fn(m) : m)));
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      for await (const ev of streamMessage(conv.conversation_id, text, ctrl.signal)) {
        if (ev.type === "tool") update((m) => ({ ...m, steps: [...m.steps, { name: ev.name, input: ev.input }] }));
        else if (ev.type === "answer") update((m) => ({ ...m, answer: ev, pending: false }));
        else if (ev.type === "error") update((m) => ({ ...m, error: ev.message, pending: false }));
      }
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        const expired = e instanceof ApiError && e.status === 404;
        update((m) => ({ ...m, error: expired ? "This conversation has expired. Start a new conversation and ask again." : "Ferrero couldn't be reached. Please check your connection and try again.", pending: false }));
      }
    } finally {
      update((m) => ({ ...m, pending: false }));
      setBusy(false);
      inputRef.current?.focus();
    }
  }

  const suggestions = conv?.case ? CASE_PROMPTS : (meta?.examples ?? []).slice(0, compact ? 4 : 6);
  const firstName = user?.full_name.split(" ")[0] ?? "";

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div ref={threadRef} className={clsx("min-h-0 flex-1 overflow-y-auto", compact ? "px-5 py-5" : "px-6 py-6 lg:px-10")}>
        {messages.length === 0 ? (
          <div className="mx-auto flex max-w-2xl flex-col items-center pt-6 text-center animate-fade-up">
            <Monogram size={44} />
            <h2 className="mt-4 text-[20px] font-semibold tracking-[-0.02em] text-ink">
              {conv?.case ? `Ask about ${conv.case.case_id}` : `How can I help, ${firstName}?`}
            </h2>
            <p className="mt-2 max-w-md text-[13.5px] leading-relaxed text-ink-2">
              {conv?.case
                ? <>Questions about <span className="font-medium text-ink">{conv.case.title}</span> are answered from its documents and the case tracker.</>
                : <>Ask about cases, documents or the whole portfolio, in English or Arabic. Answers cite the passages they come from.</>}
            </p>
            {conv?.case_requested && !conv.case && (
              <p className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-surface-2 px-3 py-1 text-[12.5px] text-ink-2">
                <Lock size={13} /> {conv.case_requested} is not available to {user?.full_name}.
              </p>
            )}
            {startError && <p className="mt-3 text-[13px] text-critical">Ferrero couldn't start a conversation. Please try again in a moment.</p>}
            <div className={clsx("mt-6 grid w-full gap-2", compact ? "grid-cols-1" : "sm:grid-cols-2")}>
              {suggestions.map((q) => (
                <button key={q} type="button" dir="auto" onClick={() => send(q)} disabled={!conv || busy}
                  className="rounded-xl border border-line bg-surface px-3.5 py-2.5 text-start text-[13.5px] text-ink-2 transition hover:border-accent hover:bg-accent-soft hover:text-ink disabled:opacity-50">
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="mx-auto flex max-w-3xl flex-col gap-6">
            {messages.map((m) => m.role === "user"
              ? <UserBubble key={m.id} text={m.text ?? ""} />
              : <AssistantMessage key={m.id} msg={m} />)}
          </div>
        )}
      </div>

      <div className={clsx("border-t border-line bg-surface/80 backdrop-blur", compact ? "px-4 pb-4 pt-3" : "px-6 pb-5 pt-4 lg:px-10")}>
        <form className="mx-auto max-w-3xl" onSubmit={(e) => { e.preventDefault(); send(input); }}>
          <div className="flex items-end gap-2 rounded-2xl border border-line-strong bg-surface p-2 shadow-card focus-within:border-accent">
            <textarea ref={inputRef} dir="auto" rows={1} maxLength={4000} value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(input); } }}
              placeholder={conv?.case ? `Ask about ${conv.case.case_id}…` : "Ask Ferrero about a case, a document or the portfolio…"}
              className="max-h-40 min-h-[40px] flex-1 resize-none bg-transparent px-2 py-2 text-[14.5px] text-ink outline-none placeholder:text-muted" />
            <button type="submit" disabled={!input.trim() || busy || !conv} aria-label="Send"
              className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary text-primary-ink transition hover:opacity-90 disabled:opacity-30">
              <ArrowUp size={18} strokeWidth={2.2} />
            </button>
          </div>
          <div className="mt-2 flex items-center justify-between gap-3 px-1 text-[11.5px] text-muted">
            <span>Answers use only the files and case data available to {user?.full_name ?? "you"}.</span>
            {messages.length > 0 && (
              <button type="button" onClick={start} className="inline-flex items-center gap-1 hover:text-ink">
                <RotateCcw size={12} /> New conversation
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}

function UserBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end animate-fade-up">
      <div dir="auto" className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-ee-md bg-primary px-4 py-2.5 text-[14.5px] leading-relaxed text-primary-ink">
        {text}
      </div>
    </div>
  );
}

function AssistantMessage({ msg }: { msg: Msg }) {
  const [copied, setCopied] = useState(false);
  const [flash, setFlash] = useState<number | null>(null);
  const a = msg.answer;
  const jump = (n: number) => {
    document.getElementById(`src-${msg.id}-${n}`)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    setFlash(n);
    window.setTimeout(() => setFlash(null), 1400);
  };
  const marked = a ? (a.segments.length ? a.segments.map((s) => s.text + s.citations.map(citeMark).join("")).join("") : a.text) : "";

  return (
    <div className="flex gap-3 animate-fade-up">
      <Monogram size={30} className="mt-0.5 shrink-0" />
      <div className="min-w-0 flex-1">
        {msg.pending && (
          <div className="rounded-2xl rounded-ss-md border border-line bg-surface px-4 py-3">
            {msg.steps.length > 0 && (
              <ol className="mb-2 space-y-1">
                {msg.steps.map((s, i) => (
                  <li key={i} className="flex items-center gap-2 text-[13px] text-ink-2">
                    <Check size={14} className="text-good" /> {describeStep(s)}
                  </li>
                ))}
              </ol>
            )}
            <div className="flex items-center gap-2 text-[13px] text-muted">
              <span className="flex gap-1">
                {[0, 1, 2].map((i) => <span key={i} className="thinking-dot size-1.5 rounded-full bg-accent" style={{ animationDelay: `${i * 0.15}s` }} />)}
              </span>
              Ferrero is checking the case files
            </div>
          </div>
        )}
        {msg.error && (
          <div className="rounded-2xl rounded-ss-md border border-line bg-surface px-4 py-3 text-[13.5px] text-critical">{msg.error}</div>
        )}
        {a && (
          <div className="rounded-2xl rounded-ss-md border border-line bg-surface px-5 py-4 shadow-card">
            <div className="mb-2.5 flex flex-wrap items-center gap-1.5">
              {a.route.includes("documents") && <RouteBadge icon={FileSearch} label="Case documents" />}
              {a.route.includes("case_data") && <RouteBadge icon={Database} label="Case tracker" />}
            </div>
            <Markdown text={marked} renderCite={(n) => (
              <button type="button" onClick={() => jump(n)} aria-label={`Source ${n}`}
                className="mx-0.5 inline-grid h-[18px] min-w-[18px] -translate-y-px place-items-center rounded-md bg-accent-soft px-1 align-middle text-[10.5px] font-semibold text-accent-ink hover:bg-accent hover:text-[#141519]">
                {n}
              </button>
            )} />
            {a.citations.length > 0 && (
              <div className="mt-4 border-t border-line pt-3">
                <div className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">
                  <BookOpenText size={13} /> Sources
                </div>
                <ol className="space-y-2">
                  {a.citations.map((c) => (
                    <li key={c.n} id={`src-${msg.id}-${c.n}`}
                      className={clsx("rounded-xl border px-3 py-2.5 transition-colors", flash === c.n ? "border-accent bg-accent-soft" : "border-line bg-surface-2")}>
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[12.5px]">
                        <span className="grid size-[18px] place-items-center rounded-md bg-surface text-[10.5px] font-semibold text-accent-ink">{c.n}</span>
                        {c.doc_id
                          ? <Link to={`/documents/${encodeURIComponent(c.doc_id)}`} dir="auto" className="font-medium text-ink hover:text-accent-ink hover:underline" title="Open the document">{c.file_name ?? c.title}</Link>
                          : <span className="font-medium text-ink" dir="auto">{c.file_name ?? c.title}</span>}
                        {c.section && <span className="text-muted" dir="auto">· {c.section}</span>}
                        {c.doc_type && <span className="rounded-full border border-line px-2 py-px text-[11px] text-ink-2">{c.doc_type}</span>}
                        {c.scanned && (
                          <span className="inline-flex items-center gap-1 rounded-full border border-line px-2 py-px text-[11px] text-ink-2" title="Text recognised from a scanned copy">
                            <ScanLine size={11} aria-hidden /> Scanned copy
                          </span>
                        )}
                      </div>
                      <blockquote dir="auto" className="mt-1.5 border-s-2 border-accent ps-2.5 text-[13px] leading-relaxed text-ink-2">{c.cited_text}</blockquote>
                      {c.library_path && <div className="mt-1 truncate text-[11px] text-muted" title={c.library_path}>{c.library_path}</div>}
                    </li>
                  ))}
                </ol>
              </div>
            )}
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-line pt-2.5 text-[12px] text-muted">
              {a.tools.length > 0 ? (
                <details className="group">
                  <summary className="cursor-pointer list-none hover:text-ink">
                    How Ferrero answered · {a.tools.length} step{a.tools.length > 1 ? "s" : ""} · {a.latency_s}s
                  </summary>
                  <ol className="mt-2 space-y-1 ps-1">
                    {a.tools.map((t, i) => (
                      <li key={i} className={clsx("text-[12.5px]", t.is_error ? "text-critical" : "text-ink-2")}>
                        {i + 1}. {describeStep(t)}{t.summary ? ` – ${t.summary}` : ""}
                      </li>
                    ))}
                  </ol>
                </details>
              ) : <span>{a.latency_s}s</span>}
              <button type="button" className="inline-flex items-center gap-1 hover:text-ink"
                onClick={() => { navigator.clipboard?.writeText(a.text).then(() => { setCopied(true); window.setTimeout(() => setCopied(false), 1500); }); }}>
                {copied ? <Check size={13} /> : <Copy size={13} />} {copied ? "Copied" : "Copy"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function RouteBadge({ icon: Icon, label }: { icon: typeof FileSearch; label: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-accent-soft px-2 py-0.5 text-[11.5px] font-medium text-accent-ink">
      <Icon size={12} /> {label}
    </span>
  );
}
