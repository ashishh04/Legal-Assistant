import clsx from "clsx";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { CalendarClock, Check, CircleCheckBig, ClipboardPlus, UserRoundCheck } from "lucide-react";
import { api, recordsChanged } from "../../api";
import { daysFrom, fmtDate, relativeDays } from "../../lib/format";
import { useToast } from "../../lib/toast";
import { useSession } from "../../session";
import type { CaseDetail } from "../../types";
import { Dialog } from "../Dialog";
import { Field, FormError, SelectInput, TextArea, TextInput } from "../forms";
import { Button, Card } from "../ui";
import { useOwners } from "./shared";

type Step = { key: string; label: string; icon: typeof Check; state: "done" | "current" | "todo"; detail: ReactNode; action?: ReactNode };

/** The case's place in the workflow (register, assign, follow up, close), with the next action one click away. */
export function WorkflowBar({ c, onAssign, onFollowUp, onClose }:
  { c: CaseDetail; onAssign: () => void; onFollowUp: () => void; onClose: () => void }) {
  const { meta } = useSession();
  const today = meta?.demo_today ?? "";
  const closed = c.status === "Closed";
  const canEdit = c.permissions.edit;
  const open = c.follow_ups.filter((f) => f.status === "Open").sort((a, b) => a.due_date.localeCompare(b.due_date));
  const next = open[0];
  const nextDue = next ? next.due_date : c.next_action_due;
  const nextDays = daysFrom(today, nextDue);
  const action = (label: string, onClick: () => void) => canEdit && !closed && (
    <button type="button" onClick={onClick} className="text-[12.5px] font-medium text-accent-ink hover:underline">{label}</button>
  );

  const steps: Step[] = [
    { key: "register", label: "Registered", icon: ClipboardPlus, state: "done",
      detail: <>{fmtDate(c.opened_date)} · {c.source_channel}</> },
    { key: "assign", label: "Assigned", icon: UserRoundCheck, state: "done",
      detail: c.lead_counsel, action: action("Reassign", onAssign) },
    { key: "follow", label: "Follow up", icon: CalendarClock, state: closed ? "done" : "current",
      detail: closed ? "Done" : next ? <>{open.length} open · next {relativeDays(nextDays)}</>
        : c.next_action_due ? <>Next action {relativeDays(nextDays)}</> : "No deadline set",
      action: action("Add follow-up", onFollowUp) },
    { key: "close", label: closed ? "Closed" : "Close", icon: CircleCheckBig, state: closed ? "done" : "todo",
      detail: closed ? <>{fmtDate(c.closed_date)} · {c.outcome}</> : "When the matter is resolved",
      action: action("Close case", onClose) },
  ];

  return (
    <Card className="mb-4 p-2 animate-fade-up">
      <ol className="grid grid-cols-2 gap-1 lg:grid-cols-4" aria-label="Case workflow">
        {steps.map((s, i) => (
          <li key={s.key} aria-current={s.state === "current" ? "step" : undefined}
            className={clsx("relative flex items-start gap-3 rounded-xl px-3 py-2.5", s.state === "current" && "bg-accent-soft/60")}>
            <span className={clsx("mt-0.5 grid size-8 shrink-0 place-items-center rounded-full border",
              s.state === "done" ? "border-transparent bg-primary text-primary-ink"
                : s.state === "current" ? "border-accent bg-surface text-accent-ink" : "border-line-strong bg-surface text-muted")}>
              {s.state === "done" ? <Check size={15} strokeWidth={2.4} /> : <s.icon size={15} strokeWidth={1.9} />}
            </span>
            <span className="min-w-0">
              <span className="block text-[11px] font-semibold uppercase tracking-[0.1em] text-muted">Step {i + 1}</span>
              <span className="block text-[13.5px] font-semibold text-ink">{s.label}</span>
              <span className="block truncate text-[12.5px] text-ink-2">{s.detail}</span>
              {s.action && <span className="mt-0.5 block">{s.action}</span>}
            </span>
          </li>
        ))}
      </ol>
    </Card>
  );
}

