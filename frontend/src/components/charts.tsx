/* Charts drawn to the dataviz specs: thin marks (<= 24px), 4px rounded data-ends square at the baseline,
   solid hairline grid, 2px surface gaps between touching marks, selective direct labels, a legend for >= 2 series,
   per-mark hover/focus tooltips (values lead, labels follow), and a table view for every chart. */
import clsx from "clsx";
import { useState, type ReactNode } from "react";
import { ChartColumnBig, Table2 } from "lucide-react";
import { useWidth } from "../lib/hooks";
import { Pagination, usePagination } from "./Pagination";
import { Card } from "./ui";

// ---------- chart card with the table-view twin ----------
export interface Column<T> { key: string; label: string; render: (row: T) => ReactNode; align?: "left" | "right" }

export function ChartCard<T>({ title, subtitle, children, rows, columns, className, dim }:
  { title: string; subtitle?: string; children: ReactNode; rows: T[]; columns: Column<T>[]; className?: string; dim?: boolean }) {
  const [view, setView] = useState<"chart" | "table">("chart");
  return (
    <Card className={clsx("flex min-w-0 flex-col p-5", className)}>
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-[15px] font-semibold tracking-[-0.01em] text-ink">{title}</h3>
          {subtitle && <p className="mt-0.5 text-[12.5px] text-muted">{subtitle}</p>}
        </div>
        <div className="flex shrink-0 rounded-lg border border-line bg-surface-2 p-0.5" role="group" aria-label={`${title}: view`}>
          {(["chart", "table"] as const).map((v) => {
            const IconCmp = v === "chart" ? ChartColumnBig : Table2;
            return (
              <button key={v} type="button" aria-pressed={view === v} aria-label={v === "chart" ? "Chart view" : "Table view"}
                onClick={() => setView(v)}
                className={clsx("grid size-7 place-items-center rounded-md transition",
                  view === v ? "bg-surface text-ink shadow-sm" : "text-muted hover:text-ink")}>
                <IconCmp size={15} strokeWidth={1.8} />
              </button>
            );
          })}
        </div>
      </div>
      <div className={clsx("min-w-0 flex-1 transition-opacity", dim && "opacity-50")}>
        {view === "chart" ? children : <DataTable rows={rows} columns={columns} />}
      </div>
    </Card>
  );
}

