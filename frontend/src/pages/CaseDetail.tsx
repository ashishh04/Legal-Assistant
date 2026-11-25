import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  ArrowLeft, CalendarClock, ChartPie, ChevronRight, FileText, Gavel, Handshake, Lock, Pencil, ScanLine, Sparkles,
} from "lucide-react";
import { ApiError, api } from "../api";
import { AuditPanel } from "../components/case/AuditPanel";
import { CaseEditDialog } from "../components/case/CaseEditDialog";
import { BusinessDialog, CommercialCard } from "../components/case/CommercialPanel";
import { ComparisonPanel } from "../components/case/ComparisonPanel";
import { AssignDialog, CloseCaseDialog, WorkflowBar } from "../components/case/Workflow";
import { EvidencePanel } from "../components/case/EvidencePanel";
import { FollowUpsPanel } from "../components/case/FollowUpsPanel";
import { awaitingBusiness } from "../components/case/shared";
import { BarList } from "../components/charts";
import { Pagination, usePagination } from "../components/Pagination";
import { Button, Callout, Card, Chip, EmptyState, IconButton, Outcome, SectionTitle, StatStrip, StatTile, StatusPill, Tabs } from "../components/ui";
import { daysFrom, fmtAED, fmtDate, fmtInt, fmtMoney, relativeDays } from "../lib/format";
import { useApi } from "../lib/hooks";
import { friendlyReason, pct } from "../lib/labels";
import { useSession } from "../session";
import type { CaseDetail as Detail, CaseDocument, TimelineEvent } from "../types";

type Tab = "overview" | "evidence" | "follow-ups" | "comparison" | "audit";
const TAB_IDS: Tab[] = ["overview", "evidence", "follow-ups", "comparison", "audit"];