/** Give the case a new owner; they are notified, and the change goes in the audit trail. */
export function AssignDialog({ c, open, onClose, onSaved }:
  { c: CaseDetail; open: boolean; onClose: () => void; onSaved: (c: CaseDetail) => void }) {
  const toast = useToast();
  const owners = useOwners(c.access_group);
  const [owner, setOwner] = useState(c.lead_counsel_id);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) { setOwner(c.lead_counsel_id); setReason(""); setError(null); } }, [open, c.lead_counsel_id]);
  const options = useMemo(() => owners.map((u) => ({ value: u.user_id, label: `${u.full_name} · ${u.job_title}` })), [owners]);
  const chosen = owners.find((u) => u.user_id === owner);

  const save = async () => {
    if (owner === c.lead_counsel_id) { onClose(); return; }
    setBusy(true); setError(null);
    try {
      const res = await api.updateCase(c.case_id, { lead_counsel_id: owner }, reason);
      onSaved(res.case);
      recordsChanged();
      toast("success", `${c.case_id} is now assigned to ${chosen?.full_name ?? owner}. They have been notified.`);
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} busy={busy} icon={<UserRoundCheck size={17} />} title={`Assign ${c.case_id}`} subtitle={c.title}
      footer={<>
        <Button variant="ghost" onClick={onClose} disabled={busy}>Cancel</Button>
        <Button variant="primary" onClick={save} disabled={busy || owner === c.lead_counsel_id}>{busy ? "Saving…" : "Assign"}</Button>
      </>}>
      <FormError>{error}</FormError>
      <div className="grid gap-4">
        <Field label="Case owner" hint={`Members of the legal team who cover ${c.country}. The new owner is notified and receives the case's reminders.`}>
          <SelectInput value={owner} onChange={(e) => setOwner(e.target.value)} options={options} />
        </Field>
        <Field label="Note for the audit trail" optional>
          <TextArea value={reason} onChange={(e) => setReason(e.target.value)} rows={2} maxLength={2000}
            placeholder="e.g. Hearing preparation needs litigation counsel" />
        </Field>
      </div>
    </Dialog>
  );
}

/** Close the case with its outcome; open follow-ups close with it. */
export function CloseCaseDialog({ c, open, onClose, onSaved }:
  { c: CaseDetail; open: boolean; onClose: () => void; onSaved: (c: CaseDetail) => void }) {
  const { meta } = useSession();
  const toast = useToast();
  const today = meta!.demo_today;
  const [outcome, setOutcome] = useState("");
  const [closedOn, setClosedOn] = useState(today);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) { setOutcome(""); setClosedOn(today); setReason(""); setError(null); } }, [open, today]);
  const openFollowUps = c.follow_ups.filter((f) => f.status === "Open").length;

  const save = async () => {
    if (!outcome) { setError("Choose the outcome."); return; }
    setBusy(true); setError(null);
    try {
      const res = await api.updateCase(c.case_id, { status: "Closed", outcome, closed_date: closedOn }, reason);
      onSaved(res.case);
      recordsChanged();
      toast("success", `${c.case_id} closed: ${outcome}.`);
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} busy={busy} icon={<CircleCheckBig size={17} />} title={`Close ${c.case_id}`} subtitle={c.title}
      footer={<>
        <Button variant="ghost" onClick={onClose} disabled={busy}>Cancel</Button>
        <Button variant="primary" onClick={save} disabled={busy}>{busy ? "Closing…" : "Close case"}</Button>
      </>}>
      <FormError>{error}</FormError>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Outcome">
          <SelectInput value={outcome} onChange={(e) => setOutcome(e.target.value)} options={meta!.case_options.outcomes} placeholder="Choose the outcome" />
        </Field>
        <Field label="Closed on">
          <TextInput type="date" value={closedOn} min={c.opened_date} max={today} onChange={(e) => setClosedOn(e.target.value)} />
        </Field>
        <Field label="Reason for closing" optional className="sm:col-span-2"
          hint={openFollowUps ? `${openFollowUps} open follow-up${openFollowUps === 1 ? "" : "s"} will close with the case.` : "Saved in the audit trail with your name and the time."}>
          <TextArea value={reason} onChange={(e) => setReason(e.target.value)} rows={2} maxLength={2000}
            placeholder="e.g. Store visit confirmed the products were withdrawn" />
        </Field>
      </div>
    </Dialog>
  );
}
