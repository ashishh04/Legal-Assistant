import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { FileText, Lock, RotateCcw, ScanLine, Search } from "lucide-react";
import { api } from "../api";
import { Pagination, usePagination } from "../components/Pagination";
import { Button, Card, Chip, EmptyState, PageHeader, SearchField, Select, StatStrip, StatTile, StatusPill } from "../components/ui";
import { fmtInt } from "../lib/format";
import { useApi } from "../lib/hooks";
import { friendlyReason, pct } from "../lib/labels";
import { useSession } from "../session";
import type { SyncDoc, SyncStatus } from "../types";

type Kind = "searchable" | "flagged" | "scan" | "faint" | "locked" | "pending" | "unmatched" | "other";

function kindOf(d: SyncDoc): Kind {
  const r = d.skip_reason ?? "";
  if (d.index_status === "Indexed") return "searchable";
  if (d.index_status === "Indexed (flagged)") return "flagged";
  if (d.index_status === "Pending") return r.startsWith("Scanned") ? "scan" : "pending";
  if (r.startsWith("OCR confidence")) return "faint";
  if (r.startsWith("Password")) return "locked";
  if (!d.case_id) return "unmatched";
  return "other";
}

const KIND_LABEL: Record<Kind, string> = {
  searchable: "Searchable", flagged: "Searchable, to review", scan: "Text recognition pending", faint: "Scan too faint",
  locked: "Password-protected", pending: "Queued", unmatched: "Not linked", other: "Not indexed",
};

function KindPill({ kind }: { kind: Kind }) {
  const map = {
    searchable: "good", flagged: "warning", scan: "scan", faint: "neutral", locked: "locked", pending: "pending",
    unmatched: "neutral", other: "neutral",
  } as const;
  return <StatusPill kind={map[kind]}>{KIND_LABEL[kind]}</StatusPill>;
}

/** The folder a file sits in: its library path without the file name (the name is the line above it). */
function folderOf(d: SyncDoc): string {
  const cut = d.library_path.lastIndexOf("/");
  return cut > 0 ? d.library_path.slice(0, cut) : d.library_path;
}