export default function CaseDetail() {
  const { caseId = "" } = useParams();
  const { user, meta, openAssistant } = useSession();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const tab: Tab = TAB_IDS.includes(params.get("tab") as Tab) ? (params.get("tab") as Tab) : "overview";
  const setTab = (t: Tab) => setParams(t === "overview" ? {} : { tab: t }, { replace: true });
  const { data: fetched, error, reload } = useApi<Detail | null>(
    () => (user ? api.case(caseId) : Promise.resolve(null)), [user?.user_id, caseId, meta?.demo_today]);
  const [c, setC] = useState<Detail | null>(null);
  useEffect(() => setC(fetched), [fetched]);
  const [editing, setEditing] = useState<"case" | "business" | "assign" | "close" | null>(null);
  const [newFollowUp, setNewFollowUp] = useState(false);
  const followUpStarted = useCallback(() => setNewFollowUp(false), []);
  const refresh = useCallback(() => reload(), [reload]);

  if (error) {
    const forbidden = error instanceof ApiError && error.status === 404;
    return (
      <div className="mx-auto max-w-xl pt-6">
        <EmptyState icon={Lock} title={forbidden ? `${caseId.toUpperCase()} isn't available to ${user?.full_name}` : "Could not load this case"}
          action={<Button icon={ArrowLeft} onClick={() => navigate("/cases")}>Back to cases</Button>}>
          {forbidden
            ? <>Cases are visible by country group. Check the case number, or ask Legal Operations if you need access.</>
            : "Please try again in a moment."}
        </EmptyState>
      </div>
    );
  }
  if (!c || c.case_id !== caseId.toUpperCase()) return <div className="py-24 text-center text-[14px] text-muted">Loading {caseId}…</div>;

  const today = meta?.demo_today ?? "";
  const due = daysFrom(today, c.next_action_due);
  const hearing = daysFrom(today, c.next_hearing_date);
  const local = (amount: number, aed: number) => ({
    value: fmtMoney(amount, c.currency),
    sub: c.currency === "AED" ? undefined : `≈ ${fmtAED(aed)}`,
  });
  const docs = Array.isArray(c.documents_on_file) ? c.documents_on_file : null;
  const invoiceRows = Object.entries(c.invoices.by_category_aed).sort((a, b) => b[1] - a[1]).map(([label, value]) => ({ label, value }));
  const ask = (prompt?: string) => openAssistant(c.case_id, prompt ?? null);
  const open = c.status === "Open";
  const waiting = awaitingBusiness(c) && open;

  return (
    <>
      <nav className="mb-4 flex items-center gap-1.5 text-[13px] text-muted animate-fade-up" aria-label="Breadcrumb">
        <Link to="/cases" className="font-medium transition-colors hover:text-ink">Cases</Link>
        <ChevronRight size={14} />
        <span className="font-medium text-ink-2">{c.case_id}</span>
      </nav>

      <Card className="mb-5 overflow-hidden animate-fade-up">
        <div className="grid grid-cols-1 gap-x-6 px-5 pb-6 pt-5 sm:px-7 lg:grid-cols-[minmax(0,1fr)_auto]">
          <div className="flex min-w-0 flex-wrap items-center gap-x-2 self-center text-[13px] text-muted">
            <span className="font-semibold text-accent-ink">{c.case_id}</span>
            <span aria-hidden>·</span>
            <span>{c.case_type}</span>
          </div>
          <div className="order-last mt-5 flex flex-wrap gap-2 lg:order-none lg:mt-0">
            {c.permissions.edit && <Button icon={Pencil} onClick={() => setEditing("case")}>Update case</Button>}
            {meta?.embedded_dashboards && !c.registered_in_app && (
              <Button icon={ChartPie} onClick={() => navigate(`/dashboards?d=DS-1&case=${encodeURIComponent(c.case_id)}`)}>
                Case dashboard
              </Button>
            )}
            <Button variant="primary" icon={Sparkles} onClick={() => ask()}>Ask Ferrero about this case</Button>
          </div>
          <h1 className="font-display mt-3 text-balance text-[28px] font-[540] leading-[1.1] text-ink sm:text-[34px] lg:col-span-2">{c.title}</h1>
          <p className="mt-2 text-[14.5px] text-ink-2 lg:col-span-2">{c.court_name ? `${c.court_name}, ` : ""}{c.country}</p>
          <div className="mt-4 flex flex-wrap items-center gap-1.5 lg:col-span-2">
              <Chip tone={open ? "accent" : "neutral"}>
                <span aria-hidden className={open ? "size-1.5 rounded-full bg-accent" : "size-1.5 rounded-full bg-muted"} />{c.status}
              </Chip>
              {c.stage !== c.status && <Chip tone="outline">{c.stage}</Chip>}
              {c.status === "Closed" && <Chip tone="outline"><Outcome outcome={c.outcome} /></Chip>}
              {c.priority && <Chip tone={c.priority === "High" ? "warning" : "outline"}>{c.priority} priority</Chip>}
              {c.risk_rating && <Chip tone={c.risk_rating === "High" ? "critical" : "outline"}>{c.risk_rating} risk</Chip>}
              {c.business_priority && <Chip tone="outline">Business priority {c.business_priority}</Chip>}
              {waiting && <Chip tone="warning"><Handshake size={12} /> Consult business first</Chip>}
            <Chip tone="outline"><Lock size={11} /> {c.sensitivity}</Chip>
          </div>
        </div>
        <dl className="grid grid-cols-2 gap-x-8 gap-y-5 border-t border-line bg-surface-2 px-5 py-5 text-[13.5px] sm:px-7 lg:grid-cols-4">
          <Fact label="Mark" value={c.mark_name} />
          <Fact label="Infringer" value={c.infringer_name} sub={c.infringer_type} />
          <Fact label="Lead counsel" value={c.lead_counsel} sub={c.external_firm || "No external firm"} />
          <Fact label="Source" value={c.source_channel} />
          <Fact label="Opened" value={fmtDate(c.opened_date)} sub={open ? `${fmtInt(daysFrom(c.opened_date, today))} days open` : undefined} />
          <Fact label={c.status === "Closed" ? "Closed" : "Last activity"} value={fmtDate(c.status === "Closed" ? c.closed_date : c.last_action_date)}
            sub={c.status === "Closed" ? `after ${fmtInt(c.days_open)} days` : undefined} />
          <Fact label="Currency" value={c.currency} sub={c.currency === "AED" ? undefined : "AED at reference exchange rates"} />
          <Fact label="File language" value={c.language} />
        </dl>
      </Card>

      {waiting && (
        <div role="status" className="mb-5 animate-fade-up">
          <Callout tone="warning" icon={Handshake} className="items-center p-4"
            title={c.consultation_status === "Hold enforcement" ? "The business has asked to hold enforcement" : "Consult the business before any enforcement step"}
            action={c.permissions.edit && <Button icon={Handshake} onClick={() => setEditing("business")}>Record consultation</Button>}>
            {c.commercial_relationship && c.commercial_relationship !== "None known" ? `${c.infringer_name} is a ${c.commercial_relationship.toLowerCase()}. ` : ""}
            Consultation: {(c.consultation_status ?? "Not started").toLowerCase()}{c.consultation_contact ? ` with ${c.consultation_contact}` : ""}.
            A notice, filing or court step needs business sign-off first; going ahead without it needs a recorded reason.
          </Callout>
        </div>
      )}

      <WorkflowBar c={c} onAssign={() => setEditing("assign")} onClose={() => setEditing("close")}
        onFollowUp={() => { setTab("follow-ups"); setNewFollowUp(true); }} />

      <Tabs<Tab> label="Case sections" value={tab} onChange={setTab} className="mb-6" tabs={[
        { value: "overview", label: "Overview" },
        { value: "evidence", label: "Evidence & documents", count: c.counts.evidence },
        { value: "follow-ups", label: "Follow-ups", count: c.counts.follow_ups_open },
        { value: "comparison", label: "Trademark comparison" },
        { value: "audit", label: "Audit trail", count: c.counts.audit },
      ]} />

      {tab === "evidence" && <EvidencePanel c={c} onChanged={refresh} />}
      {tab === "follow-ups" && <FollowUpsPanel c={c} onChanged={refresh} startNew={newFollowUp} onStarted={followUpStarted} />}
      {tab === "comparison" && <ComparisonPanel c={c} onChanged={refresh} onAddPhoto={() => setTab("evidence")} />}
      {tab === "audit" && <AuditPanel c={c} />}
      {tab === "overview" && <>
        <StatStrip className="mb-5 sm:grid-cols-2 xl:grid-cols-4">
          <StatTile label="Claimed" {...local(c.claim_amount_local, c.claim_amount_aed)} />
          <StatTile label="Awarded" {...local(c.awarded_amount_local, c.awarded_amount_aed)} />
          <StatTile label="Settled" {...local(c.settlement_amount_local, c.settlement_amount_aed)} />
          <StatTile label="Recovered" {...local(c.recovered_amount_local, c.recovered_amount_aed)} />
        </StatStrip>

        {open && (c.next_action || c.next_hearing_date) && (
          <div className="mb-5 flex flex-wrap items-center gap-x-10 gap-y-4 rounded-xl border border-accent-line bg-accent-soft px-6 py-4">
            <div className="flex min-w-0 items-center gap-3.5">
              <span className="grid size-10 shrink-0 place-items-center rounded-full bg-surface text-accent-ink ring-1 ring-accent-line"><CalendarClock size={18} /></span>
              <div className="min-w-0">
                <div className="text-[12.5px] font-medium text-accent-ink">Next action</div>
                <div className="text-[15px] font-semibold text-ink">{c.next_action ?? "–"}</div>
              </div>
            </div>
            {c.next_action_due && (
              <div>
                <div className="text-[12.5px] text-ink-2">Due</div>
                <div className="flex flex-wrap items-center gap-2 text-[14px] font-medium text-ink">
                  <span className="tabular">{fmtDate(c.next_action_due)}</span>
                  {due != null && due < 0 ? <StatusPill kind="critical">{relativeDays(due)}</StatusPill> : <span className="text-[13px] font-normal text-ink-2">{relativeDays(due)}</span>}
                </div>
              </div>
            )}
            {c.next_hearing_date && (
              <div>
                <div className="text-[12.5px] text-ink-2">Next hearing</div>
                <div className="text-[14px] font-medium text-ink"><span className="tabular">{fmtDate(c.next_hearing_date)}</span> <span className="text-[13px] font-normal text-ink-2">{relativeDays(hearing)}</span></div>
              </div>
            )}
            <Button className="ms-auto" icon={Sparkles} onClick={() => ask("What do I need to prepare for the next step on this case?")}>Help me prepare</Button>
          </div>
        )}

        <div className="grid items-start gap-5 lg:grid-cols-5">
          <Card className="p-6 lg:col-span-2">
            <SectionTitle aside={<span className="tabular text-[12.5px] text-muted">{c.timeline.length} events</span>}>Timeline</SectionTitle>
            <Timeline events={c.timeline} caseId={c.case_id} />
          </Card>

          <div className="flex min-w-0 flex-col gap-5 lg:col-span-3">
            <CommercialCard c={c} onEdit={c.permissions.edit ? () => setEditing("business") : undefined} />
            <Card className="p-6">
              <SectionTitle aside={docs && <span className="tabular text-[12.5px] text-muted">{docs.filter((d) => d.text_searchable).length} of {docs.length} searchable by Ferrero</span>}>
                Documents on file
              </SectionTitle>
              {docs ? (
                <DocList docs={docs} caseId={c.case_id}
                  onAsk={(d) => ask(`What does the ${(d.doc_type ?? "document").toLowerCase()}${d.file_name ? ` (${d.file_name})` : ""} say?`)} />
              ) : (
                <p className="flex items-center gap-2.5 text-[13.5px] text-ink-2"><Lock size={15} className="text-muted" /> Case documents are not available for your role.</p>
              )}
            </Card>
            <Card className="p-6">
              <SectionTitle aside={<span className="tabular text-[12.5px] text-muted">{c.invoices.count} invoices · {fmtAED(c.invoices.total_aed)}</span>}>External counsel spend</SectionTitle>
              {invoiceRows.length
                ? <BarList data={invoiceRows} format={(v) => fmtAED(v)} total={c.invoices.total_aed} unit="spend" />
                : <p className="text-[13.5px] text-muted">No invoices for this case.</p>}
            </Card>
          </div>
        </div>
      </>}

      <CaseEditDialog c={c} open={editing === "case"} onClose={() => setEditing(null)} onSaved={setC} />
      <BusinessDialog c={c} open={editing === "business"} onClose={() => setEditing(null)} onSaved={setC} />
      <AssignDialog c={c} open={editing === "assign"} onClose={() => setEditing(null)} onSaved={setC} />
      <CloseCaseDialog c={c} open={editing === "close"} onClose={() => setEditing(null)} onSaved={setC} />
    </>
  );
}

