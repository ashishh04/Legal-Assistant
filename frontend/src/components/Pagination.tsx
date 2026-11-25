import clsx from "clsx";
import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

export interface PageState<T> {
  page: number;
  pages: number;
  size: number;
  total: number;
  from: number;
  to: number;
  slice: T[];
  setPage: (p: number) => void;
  setSize: (s: number) => void;
}

/** Client-side paging. `resetKey` returns to page 1 whenever the filters behind `items` change. */
export function usePagination<T>(items: T[], initialSize = 10, resetKey: unknown = null): PageState<T> {
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(initialSize);
  useEffect(() => { setPage(1); }, [resetKey, size]);
  const pages = Math.max(1, Math.ceil(items.length / size));
  const current = Math.min(page, pages);
  const start = (current - 1) * size;
  return {
    page: current, pages, size, total: items.length,
    from: items.length ? start + 1 : 0, to: Math.min(start + size, items.length),
    slice: items.slice(start, start + size), setPage, setSize,
  };
}

function pageList(current: number, total: number): (number | "…")[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const set = new Set([1, total, current - 1, current, current + 1]);
  const pages = [...set].filter((p) => p >= 1 && p <= total).sort((a, b) => a - b);
  const out: (number | "…")[] = [];
  pages.forEach((p, i) => {
    if (i > 0 && p - pages[i - 1] > 1) out.push("…");
    out.push(p);
  });
  return out;
}

export function Pagination<T>({ state, noun = "items", sizes, compact = false, className }:
  { state: PageState<T>; noun?: string; sizes?: number[]; compact?: boolean; className?: string }) {
  const { page, pages, total, from, to, size, setPage, setSize } = state;
  if (total === 0) return null;
  if (pages <= 1 && !sizes) return null;
  const btn = "grid h-8 min-w-8 place-items-center rounded-md px-2 text-[12.5px] transition-colors disabled:cursor-not-allowed disabled:opacity-35";

  if (compact) {
    if (pages <= 1) return null;
    return (
      <nav aria-label={`${noun} pages`} className={clsx("mt-3 flex items-center justify-between gap-3 border-t border-line pt-3 text-[12.5px] text-muted", className)}>
        <span className="tabular">{from}–{to} of {total}</span>
        <span className="flex items-center gap-1">
          <button type="button" className={clsx(btn, "border border-line-strong bg-surface text-ink-2 hover:bg-surface-2 hover:text-ink")} disabled={page === 1}
            onClick={() => setPage(page - 1)} aria-label="Previous page"><ChevronLeft size={15} /></button>
          <span className="tabular px-2 text-ink-2">{page} / {pages}</span>
          <button type="button" className={clsx(btn, "border border-line-strong bg-surface text-ink-2 hover:bg-surface-2 hover:text-ink")} disabled={page === pages}
            onClick={() => setPage(page + 1)} aria-label="Next page"><ChevronRight size={15} /></button>
        </span>
      </nav>
    );
  }

  return (
    <nav aria-label={`${noun} pages`}
      className={clsx("flex flex-wrap items-center justify-between gap-3 border-t border-line bg-surface-2 px-5 py-3 text-[12.5px] text-muted", className)}>
      <span className="tabular">Showing <span className="font-medium text-ink">{from}–{to}</span> of <span className="font-medium text-ink">{total}</span> {noun}</span>
      <div className="flex flex-wrap items-center gap-4">
        {sizes && (
          <label className="flex items-center gap-2">
            Rows per page
            <select value={size} onChange={(e) => setSize(Number(e.target.value))}
              className="select-caret h-8 cursor-pointer rounded-md border border-line-strong bg-surface ps-2.5 pe-7 font-medium text-ink outline-none focus:border-accent">
              {sizes.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
        )}
        {pages > 1 && (
          <span className="flex items-center gap-0.5">
            <button type="button" className={clsx(btn, "text-ink-2 hover:bg-surface-3 hover:text-ink")} disabled={page === 1}
              onClick={() => setPage(page - 1)} aria-label="Previous page"><ChevronLeft size={16} /></button>
            {pageList(page, pages).map((p, i) => p === "…"
              ? <span key={`gap-${i}`} className="px-1 text-muted">…</span>
              : (
                <button key={p} type="button" onClick={() => setPage(p)} aria-current={p === page ? "page" : undefined}
                  className={clsx(btn, "tabular font-medium", p === page ? "bg-primary text-primary-ink" : "text-ink-2 hover:bg-surface-3 hover:text-ink")}>
                  {p}
                </button>
              ))}
            <button type="button" className={clsx(btn, "text-ink-2 hover:bg-surface-3 hover:text-ink")} disabled={page === pages}
              onClick={() => setPage(page + 1)} aria-label="Next page"><ChevronRight size={16} /></button>
          </span>
        )}
      </div>
    </nav>
  );
}
