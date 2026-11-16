import clsx from "clsx";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowLeft, ChartPie, ExternalLink, RotateCcw, X } from "lucide-react";
import { api } from "../api";
import { SupersetFrame } from "../components/SupersetFrame";
import { Button, Card, EmptyState, PageHeader } from "../components/ui";
import { useApi } from "../lib/hooks";
import { useSession } from "../session";
import type { DashboardsInfo, EmbeddedDashboardInfo } from "../types";

const PLANNED = [
  { id: "D1", name: "Legal Case Overview", audience: "IP counsel, litigation counsel and paralegals", question: "What needs my attention this week, and where does every case stand?" },
  { id: "D2", name: "Leadership Command View", audience: "Head of Legal, Regional General Counsel and Procurement", question: "Is enforcement paying for itself, and where are we exposed?" },
  { id: "D3", name: "Infringement Intake and Triage", audience: "Legal operations and brand protection", question: "Are we keeping up with incoming reports, and which channels generate real cases?" },
  { id: "D4", name: "Infringer and Enforcement Outcomes", audience: "IP counsel, brand protection and external counsel reviews", question: "Which infringers and routes deserve the next budget?" },
];

/** The dashboard server only lets the origins in its frame-ancestors list frame it (null: no limit). */
function blockedByServer(info: DashboardsInfo): { message: string; alternatives: string[] } | null {
  const origin = window.location.origin;
  const ancestors = info.frame_ancestors;
  if (!ancestors || ancestors.includes("*") || ancestors.includes(origin)) return null;
  const alternatives = ancestors.filter((a) => /^https?:\/\/[^*]+$/.test(a));
  return {
    message: alternatives.length
      ? `The dashboards can't be shown inside Ferrero at ${origin}. They can be shown when Ferrero is opened at ${alternatives.join(" or ")}.`
      : `The dashboards can't be shown inside Ferrero at ${origin}.`,
    alternatives,
  };
}

/** A dashboard whose embed settings name other sites. */
function domainProblem(dash: EmbeddedDashboardInfo): string | null {
  const origin = window.location.origin;
  return dash.allowed_domains.length && !dash.allowed_domains.includes(origin)
    ? `This dashboard can only be shown from ${dash.allowed_domains.join(", ")}.`
    : null;
}

function label(d: EmbeddedDashboardInfo) {
  return d.code ? `${d.code} · ${d.title}` : d.title;
}

export default function Dashboards() {
  const { user } = useSession();
  const userId = user?.user_id ?? "";
  const { data, error, loading, reload } = useApi(() => api.dashboards(userId), [userId]);

  if (!user) return null;
  if (loading && !data) return <><PageHeader eyebrow="Analytics" title="Dashboards" /><Card className="h-[420px] animate-pulse" /></>;
  if (error || !data) {
    return (
      <>
        <PageHeader eyebrow="Analytics" title="Dashboards" />
        <EmptyState icon={ChartPie} title="Dashboards are unavailable" action={<Button icon={RotateCcw} onClick={reload}>Try again</Button>}>
          The dashboard list couldn't be loaded. Please try again in a moment.
        </EmptyState>
      </>
    );
  }
  if (data.mode === "embedded") return <EmbeddedDashboards info={data} userId={userId} reload={reload} />;
  if (data.mode === "links") return <LinkedDashboards dashboards={data.dashboards as { title: string; url: string }[]} />;
  return <PlannedDashboards />;
}