function Timeline({ events, caseId }: { events: TimelineEvent[]; caseId: string }) {
  const newestFirst = [...events].reverse();
  const pager = usePagination(newestFirst, 6, caseId);
  if (!events.length) return <p className="text-[13.5px] leading-relaxed text-muted">No events on the tracker yet. Changes made here are in the audit trail.</p>;
  return (
    <>
      <ol className="relative ms-[5px] border-s border-line-strong">
        {pager.slice.map((e, i) => {
          const latest = pager.page === 1 && i === 0;
          return (
            <li key={`${e.event_date}-${e.event_type}-${i}`} className="relative pb-5 ps-6 last:pb-0">
              <span aria-hidden className={`absolute -start-[5.5px] top-[5px] size-[10px] rounded-full ring-4 ring-surface ${latest ? "bg-accent" : "bg-line-strong"}`} />
              <div className="text-[14px] font-medium leading-snug text-ink">{e.event_type}</div>
              <div className="mt-0.5 text-[12.5px] text-muted">
                <span className="tabular">{fmtDate(e.event_date)}</span>{e.external_fees_aed ? ` · ${fmtAED(e.external_fees_aed)} external fees` : ""}
              </div>
            </li>
          );
        })}
      </ol>
      <Pagination state={pager} noun="events" compact />
    </>
  );
}

