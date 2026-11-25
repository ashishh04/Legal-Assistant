import clsx from "clsx";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ChevronRight, ExternalLink, FileText, Lock, ScanLine, Sparkles, TriangleAlert } from "lucide-react";
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
    () => (user ? api.document(docId) : Promise.resolve(null)), [user?.user_id, docId]);
  const [page, setPage] = useState(1);
  useEffect(() => { setPage(1); }, [docId]);
  const pager = usePagination(d?.sections ?? [], 6, docId);

  if (error) {
    const forbidden = error instanceof ApiError && error.status === 404;
    return (
      <div className="mx-auto max-w-xl pt-6">
        <EmptyState icon={Lock} title={forbidden ? `This document isn't available to ${user?.full_name}` : "Could not load this document"}
          action={<Button icon={ArrowLeft} onClick={() => navigate("/documents")}>Back to documents</Button>}>
          {forbidden ? "Documents follow their case's access rights. Ask Legal Operations if you need access." : "Please try again in a moment."}
        </EmptyState>
      </div>
    );
  }
  if (!d || !user) return <div className="py-24 text-center text-[14px] text-muted">Loading document…</div>;

  const scan = d.extraction === "ocr";
  const searchable = d.index_status.startsWith("Indexed");
  const rtl = d.language === "AR";
  const reviewAt = d.review_confidence ?? 0.9;
  const pageConfidence = d.page_confidence[page - 1] ?? null;
  const reason = d.skip_reason ? friendlyReason(d.skip_reason) : "";

  const text = (
    <Card className="flex min-w-0 flex-col p-6">
      <SectionTitle aside={searchable && <span className="tabular text-[12.5px] text-muted">{d.sections.length} passages</span>}>
        {scan ? "Recognised text" : "Text"}
      </SectionTitle>
      {searchable ? (
        <>
          <div dir={rtl ? "rtl" : "ltr"}>
            <div className="max-w-[72ch] space-y-6">
              {pager.slice.map((s) => (
                <section key={s.seq}>
                  <h3 className="mb-2 text-start text-[13.5px] font-semibold text-accent-ink">{s.section}</h3>
                  <div className="space-y-2.5 text-[14.5px] leading-[1.7] text-ink">
                    {s.blocks.map((b, i) => <p key={i} dir="auto">{b}</p>)}
                  </div>
                </section>
              ))}
            </div>
          </div>
          <Pagination state={pager} noun="passages" compact />
        </>
      ) : (
        <div className="grid flex-1 place-items-center rounded-lg border border-dashed border-line-strong bg-surface-2 px-6 py-12 text-center text-[13.5px] leading-relaxed text-ink-2">
          <div className="max-w-md">
            <div className="mb-1 text-[14.5px] font-semibold text-ink">{reason || "Not searchable yet"}</div>
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
      <nav className="mb-4 flex items-center gap-1.5 text-[13px] text-muted animate-fade-up" aria-label="Breadcrumb">
        <Link to="/documents" className="font-medium transition-colors hover:text-ink">Documents</Link>
        <ChevronRight size={14} />
        <Link to={`/cases/${d.case_id}`} className="font-medium transition-colors hover:text-ink">{d.case_id}</Link>
        <ChevronRight size={14} />
        <span className="truncate font-medium text-ink-2" dir="auto">{d.file_name}</span>
      </nav>

      <Card className="mb-5 px-7 py-6 animate-fade-up">
        <div className="flex items-start gap-4">
          <span className="mt-1 hidden size-11 shrink-0 place-items-center rounded-full border border-accent-line bg-accent-soft text-accent-ink sm:grid">
            {scan ? <ScanLine size={20} strokeWidth={1.7} /> : <FileText size={20} strokeWidth={1.7} />}
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-3">
              <div className="min-w-0">
                <h1 className="font-display text-[28px] font-[540] leading-tight text-ink">{d.doc_type ?? "Document"}</h1>
                <div className="mt-1 truncate text-start text-[13.5px] text-muted" dir="auto" title={d.library_path}>{d.file_name}</div>
              </div>
              {searchable && (
                <Button variant="primary" icon={Sparkles}
                  onClick={() => openAssistant(d.case_id, `What does the ${(d.doc_type ?? "document").toLowerCase()} (${d.file_name}) say?`)}>
                  Ask Ferrero about this document
                </Button>
              )}
            </div>
            <div className="mt-3.5 flex flex-wrap items-center gap-1.5">
                <Link to={`/cases/${d.case_id}`}><Chip tone="accent" className="hover:bg-accent-line">{d.case_id}</Chip></Link>
                {d.language && <Chip tone="outline">{d.language === "AR" ? "Arabic" : "English"}</Chip>}
                {d.sensitivity && <Chip tone="outline">{d.sensitivity}</Chip>}
                {scan && <Chip tone="outline"><ScanLine size={12} aria-hidden /> Scanned copy{d.ocr_confidence != null && ` · read with ${pct(d.ocr_confidence)} confidence`}</Chip>}
                {statusOf(d)}
              </div>
            {d.index_status === "Indexed (flagged)" && reason && <p className="mt-2.5 text-[13px] text-ink-2">{reason}.</p>}
          </div>
        </div>
      </Card>

      {scan && d.page_images > 0 ? (
        <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <Card className="min-w-0 p-6">
            <SectionTitle aside={
              <a href={api.pageImageUrl(d.doc_id, page)} target="_blank" rel="noreferrer"
                className="inline-flex items-center gap-1 text-[12.5px] font-medium text-accent-ink underline-offset-2 hover:underline">Full size <ExternalLink size={12} /></a>}>
              Scanned page {page} of {d.page_images}
            </SectionTitle>
            {d.page_images > 1 && (
              <div className="mb-4 flex flex-wrap gap-1.5" role="tablist" aria-label="Pages">
                {Array.from({ length: d.page_images }, (_, i) => i + 1).map((n) => {
                  const c = d.page_confidence[n - 1];
                  const low = c != null && c < reviewAt;
                  return (
                    <button key={n} type="button" role="tab" aria-selected={n === page} onClick={() => setPage(n)}
                      className={clsx("inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[12.5px] font-medium transition-colors",
                        n === page ? "bg-primary text-primary-ink" : "bg-surface-3 text-ink-2 hover:text-ink")}>
                      Page {n}
                      {c != null && <span className={clsx("tabular font-normal", n === page ? "opacity-75" : "text-muted")}>{pct(c)}</span>}
                      {low && <TriangleAlert size={12} className={n === page ? "opacity-90" : "text-warning"} aria-label="Read with low confidence" />}
                    </button>
                  );
                })}
              </div>
            )}
            <img key={page} src={api.pageImageUrl(d.doc_id, page)} alt={`Scanned page ${page} of ${d.file_name}`}
              className="w-full rounded-lg border border-line-strong bg-white" loading="lazy" />
            {pageConfidence != null && (
              <p className="mt-3 text-[12.5px] leading-relaxed text-muted">
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
