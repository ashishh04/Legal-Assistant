import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, RotateCcw, Sparkles } from "lucide-react";
import { api } from "../api";
import { BarList, ChartCard, GroupedColumns, Sparkline, SplitList } from "../components/charts";
import { Pagination, usePagination } from "../components/Pagination";
import { Button, Card, HeroFigure, OUTCOME_SLOTS, PageHeader, Select, StatTile, StatusPill } from "../components/ui";
import { daysFrom, fmtAED, fmtDate, fmtInt, fmtPct, greeting, relativeDays } from "../lib/format";
import { useApi } from "../lib/hooks";
import { useSession } from "../session";
import type { InfringerRow, LabelValue, Overview as OverviewData, UpcomingRow, YearAmounts } from "../types";

const AMOUNT_SERIES = [
  { key: "claimed" as const, label: "Claimed", color: "var(--series-1)" },
  { key: "awarded_or_settled" as const, label: "Awarded or settled", color: "var(--series-2)" },
  { key: "recovered" as const, label: "Recovered", color: "var(--series-3)" },
];

export default function Overview() {
  const { user, openAssistant } = useSession();
  const [country, setCountry] = useState("");
  const [mark, setMark] = useState("");
  useEffect(() => { setCountry(""); setMark(""); }, [user?.user_id]);
  const { data, error, loading } = useApi<OverviewData | null>(
    () => (user ? api.overview(user.user_id, country, mark) : Promise.resolve(null)),
    [user?.user_id, country, mark],
  );

  if (!user) return null;
  if (error) return <Card className="p-6 text-[14px] text-critical">The overview couldn't be loaded. Please try again in a moment.</Card>;
  if (!data) return <div className="py-20 text-center text-[14px] text-muted">Loading the portfolio…</div>;

  const k = data.kpis;
  const dim = loading;
  const filtered = Boolean(country || mark);
  const totalOpen = k.open_cases;

  return (
    <>
      <PageHeader
        eyebrow={`Overview · as of ${fmtDate(data.as_of)}`}
        title={`${greeting()}, ${user.full_name.split(" ")[0]}`}
        subtitle={<>Where every case you can see stands, what is due, and what enforcement recovers. You can see {user.access}.</>}
        actions={<Button variant="primary" icon={Sparkles} onClick={() => openAssistant(null, "What needs my attention this week?")}>What needs my attention?</Button>}
      />

      {/* one filter row, scoping everything below it */}
      <div className="mb-5 flex flex-wrap items-center gap-2 animate-fade-up">
        <Select label="Country" value={country} onChange={setCountry}
          options={[{ value: "", label: "All countries" }, ...data.filters.countries.map((c) => ({ value: c, label: c }))]} />
        <Select label="Mark" value={mark} onChange={setMark}
          options={[{ value: "", label: "All marks" }, ...data.filters.marks.map((m) => ({ value: m.id, label: m.name }))]} />
        {filtered && <Button variant="ghost" icon={RotateCcw} onClick={() => { setCountry(""); setMark(""); }}>Reset</Button>}
      </div>

      <div className={`grid gap-4 transition-opacity lg:grid-cols-4 ${dim ? "opacity-60" : ""}`}>
        <HeroFigure label="Open cases" value={fmtInt(k.open_cases)}
          sub={<>{fmtInt(k.cases)} cases in scope · {fmtInt(k.new_cases_30d)} opened in the last 30 days</>}>
          <div className="mb-1.5 text-[12px] text-muted">Cases opened per month</div>
          <Sparkline label="Cases opened per month" data={data.opened_by_month.map((m) => ({ period: m.month, value: m.value }))}
            formatPeriod={(p) => (p ? fmtDate(`${p}-01`, { month: "short", year: "numeric" }) : "")} />
          <div className="mt-4 flex items-center justify-between border-t border-line pt-3.5 text-[12.5px] text-ink-2">
            <span>Average age of open cases</span>
            <span className="font-semibold text-ink">{k.avg_days_open == null ? "–" : `${fmtInt(k.avg_days_open)} days`}</span>
          </div>
        </HeroFigure>
        <div className="grid gap-4 sm:grid-cols-2 lg:col-span-3 lg:grid-cols-3">
          <StatTile label="Hearings in the next 30 days" value={fmtInt(k.hearings_30d)} sub="Open cases with a listed hearing" />
          <StatTile label="Overdue actions" value={fmtInt(k.overdue_actions)} sub="Next action past its due date"
            status={k.overdue_actions > 0 ? { kind: "warning", text: "Needs attention" } : { kind: "good", text: "All on time" }} />
          <StatTile label="Cases closed this year" value={fmtInt(k.closed_ytd)} sub={`Since 1 January ${data.as_of.slice(0, 4)}`} />
          <StatTile label="Recovery rate" value={fmtPct(k.recovery_rate)} sub={`${fmtAED(k.recovered)} recovered of ${fmtAED(k.awarded + k.settled)} awarded or settled`} />
          <StatTile label="Win rate" value={fmtPct(k.win_rate)} sub={`${fmtInt(k.favourable)} favourable of ${fmtInt(k.decided)} decided cases`} />
          <StatTile label="Legal spend" value={fmtAED(k.legal_spend)} sub={k.spend_to_recovery == null ? "No recoveries yet" : `AED ${k.spend_to_recovery.toFixed(2)} spent per AED recovered`} />
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <ChartCard<LabelValue> title="Open cases by stage" subtitle="From intake to appeal" dim={dim}
          rows={data.open_by_stage} columns={[
            { key: "s", label: "Stage", render: (r) => r.label },
            { key: "v", label: "Open cases", render: (r) => fmtInt(r.value), align: "right" },
          ]}>
          <BarList data={data.open_by_stage} format={fmtInt} total={totalOpen} unit="open cases" />
        </ChartCard>
        <ChartCard<LabelValue> title="Open cases by country" subtitle={country ? "Filtered by the country above" : "Select a country to filter the page"} dim={dim}
          rows={data.open_by_country} columns={[
            { key: "c", label: "Country", render: (r) => r.label },
            { key: "v", label: "Open cases", render: (r) => fmtInt(r.value), align: "right" },
          ]}>
          {data.open_by_country.length
            ? <BarList data={data.open_by_country} format={fmtInt} total={totalOpen} unit="open cases"
                onSelect={(c) => setCountry(country === c ? "" : c)} />
            : <p className="text-[13px] text-muted">No open cases in this selection.</p>}
        </ChartCard>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <ChartCard<YearAmounts> className="lg:col-span-2" title="Claimed, awarded or settled, and recovered" subtitle="AED, by the year the case was opened" dim={dim}
          rows={data.amounts_by_year} columns={[
            { key: "y", label: "Year", render: (r) => r.year },
            ...AMOUNT_SERIES.map((s) => ({ key: s.key, label: s.label, render: (r: YearAmounts) => fmtAED(r[s.key], false), align: "right" as const })),
          ]}>
          <GroupedColumns data={data.amounts_by_year} xKey="year" series={AMOUNT_SERIES} format={(v) => fmtAED(v)} height={236} />
        </ChartCard>
        <ChartCard<LabelValue> title="Outcomes of closed cases" subtitle={`${fmtInt(data.outcomes.reduce((s, o) => s + o.value, 0))} closed cases`} dim={dim}
          rows={data.outcomes} columns={[
            { key: "o", label: "Outcome", render: (r) => r.label },
            { key: "v", label: "Cases", render: (r) => fmtInt(r.value), align: "right" },
          ]}>
          <div className="flex h-full flex-col justify-between gap-4">
            <SplitList data={data.outcomes} colors={OUTCOME_SLOTS} />
            <div className="rounded-xl bg-surface-2 p-3.5 text-[12.5px] leading-relaxed text-ink-2">
              <span className="font-semibold text-ink">{fmtPct(k.win_rate, 0)}</span> of decided cases ended favourably
              (won, partially won, settled or taken down); withdrawn cases are not counted as decided.
            </div>
          </div>
        </ChartCard>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card className="min-w-0 p-5 lg:col-span-2">
          <div className="mb-4 flex items-start justify-between gap-3">
            <div>
              <h3 className="text-[15px] font-semibold tracking-[-0.01em] text-ink">Upcoming hearings and due actions</h3>
              <p className="mt-0.5 text-[12.5px] text-muted">Overdue first, then the next 30 days</p>
            </div>
            <Link to="/cases" className="inline-flex items-center gap-1 text-[12.5px] font-medium text-accent-ink hover:underline">All cases <ArrowUpRight size={14} /></Link>
          </div>
          <UpcomingTable rows={data.upcoming} today={data.as_of} onAsk={(id) => openAssistant(id, "What happens next on this case, and what do I need to prepare?")} />
        </Card>
        <ChartCard<InfringerRow> title="Most frequent infringers" subtitle="Cases per party, with amounts recovered" dim={dim}
          rows={data.top_infringers} columns={[
            { key: "n", label: "Infringer", render: (r) => r.name },
            { key: "c", label: "Cases", render: (r) => fmtInt(r.cases), align: "right" },
            { key: "o", label: "Open", render: (r) => fmtInt(r.open), align: "right" },
            { key: "r", label: "Recovered", render: (r) => fmtAED(r.recovered), align: "right" },
          ]}>
          <InfringerList rows={data.top_infringers} />
        </ChartCard>
      </div>
    </>
  );
}

