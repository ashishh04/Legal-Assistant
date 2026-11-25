import clsx from "clsx";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { CalendarClock, Gavel, ListChecks, Search } from "lucide-react";
import { DateBlock, DuePill } from "../components/case/FollowUpsPanel";
import { Segmented } from "../components/forms";
import { Card, Chip, EmptyState, PageHeader, SearchField, Select, StatStrip, StatTile, StatusPill } from "../components/ui";
import { api } from "../api";
import { fmtDate, fmtDateTime } from "../lib/format";
import { useApi } from "../lib/hooks";
import { deadlineState } from "../lib/labels";
import { useSession } from "../session";
import type { WorkItem, Worklist } from "../types";

type Scope = "mine" | "all";
const GROUPS = [
  { state: "overdue", title: "Overdue" },
  { state: "today", title: "Due today" },
  { state: "soon", title: "Coming up" },
  { state: "later", title: "Later" },
] as const;

/** Every open deadline the user can see, soonest first: their own by default. */
export default function FollowUps() {
  const { user, meta } = useSession();
  const { data, error, loading, reload } = useApi<Worklist | null>(
    () => (user ? api.worklist() : Promise.resolve(null)), [user?.user_id, meta?.demo_today]);
  const [scope, setScope] = useState<Scope>("mine");
  const [type, setType] = useState("");
  const [q, setQ] = useState("");
  const mineCount = data?.items.filter((i) => i.mine).length ?? 0;
  useEffect(() => { if (data) setScope(data.items.some((i) => i.mine) ? "mine" : "all"); }, [data?.as_of, user?.user_id]);  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    window.addEventListener("ferrero:records", reload);
    return () => window.removeEventListener("ferrero:records", reload);
  }, [reload]);

  const lead = data?.lead_days ?? 7;
  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return (data?.items ?? []).filter((i) => (scope === "all" || i.mine) && (!type || i.type === type) &&
      (!needle || [i.case_id, i.case_title ?? "", i.title, i.owner_name].some((v) => v.toLowerCase().includes(needle))));
  }, [data, scope, type, q]);
  const grouped = useMemo(() => {
    const m: Record<string, WorkItem[]> = { overdue: [], today: [], soon: [], later: [] };
    for (const i of shown) m[deadlineState(i.days_left, lead)].push(i);
    return m;
  }, [shown, lead]);
  const resolved = (data?.resolved ?? []).filter((i) => scope === "all" || i.mine);

  if (!user) return null;
  return (
    <>
      <PageHeader eyebrow={data ? `As of ${fmtDate(data.as_of, { weekday: "long", day: "numeric", month: "long", year: "numeric" })}` : undefined} title="Follow-ups"
        subtitle={<>Follow-ups set on cases, and the next actions and hearings from the case tracker. Owners are reminded
          {` ${lead}`} days ahead and told when a deadline is reached; {data?.escalate_days ?? 3} days after, Legal Operations is told too.</>} />

      <StatStrip className={clsx("mb-6 transition-opacity sm:grid-cols-2 lg:grid-cols-4", loading && data && "opacity-60")}>
        <StatTile label="Overdue" value={grouped.overdue.length} sub="Past the deadline, no decision"
          status={grouped.overdue.length ? { kind: "critical", text: "Needs a decision" } : { kind: "good", text: "None overdue" }} />
        <StatTile label="Due today" value={grouped.today.length} sub="Follow up and decide today" />
        <StatTile label={`In the next ${lead} days`} value={grouped.soon.length} sub="Reminders already sent" />
        <StatTile label="Later" value={grouped.later.length} sub="Further out" />
      </StatStrip>

      <div className="mb-5 flex flex-wrap items-center gap-2">
        <Segmented<Scope> label="Whose deadlines" value={scope} onChange={setScope}
          options={[{ value: "mine", label: `Mine · ${mineCount}` }, { value: "all", label: `Everyone's I can see · ${data?.items.length ?? 0}` }]} />
        <Select label="Kind" value={type} onChange={setType}
          options={[{ value: "", label: "All" }, { value: "follow_up", label: "Follow-ups" }, { value: "next_action", label: "Next actions" }, { value: "hearing", label: "Hearings" }]} />
        <SearchField icon={Search} value={q} onChange={setQ} placeholder="Case, party, owner…" label="Filter deadlines" className="flex-1 sm:max-w-[280px]" />
      </div>

      {error && <Card className="p-6 text-[14px] text-critical-ink">The deadlines couldn't be loaded. Please try again in a moment.</Card>}
      {!data && !error && <div className="py-16 text-center text-[14px] text-muted">Loading deadlines…</div>}
      {data && !shown.length && (
        <EmptyState icon={ListChecks} title={scope === "mine" ? "No open deadlines of yours" : "No open deadlines"}>
          {scope === "mine" ? "Switch to everyone's to see the deadlines on all the cases you can access." : "Nothing is due on the cases you can see."}
        </EmptyState>
      )}

      <div className="flex flex-col gap-5">
        {GROUPS.map(({ state, title }) => grouped[state].length > 0 && (
          <Card key={state} className="overflow-hidden">
            <div className="flex items-center gap-2.5 border-b border-line bg-surface-2 px-6 py-3">
              <span aria-hidden className={clsx("size-2 rounded-full",
                state === "overdue" ? "bg-critical" : state === "today" ? "bg-warning" : state === "soon" ? "bg-accent" : "bg-line-strong")} />
              <h2 className="text-[14px] font-semibold text-ink">{title}</h2>
              <span className="tabular rounded-full bg-surface-3 px-1.5 py-px text-[11.5px] font-semibold text-ink-2">{grouped[state].length}</span>
            </div>
            <ul className="divide-y divide-line">
              {grouped[state].map((i) => <Row key={i.id} i={i} lead={lead} />)}
            </ul>
          </Card>
        ))}
        {resolved.length > 0 && (
          <Card className="overflow-hidden">
            <div className="border-b border-line bg-surface-2 px-6 py-3">
              <h2 className="text-[14px] font-semibold text-ink">Recently resolved</h2>
            </div>
            <ul className="divide-y divide-line">
              {resolved.map((i) => (
                <li key={i.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-6 py-3 text-[13.5px]">
                  <Link to={i.link} className="font-medium text-ink underline-offset-2 hover:text-accent-ink hover:underline">{i.case_id}</Link>
                  <span className="min-w-0 flex-1 text-ink-2" dir="auto">{i.title}</span>
                  <StatusPill kind={i.status === "Cancelled" ? "neutral" : "good"}>{i.decision_label ?? i.status}</StatusPill>
                  <span className="text-[12.5px] text-muted">{i.resolved_by} · {fmtDateTime(i.resolved_at)}</span>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>
    </>
  );
}

function Row({ i, lead }: { i: WorkItem; lead: number }) {
  const Icon = i.type === "hearing" ? Gavel : i.type === "next_action" ? CalendarClock : ListChecks;
  return (
    <li className="flex items-center gap-4 px-6 py-3.5 transition-colors hover:bg-surface-2">
      <DateBlock iso={i.due_date} state={deadlineState(i.days_left, lead)} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
          <Link to={i.link} className="text-[14.5px] font-medium text-ink underline-offset-2 hover:text-accent-ink hover:underline" dir="auto">{i.title}</Link>
          <Chip><Icon size={11} /> {i.type === "follow_up" ? i.kind : i.type === "hearing" ? "Hearing" : "Next action"}</Chip>
        </div>
        <div className="mt-0.5 truncate text-[13px] text-muted">
          <Link to={i.link} className="font-medium text-ink-2 underline-offset-2 hover:underline">{i.case_id}</Link> · {i.case_title} · owner {i.owner_name}{i.mine ? " (you)" : ""}
        </div>
        <div className="mt-2 sm:hidden"><DuePill days={i.days_left} lead={lead} /></div>
      </div>
      <div className="hidden shrink-0 sm:block"><DuePill days={i.days_left} lead={lead} /></div>
    </li>
  );
}
