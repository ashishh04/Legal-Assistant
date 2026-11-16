import clsx from "clsx";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ChevronRight, ExternalLink, FileText, Lock, ScanLine, Sparkles } from "lucide-react";
import { ApiError, api } from "../api";
import { Pagination, usePagination } from "../components/Pagination";
import { Button, Card, Chip, EmptyState, SectionTitle, StatusPill } from "../components/ui";
import { useApi } from "../lib/hooks";
import { friendlyReason, pct } from "../lib/labels";
import { useSession } from "../session";
import type { DocumentView as Doc } from "../types";

function statusOf(d: Doc) {
  if (d.index_status === "Indexed") return <StatusPill kind="good">Searchable</StatusPill>;
  if (d.index_status === "Indexed (flagged)") return <StatusPill kind="warning">Searchable, to review</StatusPill>;
  if (d.index_status === "Pending" && (d.skip_reason ?? "").startsWith("Scanned")) return <StatusPill kind="scan">Text recognition pending</StatusPill>;
  if (d.index_status === "Pending") return <StatusPill kind="pending">Queued</StatusPill>;
  return <StatusPill kind="neutral">Not searchable</StatusPill>;
}

export default function DocumentView() {
  const { docId = "" } = useParams();
  const { user, openAssistant } = useSession();
  const navigate = useNavigate();
  const { data: d, error } = useApi<Doc | null>(
    () => (user ? api.document(user.user_id, docId) : Promise.resolve(null)), [user?.user_id, docId]);
  const [page, setPage] = useState(1);
  useEffect(() => { setPage(1); }, [docId]);
  const pager = usePagination(d?.sections ?? [], 6, docId);

  if (error) {
    const forbidden = error instanceof ApiError && error.status === 404;
    return (
      <div className="mx-auto max-w-xl pt-6">
        <EmptyState icon={Lock} title={forbidden ? `This document isn't available to ${user?.full_name}` : "Could not load this document"}
          action={<Button icon={ArrowLeft} onClick={() => navigate("/documents")}>Back to documents</Button>}>
          {forbidden ? "Documents follow their case's access rights. Switch to a user whose role covers this case." : "Please try again in a moment."}
        </EmptyState>
      </div>
    );
  }
  if (!d || !user) return <div className="py-20 text-center text-[14px] text-muted">Loading document…</div>;

  const scan = d.extraction === "ocr";
  const searchable = d.index_status.startsWith("Indexed");
  const rtl = d.language === "AR";
  const reviewAt = d.review_confidence ?? 0.9;
  const pageConfidence = d.page_confidence[page - 1] ?? null;
  const reason = d.skip_reason ? friendlyReason(d.skip_reason) : "";

  const text = (
    <Card className="flex min-w-0 flex-col p-5">
      <SectionTitle aside={searchable && <span className="text-[12px] text-muted">{d.sections.length} passages</span>}>
        {scan ? "Recognised text" : "Text"}
      </SectionTitle>
      {searchable ? (
        <>
          <div dir={rtl ? "rtl" : "auto"} className="space-y-5">
            {pager.slice.map((s) => (
              <section key={s.seq}>
                <h3 className="mb-1.5 text-[12px] font-semibold uppercase tracking-[0.08em] text-accent-ink" dir="auto">{s.section}</h3>
                <div className="space-y-2 text-[14px] leading-relaxed text-ink">
                  {s.blocks.map((b, i) => <p key={i} dir="auto">{b}</p>)}
                </div>
              </section>
            ))}
          </div>
          <Pagination state={pager} noun="passages" compact />
        </>
      ) : (
        <div className="grid flex-1 place-items-center rounded-xl border border-dashed border-line px-6 py-12 text-center text-[13.5px] text-ink-2">
          <div>
            <div className="mb-1 font-medium text-ink">{reason || "Not searchable yet"}</div>
            {d.index_status === "Pending" && scan
              ? "The scan is queued for text recognition; it becomes searchable as soon as its text has been read."
              : d.skip_reason?.startsWith("OCR confidence")
                ? "The recognised text was too uncertain to index. The scanned pages are shown for reading."
                : "Ferrero cannot search this file."}
          </div>
        </div>
      )}
    </Card>
  );

  return (
    <>
      <nav className="mb-4 flex items-center gap-1.5 text-[12.5px] text-muted animate-fade-up" aria-label="Breadcrumb">
        <Link to="/documents" className="hover:text-ink">Documents</Link>
        <ChevronRight size={13} />
        <Link to={`/cases/${d.case_id}`} className="hover:text-ink">{d.case_id}</Link>
        <ChevronRight size={13} />
        <span className="truncate text-ink-2" dir="auto">{d.file_name}</span>
      </nav>

      <Card className="mb-4 p-6 animate-fade-up">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex min-w-0 items-start gap-3">
            <span className="grid size-11 shrink-0 place-items-center rounded-2xl bg-accent-soft text-accent-ink">
              {scan ? <ScanLine size={20} strokeWidth={1.7} /> : <FileText size={20} strokeWidth={1.7} />}
            </span>
            <div className="min-w-0">
              <h1 className="text-[22px] font-semibold leading-tight tracking-[-0.02em] text-ink">{d.doc_type ?? "Document"}</h1>
              <div className="mt-0.5 truncate text-[13px] text-muted" dir="auto" title={d.library_path}>{d.file_name}</div>
              <div className="mt-2.5 flex flex-wrap items-center gap-2">
                <Link to={`/cases/${d.case_id}`}><Chip className="hover:border-accent hover:text-accent-ink">{d.case_id}</Chip></Link>
                {d.language && <Chip>{d.language === "AR" ? "Arabic" : "English"}</Chip>}
                {d.sensitivity && <Chip>{d.sensitivity}</Chip>}
                {scan && <Chip><ScanLine size={12} aria-hidden /> Scanned copy{d.ocr_confidence != null && ` · read with ${pct(d.ocr_confidence)} confidence`}</Chip>}
                {statusOf(d)}
              </div>
              {d.index_status === "Indexed (flagged)" && reason && <p className="mt-2 text-[12.5px] text-ink-2">{reason}.</p>}
            </div>
          </div>
          {searchable && (
            <Button variant="primary" icon={Sparkles}
              onClick={() => openAssistant(d.case_id, `What does the ${(d.doc_type ?? "document").toLowerCase()} (${d.file_name}) say?`)}>
              Ask Ferrero about this document
            </Button>
          )}
        </div>
      </Card>

      {scan && d.page_images > 0 ? (
        <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <Card className="min-w-0 p-5">
            <SectionTitle aside={
              <a href={api.pageImageUrl(user.user_id, d.doc_id, page)} target="_blank" rel="noreferrer"
                className="inline-flex items-center gap-1 text-[12px] text-muted hover:text-ink">Full size <ExternalLink size={12} /></a>}>
              Scanned page {page} of {d.page_images}
            </SectionTitle>
            {d.page_images > 1 && (
              <div className="mb-3 flex flex-wrap gap-1.5" role="tablist" aria-label="Pages">
                {Array.from({ length: d.page_images }, (_, i) => i + 1).map((n) => {
                  const c = d.page_confidence[n - 1];
                  const low = c != null && c < reviewAt;
                  return (
                    <button key={n} type="button" role="tab" aria-selected={n === page} onClick={() => setPage(n)}
                      className={clsx("inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-[12px] transition",
                        n === page ? "border-accent bg-accent-soft font-medium text-accent-ink" : "border-line text-ink-2 hover:bg-surface-2")}>
                      Page {n}
                      {c != null && <span className={clsx("tabular", low ? "text-[color:var(--warning)]" : "text-muted")}>{pct(c)}</span>}
                    </button>
                  );
                })}
              </div>
            )}
            <img key={page} src={api.pageImageUrl(user.user_id, d.doc_id, page)} alt={`Scanned page ${page} of ${d.file_name}`}
              className="w-full rounded-xl border border-line bg-white" loading="lazy" />
            {pageConfidence != null && (
              <p className="mt-2 text-[12px] text-muted">
                Text on this page read with {pct(pageConfidence)} confidence
                {pageConfidence < reviewAt ? " – check names, dates and amounts against the scan." : "."}
              </p>
            )}
          </Card>
          {text}
        </div>
      ) : text}
    </>
  );
}