function EmbeddedDashboards({ info, userId, reload }: { info: DashboardsInfo; userId: string; reload: () => void }) {
  const { theme } = useSession();
  const [params, setParams] = useSearchParams();
  const dashboards = info.dashboards as EmbeddedDashboardInfo[];

  if (info.error || !dashboards.length) {
    return (
      <>
        <PageHeader eyebrow="Analytics" title="Dashboards" />
        <EmptyState icon={ChartPie} title={info.error ? "Dashboards are unavailable" : "No dashboards yet"}
          action={<Button icon={RotateCcw} onClick={reload}>Try again</Button>}>
          {info.error ?? "No dashboards are published for Ferrero yet."}
        </EmptyState>
      </>
    );
  }

  const wanted = params.get("d");
  const current = dashboards.find((d) => d.code === wanted || d.uuid === wanted) ?? dashboards[0];
  const caseId = current.code === "DS-1" ? params.get("case")?.toUpperCase() ?? null : null;
  const blocked = blockedByServer(info);
  const problem = domainProblem(current);

  const select = (d: EmbeddedDashboardInfo) => {
    const next = new URLSearchParams(params);
    next.set("d", d.code ?? d.uuid);
    if (d.code !== "DS-1") next.delete("case");
    setParams(next, { replace: true });
  };
  const clearCase = () => {
    const next = new URLSearchParams(params);
    next.delete("case");
    setParams(next, { replace: true });
  };

  return (
    <>
      <PageHeader eyebrow="Analytics" title="Dashboards"
        subtitle="Portfolio dashboards for each audience, on the same case data and access rights as the rest of Ferrero."
        actions={<a href={current.url} target="_blank" rel="noreferrer"
          className="inline-flex items-center gap-2 rounded-xl border border-line-strong bg-surface px-3.5 py-2 text-[13.5px] font-medium text-ink hover:bg-surface-2">
          <ExternalLink size={15} /> Open in a new tab</a>} />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex flex-wrap gap-1 rounded-xl border border-line bg-surface p-1" role="tablist" aria-label="Dashboards">
          {dashboards.map((d) => (
            <button key={d.uuid} type="button" role="tab" aria-selected={d.uuid === current.uuid} onClick={() => select(d)}
              className={clsx("rounded-lg px-3 py-1.5 text-[13px] transition",
                d.uuid === current.uuid ? "bg-primary text-primary-ink" : "text-ink-2 hover:bg-surface-2")}>
              {label(d)}
            </button>
          ))}
        </div>
        {caseId && (
          <span className="inline-flex items-center gap-2 rounded-full border border-line bg-surface-2 py-1 pe-1.5 ps-3 text-[12.5px] text-ink-2">
            <Link to={`/cases/${caseId}`} className="inline-flex items-center gap-1 font-medium text-ink hover:underline">
              <ArrowLeft size={13} /> {caseId}
            </Link>
            <span>only</span>
            <button type="button" onClick={clearCase} aria-label="Show all cases"
              className="grid size-5 place-items-center rounded-full hover:bg-surface"><X size={12} /></button>
          </span>
        )}
      </div>
      {blocked ? (
        <EmptyState icon={ChartPie} title="Open Ferrero from an address that can show the dashboards"
          action={blocked.alternatives[0] && (
            <a href={`${blocked.alternatives[0]}${window.location.pathname}${window.location.search}`}
              className="inline-flex items-center gap-2 rounded-xl bg-primary px-3.5 py-2 text-[13.5px] font-medium text-primary-ink hover:opacity-90">
              <ExternalLink size={15} /> Open at {blocked.alternatives[0]}
            </a>
          )}>
          {blocked.message}
        </EmptyState>
      ) : (
        <>
          {problem && (
            <div role="status" className="mb-3 rounded-xl border border-line bg-surface-2 px-4 py-2.5 text-[13px] text-ink-2">{problem}</div>
          )}
          <Card className="overflow-hidden">
            <SupersetFrame uuid={current.uuid} domain={info.superset_url ?? ""} userId={userId} caseId={caseId}
              title={label(current)} theme={theme} blockedHint={problem} />
          </Card>
        </>
      )}
    </>
  );
}

function LinkedDashboards({ dashboards }: { dashboards: { title: string; url: string }[] }) {
  const [active, setActive] = useState(0);
  const current = dashboards[Math.min(active, dashboards.length - 1)];
  return (
    <>
      <PageHeader eyebrow="Analytics" title="Dashboards"
        actions={<a href={current.url} target="_blank" rel="noreferrer"
          className="inline-flex items-center gap-2 rounded-xl border border-line-strong bg-surface px-3.5 py-2 text-[13.5px] font-medium text-ink hover:bg-surface-2">
          <ExternalLink size={15} /> Open in a new tab</a>} />
      <div className="mb-4 flex flex-wrap gap-1 rounded-xl border border-line bg-surface p-1">
        {dashboards.map((d, i) => (
          <button key={d.url} type="button" onClick={() => setActive(i)} aria-pressed={i === active}
            className={clsx("rounded-lg px-3 py-1.5 text-[13px] transition", i === active ? "bg-primary text-primary-ink" : "text-ink-2 hover:bg-surface-2")}>
            {d.title}
          </button>
        ))}
      </div>
      <Card className="overflow-hidden">
        <iframe key={current.url} title={current.title} src={current.url} className="h-[calc(100dvh-15rem)] min-h-[560px] w-full border-0 bg-surface" />
      </Card>
    </>
  );
}

function PlannedDashboards() {
  return (
    <>
      <PageHeader eyebrow="Analytics" title="Dashboards"
        subtitle="Portfolio dashboards for each audience, built on the same case data and access rights as the rest of Ferrero." />
      <div className="grid gap-4 md:grid-cols-2">
        {PLANNED.map((d) => (
          <Card key={d.id} className="flex flex-col p-5">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <span className="grid size-9 place-items-center rounded-xl bg-accent-soft text-accent-ink"><ChartPie size={17} /></span>
                <div>
                  <div className="text-[11px] font-semibold tracking-[0.08em] text-accent-ink">{d.id}</div>
                  <h3 className="text-[15px] font-semibold text-ink">{d.name}</h3>
                </div>
              </div>
              <span className="rounded-full border border-line bg-surface-2 px-2.5 py-0.5 text-[11.5px] font-medium text-ink-2">Coming soon</span>
            </div>
            <p className="mt-4 text-[13.5px] italic leading-relaxed text-ink-2">“{d.question}”</p>
            <p className="mt-auto pt-3 text-[12px] text-muted">For {d.audience}</p>
          </Card>
        ))}
      </div>
    </>
  );
}
