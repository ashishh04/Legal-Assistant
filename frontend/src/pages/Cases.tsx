import clsx from "clsx";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ArrowDown, ArrowUp, ClipboardPlus, Handshake, RotateCcw, Search } from "lucide-react";
import { api } from "../api";
import { RegisterCaseDialog } from "../components/case/RegisterCaseDialog";
import { Pagination, usePagination } from "../components/Pagination";
import { Button, Card, Outcome, PageHeader, Select, StatusPill } from "../components/ui";
import { daysFrom, fmtAED, fmtDate, relativeDays } from "../lib/format";
import { useApi } from "../lib/hooks";
import { useSession } from "../session";
import type { CaseRow } from "../types";

type SortKey = "opened_date" | "next" | "claim_amount_aed" | "case_id";

const nextDate = (r: CaseRow) => (r.status === "Open" ? (r.next_hearing_date ?? r.next_action_due ?? "") : "");

export default function Cases() {
  const { user, meta } = useSession();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [q, setQ] = useState(params.get("q") ?? "");
  const [status, setStatus] = useState("");
  const [stage, setStage] = useState(params.get("stage") ?? "");
  const [owner, setOwner] = useState(params.get("owner") === "me" ? "me" : "");
  const [registering, setRegistering] = useState(false);
  const [country, setCountry] = useState("");
  const [mark, setMark] = useState("");
  const [business, setBusiness] = useState("");
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "opened_date", dir: -1 });
  useEffect(() => { setQ(params.get("q") ?? ""); }, [params]);
  const { data, error, loading } = useApi<CaseRow[]>(() => (user ? api.cases() : Promise.resolve([])), [user?.user_id]);

  const rows = data ?? [];
  const options = useMemo(() => ({
    stages: [...new Set(rows.map((r) => r.stage))],
    countries: [...new Set(rows.map((r) => r.country))].sort(),
    marks: [...new Map(rows.map((r) => [r.mark_id, r.mark_name])).entries()].sort((a, b) => a[1].localeCompare(b[1])),
  }), [rows]);

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const list = rows.filter((r) =>
      (!status || r.status === status) && (!stage || r.stage === stage) && (!country || r.country === country) && (!mark || r.mark_id === mark) &&
      (!owner || r.lead_counsel_id === user?.user_id) &&
      (!business || (business === "consult" ? Boolean(r.consultation_required) && r.consultation_status !== "Cleared to proceed"
        : business === "unassessed" ? r.business_priority == null && r.consultation_required == null : r.business_priority === business)) &&
      (!needle || [r.case_id, r.title, r.infringer_name, r.mark_name, r.court_name, r.case_type, r.lead_counsel].some((v) => v?.toLowerCase().includes(needle))));
    const val = (r: CaseRow) => (sort.key === "next" ? nextDate(r) || "9999" : sort.key === "claim_amount_aed" ? r.claim_amount_aed : r[sort.key]);
    return [...list].sort((a, b) => (val(a) > val(b) ? 1 : val(a) < val(b) ? -1 : 0) * sort.dir);
  }, [rows, q, status, stage, country, mark, business, owner, sort, user?.user_id]);

  const pager = usePagination(shown, 15, [q, status, stage, country, mark, business, owner, sort.key, sort.dir, user?.user_id].join("|"));
  const filtered = Boolean(q || status || stage || country || mark || business || owner);
  const reset = () => { setQ(""); setStatus(""); setStage(""); setCountry(""); setMark(""); setBusiness(""); setOwner(""); setParams({}); };
  const toggleSort = (key: SortKey) => setSort((s) => ({ key, dir: s.key === key ? (s.dir === 1 ? -1 : 1) : key === "next" ? 1 : -1 }));
  const today = meta?.demo_today ?? "";
  const open = rows.filter((r) => r.status === "Open").length;

  return (
    <>
      <PageHeader eyebrow="Case tracker" title="Cases"
        subtitle={user ? <>{rows.length} cases visible to {user.full_name} · {open} open. Select a case to work on it.</> : null}
        actions={user?.can_edit && <Button variant="primary" icon={ClipboardPlus} onClick={() => setRegistering(true)}>Register a case</Button>} />

      <div className="mb-4 flex flex-wrap items-center gap-2 animate-fade-up">
        <label className="flex min-w-[240px] flex-1 items-center gap-2 rounded-xl border border-line-strong bg-surface px-3 py-1.5 text-[13px] focus-within:border-accent sm:max-w-xs">
          <Search size={15} className="text-muted" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Case number, party, mark, court…"
            className="min-w-0 flex-1 bg-transparent py-0.5 text-ink outline-none placeholder:text-muted" aria-label="Filter cases" />
        </label>
        <Select label="Status" value={status} onChange={setStatus} options={[{ value: "", label: "All" }, { value: "Open", label: "Open" }, { value: "Closed", label: "Closed" }]} />
        <Select label="Owner" value={owner} onChange={setOwner} options={[{ value: "", label: "Everyone" }, { value: "me", label: "My cases" }]} />
        <Select label="Stage" value={stage} onChange={setStage} options={[{ value: "", label: "All" }, ...options.stages.map((s) => ({ value: s, label: s }))]} />
        <Select label="Country" value={country} onChange={setCountry} options={[{ value: "", label: "All" }, ...options.countries.map((c) => ({ value: c, label: c }))]} />
        <Select label="Mark" value={mark} onChange={setMark} options={[{ value: "", label: "All" }, ...options.marks.map(([id, name]) => ({ value: id, label: name }))]} />
        <Select label="Business" value={business} onChange={setBusiness} options={[
          { value: "", label: "All" }, { value: "consult", label: "Consult business first" }, { value: "High", label: "Business priority High" },
          { value: "Medium", label: "Business priority Medium" }, { value: "Low", label: "Business priority Low" }, { value: "unassessed", label: "Not assessed" },
        ]} />
        {filtered && <Button variant="ghost" icon={RotateCcw} onClick={reset}>Reset</Button>}
      </div>

      {error && <Card className="p-6 text-[14px] text-critical">The case list couldn't be loaded. Please try again in a moment.</Card>}
      <Card className={clsx("overflow-hidden transition-opacity", loading && data && "opacity-60")}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[920px] text-[13.5px]">
            <thead className="border-b border-line bg-surface-2 text-left text-[12px] text-muted">
              <tr>
                <Th label="Case" onClick={() => toggleSort("case_id")} sort={sort.key === "case_id" ? sort.dir : 0} />
                <th className="px-4 py-3 font-medium">Country</th>
                <th className="px-4 py-3 font-medium">Stage · outcome</th>
                <Th label="Next" onClick={() => toggleSort("next")} sort={sort.key === "next" ? sort.dir : 0} />
                <th className="px-4 py-3 font-medium">Counsel</th>
                <Th label="Opened" onClick={() => toggleSort("opened_date")} sort={sort.key === "opened_date" ? sort.dir : 0} />
                <Th label="Claimed" align="right" onClick={() => toggleSort("claim_amount_aed")} sort={sort.key === "claim_amount_aed" ? sort.dir : 0} />
              </tr>
            </thead>
            <tbody>
              {pager.slice.map((r) => {
                const due = daysFrom(today, r.next_action_due);
                return (
                  <tr key={r.case_id} onClick={() => navigate(`/cases/${r.case_id}`)}
                    onKeyDown={(e) => { if (e.key === "Enter") navigate(`/cases/${r.case_id}`); }} tabIndex={0}
                    className="cursor-pointer border-b border-line align-top transition last:border-0 hover:bg-surface-2 focus-visible:bg-surface-2">
                    <td className="px-4 py-3">
                      <span className="block text-[11.5px] font-medium text-muted">{r.case_id} · {r.case_type}</span>
                      <span className="block max-w-[340px] truncate font-medium text-ink">{r.title}</span>
                      {(r.business_priority || r.consultation_required) && (
                        <span className="mt-1 flex flex-wrap gap-1.5">
                          {r.business_priority && <span className="rounded-md border border-line px-1.5 text-[11px] font-medium text-ink-2">Business {r.business_priority}</span>}
                          {Boolean(r.consultation_required) && r.consultation_status !== "Cleared to proceed" && r.status === "Open" && (
                            <span className="inline-flex items-center gap-1 rounded-md border border-warning/60 bg-warning/10 px-1.5 text-[11px] font-medium text-ink">
                              <Handshake size={11} /> Consult business first
                            </span>
                          )}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-ink-2">{r.country}</td>
                    <td className="px-4 py-3">
                      {r.status === "Open"
                        ? <span className="text-ink">{r.stage}</span>
                        : <Outcome outcome={r.outcome} />}
                      <span className="block text-[11.5px] text-muted">{r.status}{r.priority ? ` · ${r.priority} priority` : ""}</span>
                    </td>
                    <td className="px-4 py-3">
                      {r.status === "Open" ? (
                        <>
                          <span className="block text-ink">{r.next_action ?? "–"}</span>
                          {r.overdue
                            ? <span className="mt-1 inline-block"><StatusPill kind="warning">{relativeDays(due)}</StatusPill></span>
                            : <span className="block text-[11.5px] text-muted">
                                {r.next_hearing_date ? `Hearing ${fmtDate(r.next_hearing_date, { day: "numeric", month: "short" })}` : r.next_action_due ? `Due ${fmtDate(r.next_action_due, { day: "numeric", month: "short" })}` : ""}
                              </span>}
                        </>
                      ) : <span className="text-[12.5px] text-muted">Closed {fmtDate(r.closed_date)}</span>}
                    </td>
                    <td className="px-4 py-3 text-ink-2">{r.lead_counsel}</td>
                    <td className="tabular whitespace-nowrap px-4 py-3 text-ink-2">{fmtDate(r.opened_date)}</td>
                    <td className="tabular whitespace-nowrap px-4 py-3 text-right text-ink">{r.claim_amount_aed ? fmtAED(r.claim_amount_aed) : "–"}</td>
                  </tr>
                );
              })}
              {!shown.length && (
                <tr><td colSpan={7} className="px-4 py-14 text-center text-[13.5px] text-muted">{data ? "No cases match these filters." : "Loading cases…"}</td></tr>
              )}
            </tbody>
          </table>
        </div>
        <Pagination state={pager} noun={shown.length === rows.length ? "cases" : `matching cases (${rows.length} in total)`} sizes={[10, 15, 25, 50]} />
      </Card>
      <RegisterCaseDialog open={registering} onClose={() => setRegistering(false)} />
    </>
  );
}

function Th({ label, onClick, sort, align }: { label: string; onClick: () => void; sort: 0 | 1 | -1; align?: "right" }) {
  const Icon = sort === 1 ? ArrowUp : ArrowDown;
  return (
    <th className={clsx("px-4 py-3 font-medium", align === "right" && "text-right")} aria-sort={sort === 0 ? "none" : sort === 1 ? "ascending" : "descending"}>
      <button type="button" onClick={onClick} className={clsx("inline-flex items-center gap-1 hover:text-ink", sort !== 0 && "text-ink")}>
        {label}{sort !== 0 && <Icon size={12} />}
      </button>
    </th>
  );
}