export default function Documents() {
  const { user } = useSession();
  const [q, setQ] = useState("");
  const [kind, setKind] = useState("");
  const { data, error } = useApi<SyncStatus | null>(() => (user ? api.sync() : Promise.resolve(null)), [user?.user_id]);

  const docs = data?.documents ?? [];
  const counts = useMemo(() => {
    const c: Record<Kind, number> = { searchable: 0, flagged: 0, scan: 0, faint: 0, locked: 0, pending: 0, unmatched: 0, other: 0 };
    for (const d of docs) c[kindOf(d)]++;
    return c;
  }, [docs]);
  const scans = useMemo(() => {
    const all = docs.filter((d) => d.extraction === "ocr");
    const read = all.filter((d) => d.index_status.startsWith("Indexed"));
    const scores = read.map((d) => d.ocr_confidence).filter((v): v is number => v != null);
    return { all: all.length, read: read.length, mean: scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null };
  }, [docs]);
  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return docs.filter((d) => (!kind || kindOf(d) === kind) &&
      (!needle || [d.file_name, d.case_id, d.doc_type ?? "", d.library_path].some((v) => v.toLowerCase().includes(needle))));
  }, [docs, q, kind]);
  const pager = usePagination(shown, 15, [q, kind, user?.user_id].join("|"));

  if (!user) return null;
  if (error) return <Card className="p-6 text-[14px] text-critical-ink">The document library couldn't be loaded. Please try again.</Card>;
  if (data && !data.visible) {
    return (
      <>
        <PageHeader title="Documents" />
        <div className="mx-auto max-w-xl"><EmptyState icon={Lock} title="Case documents aren't available for your role">
          {user.full_name} ({user.entra_group}) can see case data but not the case documents themselves.
        </EmptyState></div>
      </>
    );
  }
  const passages = docs.reduce((s, d) => s + (d.passages || 0), 0);

  return (
    <>
      <PageHeader title="Documents"
        subtitle="Files from the case libraries, each linked to its case and made searchable for Ferrero with that case's access rights. Scanned copies are read page by page with text recognition. Only files you may open are listed." />

      <StatStrip className="mb-6 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile label="Searchable by Ferrero" value={fmtInt(counts.searchable + counts.flagged)} sub={`${fmtInt(passages)} passages indexed`} />
        <StatTile label="Read from scans" value={<>{fmtInt(scans.read)}<span className="text-[17px] font-medium text-muted"> of {fmtInt(scans.all)}</span></>}
          sub={counts.scan ? `${fmtInt(counts.scan)} awaiting text recognition`
            : scans.mean != null ? `Average recognition confidence ${pct(scans.mean)}` : "No scanned copies"} />
        <StatTile label="Password-protected" value={fmtInt(counts.locked)} sub="Listed, but never opened" />
        <StatTile label="Not linked to a case" value={fmtInt(counts.unmatched + counts.other)} sub="Held back until their case is confirmed" />
      </StatStrip>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <SearchField icon={Search} value={q} onChange={setQ} placeholder="File, case number, type…" label="Filter documents" className="flex-1 sm:max-w-[300px]" />
        <Select label="Status" value={kind} onChange={setKind}
          options={[{ value: "", label: "All" }, ...(Object.keys(KIND_LABEL) as Kind[]).filter((k) => counts[k]).map((k) => ({ value: k, label: `${KIND_LABEL[k]} (${counts[k]})` }))]} />
        {(q || kind) && <Button variant="ghost" icon={RotateCcw} onClick={() => { setQ(""); setKind(""); }}>Reset</Button>}
      </div>

      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] table-fixed text-[13.5px]">
            <colgroup>
              <col /><col className="w-[128px]" /><col className="w-[232px]" /><col className="w-[218px]" /><col className="w-[96px]" />
            </colgroup>
            <thead className="border-b border-line bg-surface-2 text-left text-[12.5px] text-muted">
              <tr>
                <th className="py-3 pe-3 ps-5 font-medium">File</th>
                <th className="px-3 py-3 font-medium">Case</th>
                <th className="px-3 py-3 font-medium">Type</th>
                <th className="px-3 py-3 font-medium">Status</th>
                <th className="py-3 pe-5 ps-3 text-right font-medium">Passages</th>
              </tr>
            </thead>
            <tbody>
              {pager.slice.map((d) => {
                const k = kindOf(d);
                const scan = d.extraction === "ocr";
                const Icon = scan ? ScanLine : FileText;
                return (
                  <tr key={d.doc_id} className="border-b border-line align-top transition-colors last:border-0 hover:bg-surface-2">
                    <td className="py-3 pe-3 ps-5">
                      <span className="flex min-w-0 items-start gap-3">
                        <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg bg-surface-3 text-ink-2"><Icon size={15} strokeWidth={1.7} /></span>
                        <span className="min-w-0 flex-1">
                          {d.case_id
                            ? <Link to={`/documents/${encodeURIComponent(d.doc_id)}`} dir="auto" className="block truncate text-left font-medium text-ink underline-offset-2 hover:text-accent-ink hover:underline" title={d.file_name}>{d.file_name}</Link>
                            : <span dir="auto" className="block truncate text-left font-medium text-ink" title={d.file_name}>{d.file_name}</span>}
                          <span className="mt-0.5 flex min-w-0 items-center gap-1.5 text-[12px] text-muted">
                            {scan && (
                              <span className="shrink-0 font-medium text-ink-2" title="Scanned copy: text recognised from the page images">
                                Scan{d.ocr_confidence != null && ` · ${pct(d.ocr_confidence)}`}
                              </span>
                            )}
                            {scan && <span aria-hidden>·</span>}
                            <span className="truncate text-left" dir="auto" title={d.library_path}>{folderOf(d)}</span>
                          </span>
                        </span>
                      </span>
                    </td>
                    <td className="px-3 py-3">{d.case_id
                      ? <Link to={`/cases/${d.case_id}`} className="whitespace-nowrap font-medium text-accent-ink underline-offset-2 hover:underline">{d.case_id}</Link>
                      : <span className="text-muted">–</span>}</td>
                    <td className="px-3 py-3 text-ink-2">
                      <span className="flex items-center gap-2">
                        <span className="truncate" title={d.doc_type ?? undefined}>{d.doc_type ?? "–"}</span>
                        {d.language && <Chip tone="outline" className="shrink-0 px-1.5 py-0 text-[10.5px] font-semibold">{d.language}</Chip>}
                      </span>
                    </td>
                    <td className="px-3 py-3">
                      <KindPill kind={k} />
                      {k !== "searchable" && d.skip_reason && friendlyReason(d.skip_reason) !== KIND_LABEL[k] &&
                        <span className="mt-1 block text-[12px] leading-snug text-muted">{friendlyReason(d.skip_reason)}</span>}
                    </td>
                    <td className="tabular py-3 pe-5 ps-3 text-right text-ink-2">{d.passages || <span className="text-muted">–</span>}</td>
                  </tr>
                );
              })}
              {!shown.length && <tr><td colSpan={5} className="px-4 py-16 text-center text-[13.5px] text-muted">{data ? "No documents match." : "Loading…"}</td></tr>}
            </tbody>
          </table>
        </div>
        <Pagination state={pager} noun="documents" sizes={[10, 15, 25, 50]} />
      </Card>
    </>
  );
}