export function DataTable<T>({ rows, columns }: { rows: T[]; columns: Column<T>[] }) {
  const pager = usePagination(rows, 8, rows.length);
  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="border-b border-line text-left text-muted">
              {columns.map((c) => <th key={c.key} className={clsx("py-2 pe-3 font-medium", c.align === "right" && "text-right")}>{c.label}</th>)}
            </tr>
          </thead>
          <tbody>
            {pager.slice.map((r, i) => (
              <tr key={i} className="border-b border-line last:border-0">
                {columns.map((c) => <td key={c.key} className={clsx("py-2 pe-3 text-ink", c.align === "right" && "tabular text-right")}>{c.render(r)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pagination state={pager} noun="rows" compact />
    </div>
  );
}

// ---------- tooltip ----------
interface TipRow { color?: string; label: string; value: string }
interface Tip { x: number; y: number; title?: string; rows: TipRow[] }

function Tooltip({ tip }: { tip: Tip | null }) {
  if (!tip) return null;
  return (
    <div role="tooltip" className="pointer-events-none absolute z-20 min-w-36 -translate-x-1/2 -translate-y-full rounded-xl border border-line bg-surface px-3 py-2 text-[12.5px] shadow-card"
      style={{ left: tip.x, top: tip.y - 10 }}>
      {tip.title && <div className="mb-1 text-muted">{tip.title}</div>}
      {tip.rows.map((r) => (
        <div key={r.label} className="flex items-center gap-2 py-0.5">
          {r.color && <span className="h-0.5 w-3 rounded-full" style={{ background: r.color }} aria-hidden />}
          <span className="font-semibold text-ink">{r.value}</span>
          <span className="text-ink-2">{r.label}</span>
        </div>
      ))}
    </div>
  );
}

// ---------- legend (rect swatches mirror bar marks) ----------
export function Legend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1.5 text-[12.5px] text-ink-2">
      {items.map((it) => (
        <li key={it.label} className="inline-flex items-center gap-1.5">
          <span className="size-2.5 rounded-[3px]" style={{ background: it.color }} aria-hidden />
          {it.label}
        </li>
      ))}
    </ul>
  );
}

// ---------- ranked horizontal bars (one series, one hue, values at the tips) ----------
export function BarList({ data, format = (v) => String(v), color = "var(--series-1)", max, total, onSelect, unit, stacked }:
  { data: { label: string; value: number; hint?: string }[]; format?: (v: number) => string; color?: string; max?: number;
    total?: number; onSelect?: (label: string) => void; unit?: string; stacked?: boolean }) {
  const top = max ?? Math.max(1, ...data.map((d) => d.value));
  if (stacked) {
    // Narrow cards: the name sits above its bar, so long names are never truncated to a stub.
    return (
      <ul className="flex flex-col gap-3.5">
        {data.map((d) => (
          <li key={d.label} tabIndex={0} aria-label={`${d.label}: ${format(d.value)}${d.hint ? `, ${d.hint}` : ""}`}
            className="group rounded-md outline-offset-4">
            <div className="flex items-baseline justify-between gap-3">
              <span className="min-w-0 truncate text-[13px] font-medium text-ink" title={d.label}>{d.label}</span>
              <span className="tabular shrink-0 text-[12.5px] font-medium text-ink">{format(d.value)}</span>
            </div>
            {d.hint && <div className="truncate text-[11.5px] text-muted" title={d.hint}>{d.hint}</div>}
            <div className="mt-1.5 border-s border-[var(--viz-axis)]">
              <div className="h-2 rounded-e-[4px] transition-[filter] group-hover:brightness-110"
                style={{ width: `${Math.max(d.value > 0 ? 1 : 0, (d.value / top) * 100)}%`, background: color }} />
            </div>
          </li>
        ))}
      </ul>
    );
  }
  return (
    <ul className="flex flex-col gap-2.5">
      {data.map((d) => {
        const share = total ? ` · ${Math.round((d.value / total) * 100)}% of ${unit ?? "total"}` : "";
        const Row = onSelect ? "button" : "div";
        return (
          <li key={d.label}>
            <Row
              {...(onSelect ? { type: "button" as const, onClick: () => onSelect(d.label) } : { tabIndex: 0 })}
              aria-label={`${d.label}: ${format(d.value)}${share}`}
              title={`${d.label}: ${format(d.value)}${share}${d.hint ? ` · ${d.hint}` : ""}`}
              className="group grid w-full grid-cols-[minmax(84px,34%)_1fr] items-center gap-3 rounded-md text-left outline-offset-4">
              <span className="truncate text-[13px] text-ink-2 group-hover:text-ink">{d.label}</span>
              <span className="flex min-w-0 items-center gap-2 border-s border-[var(--viz-axis)]">
                <span className="h-2.5 rounded-e-[4px] transition-[filter] group-hover:brightness-110"
                  style={{ width: `${Math.max(d.value > 0 ? 0.8 : 0, (d.value / top) * 82)}%`, background: color }} />
                <span className="tabular shrink-0 text-[12.5px] font-medium text-ink">{format(d.value)}</span>
              </span>
            </Row>
          </li>
        );
      })}
    </ul>
  );
}

// ---------- grouped columns (categorical series, one axis) ----------
function niceStep(max: number, ticks = 4) {
  const raw = max / ticks;
  const mag = 10 ** Math.floor(Math.log10(raw || 1));
  const norm = raw / mag;
  return (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 2.5 ? 2.5 : norm <= 5 ? 5 : 10) * mag;
}

function roundedTop(x: number, y: number, w: number, h: number, r: number) {
  const rr = Math.min(r, w / 2, h);
  return `M${x},${y + h}V${y + rr}Q${x},${y} ${x + rr},${y}H${x + w - rr}Q${x + w},${y} ${x + w},${y + rr}V${y + h}Z`;
}

export function GroupedColumns<T extends object>({ data, xKey, series, format, height = 220 }:
  { data: T[]; xKey: keyof T & string; series: { key: keyof T & string; label: string; color: string }[];
    format: (v: number) => string; height?: number }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [tip, setTip] = useState<Tip | null>(null);
  const [active, setActive] = useState<number | null>(null);
  const m = { top: 12, right: 8, bottom: 26, left: 52 };
  const plotW = Math.max(0, width - m.left - m.right);
  const plotH = height - m.top - m.bottom;
  const maxV = Math.max(1, ...data.flatMap((d) => series.map((s) => Number(d[s.key]) || 0)));
  const step = niceStep(maxV);
  const top = Math.ceil(maxV / step) * step;
  const ticks = Array.from({ length: Math.round(top / step) + 1 }, (_, i) => i * step);
  const band = data.length ? plotW / data.length : 0;
  const gap = 2;
  const barW = Math.max(4, Math.min(24, (band * 0.62 - gap * (series.length - 1)) / series.length));
  const groupW = barW * series.length + gap * (series.length - 1);
  const y = (v: number) => m.top + plotH - (v / top) * plotH;

  const show = (i: number, cx: number) => {
    setActive(i);
    setTip({ x: cx, y: m.top + 4, title: String(data[i][xKey]),
      rows: series.map((s) => ({ color: s.color, label: s.label, value: format(Number(data[i][s.key]) || 0) })) });
  };
  const hide = () => { setActive(null); setTip(null); };

  return (
    <div className="flex flex-col gap-3">
      <Legend items={series.map((s) => ({ label: s.label, color: s.color }))} />
      <div ref={ref} className="relative" style={{ height }}>
        {width > 0 && (
          <svg width={width} height={height} role="img" aria-label={`Grouped columns by ${xKey}`} className="block overflow-visible">
            {ticks.map((t) => (
              <g key={t}>
                <line x1={m.left} x2={width - m.right} y1={y(t)} y2={y(t)} stroke={t === 0 ? "var(--viz-axis)" : "var(--viz-grid)"} strokeWidth={1} shapeRendering="crispEdges" />
                <text x={m.left - 8} y={y(t)} dy="0.32em" textAnchor="end" className="tabular" fontSize={11} fill="var(--muted)">{format(t)}</text>
              </g>
            ))}
            {data.map((d, i) => {
              const gx = m.left + band * i + (band - groupW) / 2;
              const cx = m.left + band * i + band / 2;
              return (
                <g key={String(d[xKey])} opacity={active === null || active === i ? 1 : 0.55} style={{ transition: "opacity .15s" }}>
                  {series.map((s, j) => {
                    const v = Number(d[s.key]) || 0;
                    const h = Math.max(0, y(0) - y(v));
                    return <path key={s.key} d={roundedTop(gx + j * (barW + gap), y(v), barW, h, 4)} fill={s.color} />;
                  })}
                  <text x={cx} y={height - 8} textAnchor="middle" fontSize={11.5} fill="var(--ink-2)">{String(d[xKey])}</text>
                  <rect x={m.left + band * i} y={m.top} width={band} height={plotH} fill="transparent" tabIndex={0}
                    aria-label={`${d[xKey]}: ${series.map((s) => `${s.label} ${format(Number(d[s.key]) || 0)}`).join(", ")}`}
                    onPointerMove={() => show(i, cx)} onPointerLeave={hide} onFocus={() => show(i, cx)} onBlur={hide}
                    style={{ outline: "none", cursor: "default" }} />
                </g>
              );
            })}
          </svg>
        )}
        <Tooltip tip={tip} />
      </div>
    </div>
  );
}

// ---------- thin segmented bar + the figures beside it (one whole, read with its numbers) ----------
export function SplitList({ data, colors, unit = "cases" }:
  { data: { label: string; value: number }[]; colors: Record<string, string>; unit?: string }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [tip, setTip] = useState<Tip | null>(null);
  const total = data.reduce((s, d) => s + d.value, 0);
  const parts = data.filter((d) => d.value > 0);
  const usable = Math.max(0, width - 2 * (parts.length - 1));
  const pct = (v: number) => (total ? `${Math.round((v / total) * 100)}%` : "–");
  let offset = 0;
  return (
    <div className="flex flex-col gap-3">
      <div ref={ref} className="relative">
        <div className="flex h-2 gap-[2px] overflow-hidden rounded-full" role="img"
          aria-label={`Split of ${total} ${unit}: ${parts.map((p) => `${p.label} ${p.value} (${pct(p.value)})`).join(", ")}`}>
          {parts.map((p) => {
            const w = total ? (usable * p.value) / total : 0;
            const center = offset + w / 2;
            offset += w + 2;
            const show = () => setTip({ x: center, y: -4, rows: [{ color: colors[p.label], label: `${p.label} · ${pct(p.value)}`, value: `${p.value} ${unit}` }] });
            return (
              <div key={p.label} tabIndex={0} aria-label={`${p.label}: ${p.value} ${unit}, ${pct(p.value)}`}
                onPointerMove={show} onPointerLeave={() => setTip(null)} onFocus={show} onBlur={() => setTip(null)}
                className="h-full outline-offset-2 transition-[filter] hover:brightness-110"
                style={{ flexGrow: p.value, flexBasis: 0, background: colors[p.label] }} />
            );
          })}
        </div>
        <Tooltip tip={tip} />
      </div>
      <ul className="divide-y divide-line">
        {data.map((d) => (
          <li key={d.label} className="flex items-center gap-2.5 py-2 text-[13px]">
            <span className="size-2.5 shrink-0 rounded-[3px]" style={{ background: colors[d.label] }} aria-hidden />
            <span className="min-w-0 flex-1 truncate text-ink-2">{d.label}</span>
            <span className="tabular font-medium text-ink">{d.value}</span>
            <span className="tabular w-10 text-right text-muted">{pct(d.value)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---------- sparkline (12 periods; de-emphasis grey, the current period in the accent) ----------
export function Sparkline({ data, label, formatPeriod }:
  { data: { period: string; value: number }[]; label: string; formatPeriod: (p: string) => string }) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <div>
      <div className="flex h-12 items-end gap-[3px]" role="img"
        aria-label={`${label}: ${data.map((d) => `${formatPeriod(d.period)} ${d.value}`).join(", ")}`}>
        {data.map((d, i) => {
          const current = i === data.length - 1;
          return (
            <span key={d.period} title={`${formatPeriod(d.period)}: ${d.value}${current ? " (so far)" : ""}`}
              className="flex-1 rounded-t-[2px]"
              style={{
                height: d.value ? `${Math.max(10, (d.value / max) * 100)}%` : "2px",
                background: current ? "var(--series-1)" : d.value ? "var(--viz-axis)" : "var(--viz-grid)",
              }} />
          );
        })}
      </div>
      <div className="mt-1.5 flex justify-between text-[11px] text-muted">
        <span>{formatPeriod(data[0]?.period ?? "")}</span>
        <span>{formatPeriod(data[data.length - 1]?.period ?? "")}</span>
      </div>
    </div>
  );
}