function DocList({ docs, caseId, onAsk }: { docs: CaseDocument[]; caseId: string; onAsk: (d: CaseDocument) => void }) {
  const pager = usePagination(docs, 5, caseId);
  return (
    <>
      <ul className="-my-1 divide-y divide-line">
        {pager.slice.map((d, i) => <DocRow key={d.doc_id ?? d.file_name ?? i} doc={d} onAsk={() => onAsk(d)} />)}
      </ul>
      <Pagination state={pager} noun="documents" compact />
    </>
  );
}

function Fact({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-[12.5px] text-muted">{label}</dt>
      <dd className="mt-1 truncate font-medium text-ink" title={value}>{value}</dd>
      {sub && <dd className="mt-0.5 truncate text-[12.5px] text-muted" title={sub}>{sub}</dd>}
    </div>
  );
}

function DocRow({ doc, onAsk }: { doc: CaseDocument; onAsk: () => void }) {
  const note = doc.sync_note ?? "";
  const status = doc.text_searchable
    ? doc.review_note ? <StatusPill kind="warning">{friendlyReason(doc.review_note)}</StatusPill>
      : doc.scanned_copy ? <StatusPill kind="good">Read from scan</StatusPill>
      : <StatusPill kind="good">Searchable</StatusPill>
    : note.startsWith("Password") ? <StatusPill kind="locked">Password-protected</StatusPill>
    : note.startsWith("Scanned PDF – waiting") ? <StatusPill kind="scan">Text recognition pending</StatusPill>
    : note.startsWith("OCR confidence") ? <StatusPill kind="scan">Scan too faint</StatusPill>
    : note ? <StatusPill kind="neutral">{friendlyReason(note)}</StatusPill>
    : <StatusPill kind="neutral">Not in the library</StatusPill>;
  const Icon = doc.scanned_copy ? ScanLine : doc.doc_type === "Judgment" ? Gavel : FileText;
  const name = doc.file_name ?? doc.title;
  return (
    <li className="flex items-center gap-3 py-3">
      <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-surface-3 text-ink-2"><Icon size={16} strokeWidth={1.7} /></span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 text-[13.5px]">
          <span className="font-medium text-ink">{doc.doc_type ?? "Document"}</span>
          {doc.language && <Chip tone="outline" className="px-1.5 py-0 text-[10.5px] font-semibold">{doc.language}</Chip>}
          {doc.doc_date && <span className="tabular text-[12.5px] text-muted">{fmtDate(doc.doc_date)}</span>}
          {doc.scanned_copy && doc.ocr_confidence != null && doc.text_searchable &&
            <span className="text-[12.5px] text-muted">scan · {pct(doc.ocr_confidence)}</span>}
        </div>
        {doc.synced_doc_id
          ? <Link to={`/documents/${encodeURIComponent(doc.synced_doc_id)}`} dir="auto" className="mt-0.5 block truncate text-[12.5px] text-muted underline-offset-2 hover:text-accent-ink hover:underline" title={name}>{name}</Link>
          : <div className="mt-0.5 truncate text-[12.5px] text-muted" dir="auto" title={name}>{name}</div>}
      </div>
      {status}
      {doc.text_searchable && (
        <IconButton icon={Sparkles} size={32} onClick={onAsk} aria-label="Ask Ferrero about this document" title="Ask Ferrero about this document"
          className="text-muted hover:bg-accent-soft hover:text-accent-ink" />
      )}
    </li>
  );
}
