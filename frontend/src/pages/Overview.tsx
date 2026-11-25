import clsx from "clsx";
import { useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, CalendarClock, ChevronRight, CircleCheck, CircleCheckBig, ClipboardPlus, UserRoundCheck } from "lucide-react";
import { api } from "../api";
import { RegisterCaseDialog } from "../components/case/RegisterCaseDialog";
import { DateBlock, DuePill } from "../components/case/FollowUpsPanel";
import { Button, Card, PageHeader, type Icon } from "../components/ui";
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
  const { data: cases, error } = useApi<CaseRow[] | null>(() => (user ? api.cases() : Promise.resolve(null)), [user?.user_id, meta?.demo_today]);
  const { data: work } = useApi<Worklist | null>(() => (user ? api.worklist() : Promise.resolve(null)), [user?.user_id, meta?.demo_today]);

  if (!user) return null;
  if (error) return <Card className="p-6 text-[14px] text-critical-ink">The overview couldn't be loaded. Please try again in a moment.</Card>;

  const lead = work?.lead_days ?? meta?.case_options.reminder_lead_days ?? 7;
  const due = (work?.items ?? []).filter((i) => i.days_left <= lead);
  const mine = due.filter((i) => i.mine);
  const attention: WorkItem[] = (mine.length ? mine : due).slice(0, ATTENTION_ROWS);
  const open = (cases ?? []).filter((r) => r.status === "Open");
  const intake = open.filter((r) => r.stage === "Intake").length;
  const myOpen = open.filter((r) => r.lead_counsel_id === user.user_id).length;
  const decisions = (work?.items ?? []).filter((i) => i.type === "follow_up" && i.days_left <= 0 && (i.mine || !mine.length)).length;
  const loading = !cases || !work;
  const week = (mine.length ? mine : due).length;

  return (
    <>
      <PageHeader
        eyebrow={fmtDate(meta?.demo_today, { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
        title={`${greeting()}, ${user.full_name.split(" ")[0]}`}
        subtitle="What needs doing today."
        actions={user.can_edit && <Button variant="primary" icon={ClipboardPlus} onClick={() => setRegistering(true)}>Register a case</Button>}
      />

      <Card className="overflow-hidden animate-fade-up">
        <ol className="grid grid-cols-1 gap-px bg-line sm:grid-cols-2 xl:grid-cols-4" aria-label="Case workflow">
          <Step n={1} icon={ClipboardPlus} title="Register" text="Record a new infringement."
            onClick={user.can_edit ? () => setRegistering(true) : undefined} cta={user.can_edit ? "Register a case" : undefined} />
          <Step n={2} icon={UserRoundCheck} title="Assign" loading={loading}
            text={intake ? <><Figure>{intake}</Figure> new {intake === 1 ? "case" : "cases"} at intake</> : "No new cases waiting"}
            onClick={() => navigate("/cases?stage=Intake")} cta="View new cases" />
          <Step n={3} icon={CalendarClock} title="Follow up" loading={loading} highlight={due.length > 0}
            text={due.length ? <><Figure>{week}</Figure> {week === 1 ? "deadline" : "deadlines"} this week</> : "Nothing due this week"}
            onClick={() => navigate("/follow-ups")} cta="Open follow-ups" />
          <Step n={4} icon={CircleCheckBig} title="Close" loading={loading} last
            text={decisions ? <><Figure>{decisions}</Figure> {decisions === 1 ? "decision" : "decisions"} due</>
              : <><Figure>{myOpen}</Figure> open {myOpen === 1 ? "case" : "cases"} of yours</>}
            onClick={() => navigate(decisions ? "/follow-ups" : "/cases?owner=me")} cta={decisions ? "Record decisions" : "My cases"} />
        </ol>
      </Card>

      <Card className="mt-6 animate-fade-up">
        <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-2 px-6 pb-4 pt-5">
          <div>
            <h2 className="text-[16px] font-semibold text-ink">Needs attention</h2>
            <p className="mt-0.5 text-[13px] text-muted">
              {mine.length ? "Your deadlines" : "Deadlines on the cases you can see"}: overdue, or due within {lead} days.
            </p>
          </div>
          <Link to="/follow-ups" className="inline-flex items-center gap-1 text-[13px] font-medium text-accent-ink underline-offset-2 hover:underline">
            All follow-ups <ArrowRight size={14} />
          </Link>
        </div>
        {!work && <p className="border-t border-line px-6 py-10 text-center text-[13.5px] text-muted">Loading…</p>}
        {work && !attention.length && (
          <div className="mx-6 mb-6 flex items-center gap-3 rounded-lg border border-good-line bg-good-soft px-4 py-3.5 text-[13.5px] text-ink">
            <CircleCheck size={18} className="shrink-0 text-good" /> Nothing is overdue or due in the next {lead} days.
          </div>
        )}
        {attention.length > 0 && (
          <ul className="divide-y divide-line border-t border-line">
            {attention.map((i) => (
              <li key={i.id}>
                <button type="button" onClick={() => navigate(i.link)}
                  className="group flex w-full items-center gap-4 px-6 py-3.5 text-start transition-colors hover:bg-surface-2">
                  <DateBlock iso={i.due_date} state={deadlineState(i.days_left, lead)} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[14.5px] font-medium text-ink" dir="auto">{i.title}</span>
                    <span className="mt-0.5 block truncate text-[13px] text-muted">
                      <span className="font-medium text-ink-2">{i.case_id}</span> · {i.case_title}{i.mine ? "" : ` · ${i.owner_name}`}
                    </span>
                    <span className="mt-2 block sm:hidden"><DuePill days={i.days_left} lead={lead} /></span>
                  </span>
                  <span className="hidden shrink-0 sm:block"><DuePill days={i.days_left} lead={lead} /></span>
                  <ChevronRight size={16} className="hidden shrink-0 text-line-strong transition-colors group-hover:text-ink-2 sm:block" aria-hidden />
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <RegisterCaseDialog open={registering} onClose={() => setRegistering(false)} />
    </>
  );
}

function Figure({ children }: { children: ReactNode }) {
  return <span className="tabular font-semibold text-ink">{children}</span>;
}

/** One stage of the workflow, in a ruled row of four: its number, what is waiting there, and the way in. */
function Step({ n, icon: IconCmp, title, text, onClick, cta, loading = false, highlight = false, last = false }: {
  n: number; icon: Icon; title: string; text: ReactNode; onClick?: () => void; cta?: string; loading?: boolean; highlight?: boolean; last?: boolean;
}) {
  const body = (
    <>
      <span className="flex items-center gap-3">
        <span className={clsx("tabular grid size-7 shrink-0 place-items-center rounded-full text-[12.5px] font-semibold",
          highlight ? "bg-accent text-accent-contrast" : "bg-surface-3 text-ink-2")}>{n}</span>
        <span className="text-[15.5px] font-semibold text-ink"><span className="sr-only">Step {n}: </span>{title}</span>
        <IconCmp size={18} strokeWidth={1.6} className={clsx("ms-auto shrink-0", highlight ? "text-accent" : "text-muted/55")} aria-hidden />
      </span>
      <span className="mt-4 block min-h-[21px] text-[14px] text-ink-2">
        {loading ? <span className="skeleton inline-block h-3.5 w-36 align-middle" /> : text}
      </span>
      {cta && (
        <span className="mt-2.5 inline-flex items-center gap-1 text-[13px] font-medium text-accent-ink">
          {cta} <ArrowRight size={14} className="transition-transform group-hover:translate-x-0.5" />
        </span>
      )}
      {!last && (
        <span aria-hidden className="absolute -end-[9px] top-[26px] z-10 hidden size-[18px] place-items-center rounded-full border border-line bg-surface text-muted xl:grid">
          <ChevronRight size={11} strokeWidth={2.4} />
        </span>
      )}
    </>
  );
  const box = "relative block h-full w-full bg-surface px-6 py-5 text-start";
  return (
    <li className="relative">
      {onClick ? (
        <button type="button" onClick={onClick} className={clsx(box, "group transition-colors hover:bg-surface-2")}>{body}</button>
      ) : <div className={box}>{body}</div>}
    </li>
  );
}
