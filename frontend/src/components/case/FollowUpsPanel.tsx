import clsx from "clsx";
import { useEffect, useMemo, useState } from "react";
import { Ban, BellRing, CalendarClock, CalendarPlus, Check, CircleCheck, Gavel, Pencil, Plus, TriangleAlert } from "lucide-react";
import { ApiError, api, recordsChanged } from "../../api";
import { addDays, daysFrom, fmtDate, fmtDateTime, relativeDays } from "../../lib/format";
import { useApi } from "../../lib/hooks";
import { deadlineState } from "../../lib/labels";
import { useToast } from "../../lib/toast";
import { useSession } from "../../session";
import type { CaseDetail, Decision, FollowUp } from "../../types";
import { Dialog } from "../Dialog";
import { Field, FormError, SelectInput, TextArea, TextInput } from "../forms";
import { Button, Card, Chip, EmptyState, SectionTitle, StatusPill } from "../ui";
import { GateNotice, useOwners } from "./shared";

export function DuePill({ days, lead = 7 }: { days: number; lead?: number }) {
  const state = deadlineState(days, lead);
  if (state === "overdue") return <StatusPill kind="critical">{relativeDays(days)}</StatusPill>;
  if (state === "today") return <StatusPill kind="warning">Due today</StatusPill>;
  if (state === "soon") return <StatusPill kind="pending">Due {relativeDays(days)}</StatusPill>;
  return <span className="whitespace-nowrap text-[12.5px] text-muted">Due {relativeDays(days)}</span>;
}

export function DateBlock({ iso, state }: { iso: string; state: ReturnType<typeof deadlineState> | "done" }) {
  const d = new Date(`${iso}T00:00:00`);
  // a calendar leaf: the month on a band in the deadline's tone, the day beneath
  return (
    <span className={clsx("w-12 shrink-0 self-start overflow-hidden rounded-lg border bg-surface text-center shadow-card",
      state === "overdue" ? "border-critical-line" : state === "today" ? "border-warning-line" : state === "soon" ? "border-accent-line" : "border-line")}>
      <span className={clsx("block py-[3px] text-[10px] font-semibold uppercase leading-4 tracking-[0.1em]",
        state === "overdue" ? "bg-critical-soft text-critical-ink" : state === "today" ? "bg-warning-soft text-warning-ink"
          : state === "soon" ? "bg-accent-soft text-accent-ink" : "bg-surface-3 text-muted")}>
        {d.toLocaleDateString("en-GB", { month: "short" })}
      </span>
      <span className={clsx("tabular block py-1.5 text-[17px] font-semibold leading-none", state === "done" ? "text-muted" : "text-ink")}>{d.getDate()}</span>
    </span>
  );
}

