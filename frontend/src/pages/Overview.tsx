import clsx from "clsx";
import { useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, CalendarClock, CircleCheck, CircleCheckBig, ClipboardPlus, UserRoundCheck } from "lucide-react";
import { api } from "../api";
import { RegisterCaseDialog } from "../components/case/RegisterCaseDialog";
import { DateBlock, DuePill } from "../components/case/FollowUpsPanel";
import { Button, Card, PageHeader, SectionTitle } from "../components/ui";
import { fmtDate, greeting } from "../lib/format";
import { useApi } from "../lib/hooks";
import { deadlineState } from "../lib/labels";
import { useSession } from "../session";
import type { CaseRow, WorkItem, Worklist } from "../types";

const ATTENTION_ROWS = 6;

/** The first page after sign-in: the four workflow steps, each one click away, and what needs doing next. */
export default function Overview() {
  const { user, meta } = useSession();
  const navigate = useNavigate();
  const [registering, setRegistering] = useState(false);
  const { data: cases, error } = useApi<CaseRow[] | null>(() => (user ? api.cases() : Promise.resolve(null)), [user?.user_id]);
  const { data: work } = useApi<Worklist | null>(() => (user ? api.worklist() : Promise.resolve(null)), [user?.user_id]);

  if (!user) return null;
  if (error) return <Card className="p-6 text-[14px] text-critical">The overview couldn't be loaded. Please try again in a moment.</Card>;

  const lead = work?.lead_days ?? meta?.case_options.reminder_lead_days ?? 7;
  const due = (work?.items ?? []).filter((i) => i.days_left <= lead);
  const mine = due.filter((i) => i.mine);
  const attention: WorkItem[] = (mine.length ? mine : due).slice(0, ATTENTION_ROWS);
  const open = (cases ?? []).filter((r) => r.status === "Open");
  const intake = open.filter((r) => r.stage === "Intake").length;
  const myOpen = open.filter((r) => r.lead_counsel_id === user.user_id).length;
  const decisions = (work?.items ?? []).filter((i) => i.type === "follow_up" && i.days_left <= 0 && (i.mine || !mine.length)).length;
  const loading = !cases || !work;

  return (
    <>
      <PageHeader
        eyebrow={`Overview · ${fmtDate(meta?.demo_today)}`}
        title={`${greeting()}, ${user.full_name.split(" ")[0]}`}
        subtitle="What needs doing today."
        actions={user.can_edit && <Button variant="primary" icon={ClipboardPlus} onClick={() => setRegistering(true)}>Register a case</Button>}
      />

      <ol className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4 animate-fade-up" aria-label="Case workflow">
        <Step n={1} icon={ClipboardPlus} title="Register" text="Record a new infringement."
          onClick={user.can_edit ? () => setRegistering(true) : undefined} cta={user.can_edit ? "Register a case" : undefined} />
        <Step n={2} icon={UserRoundCheck} title="Assign" loading={loading}
          text={intake ? `${intake} new ${intake === 1 ? "case" : "cases"} at intake` : "No new cases waiting"}
          onClick={() => navigate("/cases?stage=Intake")} cta="View new cases" />
        <Step n={3} icon={CalendarClock} title="Follow up" loading={loading} highlight={due.length > 0}
          text={due.length ? `${(mine.length ? mine : due).length} ${(mine.length ? mine : due).length === 1 ? "deadline" : "deadlines"} this week` : "Nothing due this week"}
          onClick={() => navigate("/follow-ups")} cta="Open follow-ups" />
        <Step n={4} icon={CircleCheckBig} title="Close" loading={loading}
          text={decisions ? `${decisions} ${decisions === 1 ? "decision" : "decisions"} due` : `${myOpen} open ${myOpen === 1 ? "case" : "cases"} of yours`}
          onClick={() => navigate(decisions ? "/follow-ups" : "/cases?owner=me")} cta={decisions ? "Record decisions" : "My cases"} />
      </ol>

      <Card className="mt-4 p-5">
        <SectionTitle aside={<Link to="/follow-ups" className="inline-flex items-center gap-1 text-[12.5px] font-medium text-accent-ink hover:underline">
          All follow-ups <ArrowRight size={13} /></Link>}>
          Needs attention
        </SectionTitle>
        <p className="-mt-1 mb-3 text-[12.5px] text-muted">
          {mine.length ? "Your deadlines" : "Deadlines on the cases you can see"}: overdue, or due within {lead} days.
        </p>
        {!work && <p className="py-6 text-center text-[13px] text-muted">Loading…</p>}
        {work && !attention.length && (
          <div className="flex items-center gap-3 rounded-xl border border-line bg-surface-2 p-4 text-[13.5px] text-ink-2">
            <CircleCheck size={18} className="shrink-0 text-good" /> Nothing is overdue or due in the next {lead} days.
          </div>
        )}
        <ul className="divide-y divide-line">
          {attention.map((i) => (
            <li key={i.id}>
              <button type="button" onClick={() => navigate(i.link)}
                className="flex w-full items-center gap-4 py-3 text-start transition hover:bg-surface-2/60">
                <DateBlock iso={i.due_date} state={deadlineState(i.days_left, lead)} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[14px] font-medium text-ink" dir="auto">{i.title}</span>
                  <span className="block truncate text-[12.5px] text-ink-2">
                    {i.case_id} · {i.case_title}{i.mine ? "" : ` · ${i.owner_name}`}
                  </span>
                  <span className="mt-1.5 block sm:hidden"><DuePill days={i.days_left} lead={lead} /></span>
                </span>
                <span className="hidden shrink-0 sm:block"><DuePill days={i.days_left} lead={lead} /></span>
              </button>
            </li>
          ))}
        </ul>
      </Card>

      <RegisterCaseDialog open={registering} onClose={() => setRegistering(false)} />
    </>
  );
}

function Step({ n, icon: Icon, title, text, onClick, cta, loading = false, highlight = false }: {
  n: number; icon: typeof ClipboardPlus; title: string; text: ReactNode; onClick?: () => void; cta?: string; loading?: boolean; highlight?: boolean;
}) {
  const body = (
    <>
      <span className="flex items-center gap-3">
        <span className={clsx("grid size-10 shrink-0 place-items-center rounded-xl", highlight ? "bg-accent text-[#141519]" : "bg-accent-soft text-accent-ink")}>
          <Icon size={19} strokeWidth={1.8} />
        </span>
        <span>
          <span className="block text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">Step {n}</span>
          <span className="block text-[16px] font-semibold text-ink">{title}</span>
        </span>
      </span>
      <span className="mt-3 block text-[13.5px] text-ink-2">{loading ? "…" : text}</span>
      {cta && <span className="mt-2 inline-flex items-center gap-1 text-[12.5px] font-medium text-accent-ink">{cta} <ArrowRight size={13} /></span>}
    </>
  );
  return (
    <li>
      {onClick ? (
        <button type="button" onClick={onClick}
          className="block h-full w-full rounded-2xl border border-line bg-surface p-5 text-start shadow-card transition hover:border-line-strong hover:bg-surface-2/40">
          {body}
        </button>
      ) : <div className="h-full rounded-2xl border border-line bg-surface p-5 shadow-card">{body}</div>}
    </li>
  );
}