function InfringerList({ rows }: { rows: InfringerRow[] }) {
  const pager = usePagination(rows, 5, rows.map((r) => r.infringer_id).join());
  const max = Math.max(1, ...rows.map((r) => r.cases)); // one scale across pages
  return (
    <>
      <BarList stacked max={max}
        data={pager.slice.map((r) => ({ label: r.name, value: r.cases, hint: `${r.type} · ${r.country} · ${fmtAED(r.recovered)} recovered` }))}
        format={(v) => `${v} case${v === 1 ? "" : "s"}`} />
      <Pagination state={pager} noun="infringers" compact />
    </>
  );
}

function UpcomingTable({ rows, today, onAsk }: { rows: UpcomingRow[]; today: string; onAsk: (caseId: string) => void }) {
  const pager = usePagination(rows, 6, rows.map((r) => r.case_id).join());
  if (!rows.length) return <p className="text-[13px] text-muted">Nothing due in the next 30 days.</p>;
  return (
    <>
    <div className="-mx-2 overflow-x-auto">
      <table className="w-full min-w-[640px] text-[13px]">
        <thead>
          <tr className="text-left text-[12px] text-muted">
            <th className="px-2 pb-2 font-medium">Case</th>
            <th className="px-2 pb-2 font-medium">Next hearing</th>
            <th className="px-2 pb-2 font-medium">Next action</th>
            <th className="px-2 pb-2 font-medium">Counsel</th>
            <th className="px-2 pb-2" />
          </tr>
        </thead>
        <tbody>
          {pager.slice.map((r) => {
            const due = daysFrom(today, r.next_action_due);
            const hearing = daysFrom(today, r.next_hearing_date);
            return (
              <tr key={r.case_id} className="border-t border-line align-top">
                <td className="px-2 py-2.5">
                  <Link to={`/cases/${r.case_id}`} className="group block">
                    <span className="block text-[11.5px] font-medium text-muted">{r.case_id} · {r.country}</span>
                    <span className="block max-w-[260px] truncate font-medium text-ink group-hover:text-accent-ink">{r.title}</span>
                  </Link>
                </td>
                <td className="px-2 py-2.5 text-ink-2">
                  {r.next_hearing_date ? <>{fmtDate(r.next_hearing_date, { day: "numeric", month: "short" })}<span className="block text-[11.5px] text-muted">{relativeDays(hearing)}</span></> : "–"}
                </td>
                <td className="px-2 py-2.5">
                  <span className="block text-ink">{r.next_action ?? "–"}</span>
                  {r.next_action_due && (r.overdue
                    ? <span className="mt-1 inline-block"><StatusPill kind="warning">{relativeDays(due)}</StatusPill></span>
                    : <span className="block text-[11.5px] text-muted">due {fmtDate(r.next_action_due, { day: "numeric", month: "short" })} · {relativeDays(due)}</span>)}
                </td>
                <td className="px-2 py-2.5 text-ink-2">{r.lead_counsel}</td>
                <td className="px-2 py-2.5 text-right">
                  <button type="button" onClick={() => onAsk(r.case_id)} aria-label={`Ask Ferrero about ${r.case_id}`}
                    className="inline-flex items-center gap-1 rounded-lg border border-line px-2 py-1 text-[12px] text-ink-2 transition hover:border-accent hover:text-ink">
                    <Sparkles size={13} className="text-accent" /> Ask
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
    <Pagination state={pager} noun="hearings and actions" compact />
    </>
  );
}