/** `startNew`: open the new follow-up form straight away (the case's workflow bar asks for it). */
export function FollowUpsPanel({ c, onChanged, startNew = false, onStarted }:
  { c: CaseDetail; onChanged: () => void; startNew?: boolean; onStarted?: () => void }) {
  const { user, meta } = useSession();
  const o = meta!.case_options;
  const today = meta!.demo_today;
  const { data, error, reload } = useApi<FollowUp[] | null>(
    () => (user ? api.followUps(c.case_id) : Promise.resolve(null)), [user?.user_id, c.case_id, c.counts.audit, today]);
  const [creating, setCreating] = useState(false);
  const [resolving, setResolving] = useState<FollowUp | null>(null);
  const [editing, setEditing] = useState<FollowUp | null>(null);
  const canEdit = c.permissions.edit;
  useEffect(() => {
    if (startNew && canEdit) setCreating(true);
    if (startNew) onStarted?.();
  }, [startNew, canEdit, onStarted]);
  const open = (data ?? []).filter((f) => f.status === "Open");
  const done = (data ?? []).filter((f) => f.status !== "Open");
  const changed = () => { reload(); onChanged(); recordsChanged(); };
  const due = daysFrom(today, c.next_action_due);
  const hearing = daysFrom(today, c.next_hearing_date);

  return (
    <div className="grid items-start gap-5 lg:grid-cols-3">
      <div className="flex min-w-0 flex-col gap-5 lg:col-span-2">
        <Card className="p-6">
          <SectionTitle aside={canEdit && <Button variant="primary" icon={Plus} onClick={() => setCreating(true)}>Add follow-up</Button>}>
            Follow-ups and deadlines
          </SectionTitle>
          {error && <p className="text-[13px] text-critical-ink">The follow-ups couldn't be loaded. Please try again.</p>}
          {!data && !error && <p className="py-8 text-center text-[13px] text-muted">Loading follow-ups…</p>}
          {data && !open.length && (
            <EmptyState plain icon={CalendarClock} title="No open follow-ups"
              action={canEdit ? <Button icon={Plus} onClick={() => setCreating(true)}>Add a follow-up</Button> : undefined}>
              Set a deadline when the other side is given time to act, for example a store given 30 days to remove the
              infringing products. The owner is told when it is reached, to follow up and decide.
            </EmptyState>
          )}
          <ul className="flex flex-col gap-3">
            {open.map((f) => {
              const state = deadlineState(f.days_left, f.remind_days || o.reminder_lead_days);
              const decide = state === "overdue" || state === "today";
              return (
                <li key={f.follow_up_id} className={clsx("flex gap-4 rounded-xl border p-4",
                  decide ? "border-warning-line bg-warning-soft/60" : "border-line bg-surface")}>
                  <DateBlock iso={f.due_date} state={state} />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[14.5px] font-semibold text-ink" dir="auto">{f.title}</span>
                      <DuePill days={f.days_left} lead={f.remind_days || o.reminder_lead_days} />
                    </div>
                    <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] text-ink-2">
                      <Chip>{f.kind}</Chip>
                      <span>{f.period_days != null ? `${f.period_days} days from ${fmtDate(f.start_date)}` : `From ${fmtDate(f.start_date)}`}</span>
                      <span className="text-muted">·</span>
                      <span>Owner <span className="font-medium text-ink">{f.owner_name}</span></span>
                    </div>
                    {f.details && <p className="mt-2.5 whitespace-pre-line text-[13.5px] leading-relaxed text-ink-2" dir="auto">{f.details}</p>}
                    <div className="mt-2 text-[12px] text-muted">
                      {f.follow_up_id} · set by {f.created_by}, {fmtDateTime(f.created_at)}
                      {f.remind_days ? ` · reminder ${f.remind_days} day${f.remind_days === 1 ? "" : "s"} before` : " · reminder on the day"}
                    </div>
                    {canEdit && (
                      <div className="mt-3.5 flex flex-wrap gap-2">
                        <Button variant={decide ? "primary" : "secondary"} icon={CircleCheck} onClick={() => setResolving(f)}>Record decision</Button>
                        <Button variant="ghost" icon={Pencil} onClick={() => setEditing(f)}>Change or extend</Button>
                      </div>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        </Card>
        {done.length > 0 && (
          <Card className="p-6">
            <SectionTitle aside={<span className="tabular text-[12.5px] text-muted">{done.length}</span>}>Resolved</SectionTitle>
            <ul className="divide-y divide-line">
              {done.map((f) => (
                <li key={f.follow_up_id} className="flex gap-4 py-3">
                  <DateBlock iso={f.due_date} state="done" />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[13.5px] font-medium text-ink" dir="auto">{f.title}</span>
                      <StatusPill kind={f.status === "Cancelled" ? "neutral" : f.decision === "escalate" ? "warning" : "good"}>{f.decision_label ?? f.status}</StatusPill>
                    </div>
                    <div className="mt-1 text-[12.5px] text-muted">{f.resolved_by} · {fmtDateTime(f.resolved_at)} · owner {f.owner_name}</div>
                    {f.decision_note && <p className="mt-2 border-s-2 border-accent ps-3 text-[13px] leading-relaxed text-ink-2" dir="auto">{f.decision_note}</p>}
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>

      <div className="flex flex-col gap-5">
        <Card className="p-6">
          <SectionTitle>From the case tracker</SectionTitle>
          {c.status === "Open" && (c.next_action_due || c.next_hearing_date) ? (
            <ul className="flex flex-col gap-4 text-[13.5px]">
              {c.next_action_due && (
                <li className="flex items-start gap-3">
                  <CalendarClock size={16} className="mt-0.5 shrink-0 text-muted" />
                  <span className="min-w-0 flex-1">
                    <span className="block font-medium text-ink">{c.next_action ?? "Next action"}</span>
                    <span className="text-[12.5px] text-muted">Due {fmtDate(c.next_action_due)} · {c.lead_counsel}</span>
                  </span>
                  {due != null && <DuePill days={due} lead={o.reminder_lead_days} />}
                </li>
              )}
              {c.next_hearing_date && (
                <li className="flex items-start gap-3">
                  <Gavel size={16} className="mt-0.5 shrink-0 text-muted" />
                  <span className="min-w-0 flex-1">
                    <span className="block font-medium text-ink">Hearing</span>
                    <span className="text-[12.5px] text-muted">{fmtDate(c.next_hearing_date)} · {c.court_name}</span>
                  </span>
                  {hearing != null && hearing >= 0 && <span className="whitespace-nowrap text-[12.5px] text-muted">{relativeDays(hearing)}</span>}
                </li>
              )}
            </ul>
          ) : <p className="text-[13px] text-muted">No next action or hearing on the tracker.</p>}
        </Card>
        <Card className="bg-surface-2 p-6">
          <SectionTitle>How reminders work</SectionTitle>
          <ol className="flex flex-col gap-3.5 text-[13px] leading-relaxed text-ink-2">
            <li className="flex gap-2.5"><BellRing size={15} className="mt-0.5 shrink-0 text-accent-ink" />
              <span>The owner is reminded before the deadline ({o.reminder_lead_days} days by default).</span></li>
            <li className="flex gap-2.5"><CalendarClock size={15} className="mt-0.5 shrink-0 text-accent-ink" />
              <span>When it is reached, the owner and whoever set it are asked to follow up and decide: close the case, extend or escalate.</span></li>
            <li className="flex gap-2.5"><TriangleAlert size={15} className="mt-0.5 shrink-0 text-accent-ink" />
              <span>{o.escalate_days} days later with no decision, Legal Operations is told as well.</span></li>
          </ol>
          <p className="mt-4 border-t border-line pt-3 text-[12.5px] leading-relaxed text-muted">Reminders appear under the bell{meta?.email_notifications ? " and arrive by e-mail" : ""}. Each decision is recorded in the audit trail.</p>
        </Card>
      </div>

      {creating && <FollowUpDialog c={c} onClose={() => setCreating(false)} onSaved={changed} />}
      {resolving && <ResolveDialog c={c} f={resolving} onClose={() => setResolving(null)} onSaved={changed} />}
      {editing && <EditFollowUpDialog c={c} f={editing} onClose={() => setEditing(null)} onSaved={changed} />}
    </div>
  );
}

const REMINDERS = [0, 1, 3, 7, 14];
const reminderLabel = (d: number) => (d === 0 ? "On the day only" : `${d} day${d === 1 ? "" : "s"} before`);

function FollowUpDialog({ c, onClose, onSaved }: { c: CaseDetail; onClose: () => void; onSaved: () => void }) {
  const { user, users, meta } = useSession();
  const toast = useToast();
  const o = meta!.case_options;
  const today = meta!.demo_today;
  const owners = useOwners(c.access_group);
  const first = o.follow_up_kinds[0];
  const [kind, setKind] = useState(first.kind);
  const [title, setTitle] = useState(first.title);
  const [start, setStart] = useState(today);
  const [days, setDays] = useState<string>(String(first.days));
  const [due, setDue] = useState(addDays(today, first.days));
  const [owner, setOwner] = useState(owners.some((u) => u.user_id === c.lead_counsel_id) ? c.lead_counsel_id : (owners[0]?.user_id ?? ""));
  const [remind, setRemind] = useState(o.reminder_lead_days);
  const [details, setDetails] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const pickKind = (k: string) => {
    const preset = o.follow_up_kinds.find((x) => x.kind === k)!;
    const previous = o.follow_up_kinds.find((x) => x.kind === kind)!;
    setKind(k);
    if (!title.trim() || title === previous.title) setTitle(preset.title);
    setDays(String(preset.days));
    setDue(addDays(start, preset.days));
  };
  const setPeriod = (value: string) => { setDays(value); const n = parseInt(value, 10); if (n > 0) setDue(addDays(start, n)); };
  const setStartDate = (value: string) => { setStart(value); const n = parseInt(days, 10); if (value && n > 0) setDue(addDays(value, n)); };
  const setDueDate = (value: string) => { setDue(value); const n = daysFrom(start, value); if (n != null && n >= 0) setDays(String(n)); };

  const ownerName = users.find((u) => u.user_id === owner)?.full_name ?? "The owner";
  const left = daysFrom(today, due) ?? 0;
  const preview = left <= 0
    ? `The deadline is already reached: ${ownerName} is notified now to follow up and decide.`
    : `${ownerName} is reminded ${remind ? `on ${fmtDate(addDays(due, -remind))}` : "on the day"}, asked to follow up and decide on ${fmtDate(due)}, ` +
      `and Legal Operations is told on ${fmtDate(addDays(due, o.escalate_days))} if nothing has been decided.`;

  const save = async () => {
    if (!user) return;
    setBusy(true); setError(null);
    try {
      const made = await api.createFollowUp(c.case_id, {
        kind, title, details: details || undefined, owner_id: owner, start_date: start, due_date: due, remind_days: remind,
      });
      onSaved();
      toast("success", `${made.follow_up_id} set: due ${fmtDate(made.due_date)}, owner ${made.owner_name}.`);
      onClose();
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };

  return (
    <Dialog open onClose={onClose} busy={busy} icon={<CalendarPlus size={18} />} title="Add a follow-up" subtitle={`${c.case_id} · ${c.title}`}
      footer={<>
        <Button variant="ghost" onClick={onClose} disabled={busy}>Cancel</Button>
        <Button variant="primary" onClick={save} disabled={busy || !title.trim() || !due || !owner}>{busy ? "Saving…" : "Set follow-up"}</Button>
      </>}>
      <FormError>{error}</FormError>
      <div className="grid gap-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Kind"><SelectInput value={kind} onChange={(e) => pickKind(e.target.value)} options={o.follow_up_kinds.map((k) => k.kind)} /></Field>
          <Field label="Owner"><SelectInput value={owner} onChange={(e) => setOwner(e.target.value)}
            options={owners.map((u) => ({ value: u.user_id, label: `${u.full_name}${u.user_id === c.lead_counsel_id ? " (case owner)" : ""}` }))} /></Field>
        </div>
        <Field label="What is due"><TextInput value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200}
          placeholder="e.g. Store to remove the infringing products" /></Field>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Starts"><TextInput type="date" value={start} onChange={(e) => setStartDate(e.target.value)} /></Field>
          <Field label="Days given"><TextInput type="number" min={1} max={3650} value={days} onChange={(e) => setPeriod(e.target.value)} /></Field>
          <Field label="Deadline"><TextInput type="date" value={due} min={start} onChange={(e) => setDueDate(e.target.value)} /></Field>
        </div>
        <div className="-mt-1 flex flex-wrap gap-1.5">
          {[7, 14, 30, 60, 90].map((n) => (
            <button key={n} type="button" onClick={() => setPeriod(String(n))} aria-pressed={days === String(n)}
              className={clsx("rounded-md px-2.5 py-1 text-[12.5px] font-medium transition-colors",
                days === String(n) ? "bg-primary text-primary-ink" : "bg-surface-3 text-ink-2 hover:text-ink")}>
              {n} days
            </button>
          ))}
        </div>
        <Field label="Remind the owner">
          <SelectInput value={String(remind)} onChange={(e) => setRemind(Number(e.target.value))}
            options={REMINDERS.map((d) => ({ value: String(d), label: reminderLabel(d) }))} />
        </Field>
        <Field label="Details" optional><TextArea value={details} onChange={(e) => setDetails(e.target.value)} rows={2} maxLength={2000}
          placeholder="e.g. Notice served in person on the store manager; photos on file" /></Field>
        <div className="flex gap-2.5 rounded-lg border border-accent-line bg-accent-soft p-3 text-[13px] leading-relaxed text-ink-2">
          <BellRing size={15} className="mt-0.5 shrink-0 text-accent-ink" /><span>{preview}</span>
        </div>
      </div>
    </Dialog>
  );
}

const DECISION_COPY: Record<Decision, { icon: typeof Check; title: string; text: string }> = {
  close_case: { icon: CircleCheck, title: "Complied – close the case", text: "The other side complied. The case is closed with the outcome you choose." },
  keep_open: { icon: Check, title: "Done – keep the case open", text: "This follow-up is complete; work on the case continues." },
  escalate: { icon: TriangleAlert, title: "Not complied – escalate", text: "Record what was found and set the next enforcement step." },
  cancel: { icon: Ban, title: "No longer needed", text: "Close this follow-up without any change to the case." },
};

function ResolveDialog({ c, f, onClose, onSaved }: { c: CaseDetail; f: FollowUp; onClose: () => void; onSaved: () => void }) {
  const { user, meta } = useSession();
  const toast = useToast();
  const o = meta!.case_options;
  const today = meta!.demo_today;
  const choices = o.decisions.filter((d) => d.value !== "close_case" || c.status === "Open");
  const [decision, setDecision] = useState<Decision>(choices[0].value);
  const [note, setNote] = useState("");
  const [outcome, setOutcome] = useState("Takedown achieved");
  const [closedOn, setClosedOn] = useState(today);
  const [nextAction, setNextAction] = useState("");
  const [nextDue, setNextDue] = useState(addDays(today, 14));
  const [stage, setStage] = useState("");
  const [gate, setGate] = useState<string | null>(null);
  const [override, setOverride] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { setGate(null); setError(null); }, [decision]);

  const needsNote = decision === "escalate" || decision === "cancel";
  const save = async () => {
    if (!user) return;
    if (gate && !override.trim()) { setError("Give the reason for going ahead, or choose another decision."); return; }
    setBusy(true); setError(null);
    try {
      await api.resolveFollowUp(f.follow_up_id, {
        decision, note: note || undefined,
        ...(decision === "close_case" ? { outcome, closed_date: closedOn } : {}),
        ...(decision === "escalate" ? { case_changes: { next_action: nextAction || undefined, next_action_due: nextAction ? nextDue : undefined, stage: stage || undefined } } : {}),
        ...(gate ? { override_reason: override } : {}),
      });
      onSaved();
      toast("success", decision === "close_case" ? `${c.case_id} closed: ${outcome}.` : "Decision recorded in the audit trail.");
      onClose();
    } catch (e) {
      if (e instanceof ApiError && e.code === "consultation_required") setGate(e.message);
      else setError((e as Error).message);
    } finally { setBusy(false); }
  };

  return (
    <Dialog open onClose={onClose} busy={busy} icon={<CircleCheck size={18} />} title="Record the follow-up decision"
      subtitle={`${f.title} · due ${fmtDate(f.due_date)} (${relativeDays(f.days_left)})`}
      footer={<>
        <Button variant="ghost" onClick={onClose} disabled={busy}>Cancel</Button>
        <Button variant="primary" onClick={save} disabled={busy || (needsNote && !note.trim())}>{busy ? "Saving…" : "Record decision"}</Button>
      </>}>
      {gate && <GateNotice message={gate} reason={override} setReason={setOverride} />}
      <FormError>{error}</FormError>
      <div role="radiogroup" aria-label="Decision" className="grid gap-2 sm:grid-cols-2">
        {choices.map((d) => {
          const copy = DECISION_COPY[d.value];
          const Icon = copy.icon;
          return (
            <button key={d.value} type="button" role="radio" aria-checked={decision === d.value} onClick={() => setDecision(d.value)}
              className={clsx("flex gap-3 rounded-lg border p-3.5 text-start transition-colors",
                decision === d.value ? "border-accent bg-accent-soft ring-1 ring-accent" : "border-line-strong bg-surface hover:bg-surface-2")}>
              <Icon size={17} className={clsx("mt-0.5 shrink-0", decision === d.value ? "text-accent-ink" : "text-ink-2")} />
              <span>
                <span className="block text-[13.5px] font-medium text-ink">{copy.title}</span>
                <span className="mt-0.5 block text-[12.5px] leading-relaxed text-ink-2">{copy.text}</span>
              </span>
            </button>
          );
        })}
      </div>
      <div className="mt-5 grid gap-4">
        {decision === "close_case" && (
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Outcome"><SelectInput value={outcome} onChange={(e) => setOutcome(e.target.value)} options={o.outcomes} /></Field>
            <Field label="Closed on"><TextInput type="date" value={closedOn} max={today} min={c.opened_date} onChange={(e) => setClosedOn(e.target.value)} /></Field>
          </div>
        )}
        {decision === "escalate" && (
          <>
            <div className="grid gap-4 sm:grid-cols-[1fr_170px]">
              <Field label="Next step" optional><TextInput value={nextAction} onChange={(e) => setNextAction(e.target.value)} maxLength={200}
                placeholder="e.g. File a statement of claim" /></Field>
              <Field label="Due"><TextInput type="date" value={nextDue} onChange={(e) => setNextDue(e.target.value)} disabled={!nextAction} /></Field>
            </div>
            <Field label="Move the case to" optional hint="Moving to a notice, filing or court stage starts enforcement.">
              <SelectInput value={stage} onChange={(e) => setStage(e.target.value)} options={o.stages_open.filter((s) => s !== c.stage)}
                placeholder={`Keep at ${c.stage}`} />
            </Field>
          </>
        )}
        <Field label={decision === "escalate" ? "What was found" : decision === "cancel" ? "Why it is no longer needed" : "Note"} optional={!needsNote}>
          <TextArea value={note} onChange={(e) => setNote(e.target.value)} rows={3} maxLength={2000}
            placeholder={decision === "close_case" ? "e.g. Store visit on 5 Nov: no infringing products on the shelves" : undefined} />
        </Field>
      </div>
    </Dialog>
  );
}

function EditFollowUpDialog({ c, f, onClose, onSaved }: { c: CaseDetail; f: FollowUp; onClose: () => void; onSaved: () => void }) {
  const { user } = useSession();
  const toast = useToast();
  const owners = useOwners(c.access_group);
  const [title, setTitle] = useState(f.title);
  const [owner, setOwner] = useState(f.owner_id);
  const [due, setDue] = useState(f.due_date);
  const [remind, setRemind] = useState(f.remind_days);
  const [details, setDetails] = useState(f.details ?? "");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const moved = due !== f.due_date;
  const changes = useMemo(() => {
    const out: Record<string, unknown> = {};
    if (title.trim() !== f.title) out.title = title.trim();
    if (owner !== f.owner_id) out.owner_id = owner;
    if (moved) out.due_date = due;
    if (remind !== f.remind_days) out.remind_days = remind;
    if ((details.trim() || null) !== f.details) out.details = details.trim() || null;
    return out;
  }, [title, owner, due, remind, details, f, moved]);

  const save = async () => {
    if (!user) return;
    setBusy(true); setError(null);
    try {
      await api.updateFollowUp(f.follow_up_id, changes, reason);
      onSaved();
      toast("success", moved ? `Deadline moved to ${fmtDate(due)}.` : "Follow-up updated.");
      onClose();
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };

  return (
    <Dialog open onClose={onClose} busy={busy} icon={<Pencil size={17} />} title="Change or extend the follow-up" subtitle={`${f.follow_up_id} · ${f.title}`}
      footer={<>
        <Button variant="ghost" onClick={onClose} disabled={busy}>Cancel</Button>
        <Button variant="primary" onClick={save} disabled={busy || !Object.keys(changes).length || (moved && !reason.trim())}>{busy ? "Saving…" : "Save"}</Button>
      </>}>
      <FormError>{error}</FormError>
      <div className="grid gap-4">
        <Field label="What is due"><TextInput value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} /></Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Owner"><SelectInput value={owner} onChange={(e) => setOwner(e.target.value)} options={owners.map((u) => ({ value: u.user_id, label: u.full_name }))} /></Field>
          <Field label="Remind the owner"><SelectInput value={String(remind)} onChange={(e) => setRemind(Number(e.target.value))}
            options={REMINDERS.map((d) => ({ value: String(d), label: reminderLabel(d) }))} /></Field>
        </div>
        <Field label="Deadline" hint={`Currently ${fmtDate(f.due_date)}.`}>
          <TextInput type="date" value={due} min={f.start_date} onChange={(e) => setDue(e.target.value)} />
        </Field>
        <div className="-mt-1 flex flex-wrap gap-1.5">
          {[7, 14, 30].map((n) => (
            <button key={n} type="button" onClick={() => setDue(addDays(f.due_date, n))}
              className="rounded-md bg-surface-3 px-2.5 py-1 text-[12.5px] font-medium text-ink-2 transition-colors hover:text-ink">+{n} days</button>
          ))}
        </div>
        <Field label="Details" optional><TextArea value={details} onChange={(e) => setDetails(e.target.value)} rows={2} maxLength={2000} /></Field>
        <Field label={moved ? "Why the deadline changes" : "Reason for the change"} optional={!moved}
          hint="Recorded in the audit trail with your name and the time.">
          <TextInput value={reason} onChange={(e) => setReason(e.target.value)} maxLength={2000}
            placeholder={moved ? "e.g. Infringer's counsel asked for two more weeks" : undefined} />
        </Field>
      </div>
    </Dialog>
  );
}
