import clsx from "clsx";
import { useEffect, useRef, type ComponentType, type CSSProperties, type ReactNode, type SVGProps } from "react";
import { ChevronDown, CircleCheck, Clock3, Lock, ScanLine, TriangleAlert, CircleDashed, CircleAlert } from "lucide-react";
import { initials } from "../lib/format";

export type Icon = ComponentType<SVGProps<SVGSVGElement> & { size?: number | string; strokeWidth?: number | string }>;

export function Card({ className, children, ...rest }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={clsx("rounded-xl border border-line bg-surface shadow-card", className)} {...rest}>
      {children}
    </div>
  );
}

export function PageHeader({ eyebrow, title, subtitle, actions }: { eyebrow?: ReactNode; title: ReactNode; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-7 flex flex-wrap items-end justify-between gap-x-6 gap-y-4 animate-fade-up">
      <div className="min-w-0">
        {eyebrow && <div className="mb-2 text-[12.5px] font-medium text-muted">{eyebrow}</div>}
        <h1 className="font-display text-[32px] font-[540] leading-[1.12] text-ink">{title}</h1>
        {subtitle && <p className="mt-2 max-w-3xl text-[14.5px] leading-relaxed text-ink-2">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

// ---------- buttons ----------
type Variant = "primary" | "secondary" | "ghost" | "inverse";
type Size = "sm" | "md" | "lg";

/** Button looks, for links that act as buttons too. */
export function buttonCls(variant: Variant = "secondary", size: Size = "md", className?: string) {
  return clsx(
    "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg font-medium transition-colors",
    "disabled:cursor-not-allowed disabled:opacity-50",
    size === "sm" && "h-8 px-2.5 text-[13px]",
    size === "md" && "h-9 px-3.5 text-[13.5px]",
    size === "lg" && "h-11 px-5 text-[14.5px]",
    variant === "primary" && "bg-primary text-primary-ink shadow-card hover:bg-primary-hover",
    variant === "inverse" && "bg-on-brand text-brand shadow-card hover:bg-white",  // on a brand surface
    variant === "secondary" && "border border-line-strong bg-surface text-ink shadow-card hover:bg-surface-2",
    variant === "ghost" && "text-ink-2 hover:bg-surface-3 hover:text-ink",
    className,
  );
}

export function Button({ variant = "secondary", size = "md", icon: IconCmp, className, children, ...rest }:
  React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size; icon?: Icon }) {
  return (
    <button type="button" className={buttonCls(variant, size, className)} {...rest}>
      {IconCmp && <IconCmp size={size === "lg" ? 17 : 16} strokeWidth={1.9} />}
      {children}
    </button>
  );
}

/** A square, borderless control for a single icon (always pass `aria-label`). */
export function IconButton({ icon: IconCmp, className, size = 36, ...rest }:
  React.ButtonHTMLAttributes<HTMLButtonElement> & { icon: Icon; size?: number }) {
  return (
    <button type="button" style={{ width: size, height: size }}
      className={clsx("grid shrink-0 place-items-center rounded-lg text-ink-2 transition-colors hover:bg-surface-3 hover:text-ink disabled:opacity-40", className)} {...rest}>
      <IconCmp size={Math.round(size / 2.1)} strokeWidth={1.9} />
    </button>
  );
}

// ---------- filters ----------
/** A labelled filter in a toolbar. It is as wide as its current value (the real select lies over it, unseen, so the
 *  keyboard and the browser's own list still work), and takes the accent while it narrows the list. */
export function Select({ label, value, onChange, options, className }:
  { label: string; value: string; onChange: (v: string) => void; options: { value: string; label: string }[]; className?: string }) {
  const current = options.find((o) => o.value === value)?.label ?? "";
  return (
    <label className={clsx(
      "relative inline-flex h-9 min-w-0 max-w-full items-center gap-1.5 rounded-lg border ps-3 pe-2.5 text-[13px] shadow-card transition-colors",
      "focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/20",
      value ? "border-accent-line bg-accent-soft" : "border-line-strong bg-surface hover:bg-surface-2",
      className)}>
      <span className="shrink-0 text-muted">{label}</span>
      <span className="truncate font-medium text-ink" aria-hidden>{current}</span>
      <ChevronDown size={14} strokeWidth={2.2} className="ms-0.5 shrink-0 text-muted" aria-hidden />
      <select aria-label={label} className="absolute inset-0 size-full cursor-pointer opacity-0"
        value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>
  );
}

/** The search box of a list page. */
export function SearchField({ value, onChange, placeholder, label, className, icon: IconCmp }:
  { value: string; onChange: (v: string) => void; placeholder: string; label: string; className?: string; icon: Icon }) {
  return (
    <label className={clsx(
      "flex h-9 min-w-[220px] items-center gap-2 rounded-lg border border-line-strong bg-surface px-3 text-[13.5px] shadow-card transition-colors",
      "focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/20", className)}>
      <IconCmp size={15} className="shrink-0 text-muted" />
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} aria-label={label}
        className="min-w-0 flex-1 bg-transparent text-ink outline-none placeholder:text-muted" />
    </label>
  );
}

// ---------- tags and state ----------
export type Tone = "neutral" | "good" | "warning" | "critical" | "info" | "accent" | "outline";

const TONES: Record<Tone, string> = {
  neutral: "bg-surface-3 text-ink-2",
  good: "bg-good-soft text-good-ink",
  warning: "bg-warning-soft text-warning-ink",
  critical: "bg-critical-soft text-critical-ink",
  info: "bg-info-soft text-info-ink",
  accent: "bg-accent-soft text-accent-ink",
  outline: "border border-line-strong text-ink-2",
};

/** A small label on a record: its type, its stage, a flag. */
export function Chip({ children, className, tone = "neutral" }: { children: ReactNode; className?: string; tone?: Tone }) {
  return (
    <span className={clsx("inline-flex items-center gap-1.5 whitespace-nowrap rounded-md px-2 py-[3px] text-[12px] font-medium leading-4", TONES[tone], className)}>
      {children}
    </span>
  );
}

/** State is never colour alone: an icon and a label, in the state's own ink on its soft fill. */
const STATUS: Record<string, { icon: Icon; tone: Tone }> = {
  good: { icon: CircleCheck, tone: "good" },
  warning: { icon: TriangleAlert, tone: "warning" },
  serious: { icon: TriangleAlert, tone: "warning" },
  critical: { icon: CircleAlert, tone: "critical" },
  pending: { icon: Clock3, tone: "neutral" },
  locked: { icon: Lock, tone: "neutral" },
  scan: { icon: ScanLine, tone: "neutral" },
  neutral: { icon: CircleDashed, tone: "neutral" },
};

export function StatusPill({ kind, children }: { kind: keyof typeof STATUS; children: ReactNode }) {
  const s = STATUS[kind];
  const IconCmp = s.icon;
  return (
    <span className={clsx("inline-flex items-center gap-1.5 whitespace-nowrap rounded-full py-[3px] ps-2 pe-2.5 text-[12px] font-medium leading-4", TONES[s.tone])}>
      <IconCmp size={13} strokeWidth={2.2} aria-hidden />
      {children}
    </span>
  );
}

export const OUTCOME_SLOTS: Record<string, string> = {
  "Won": "var(--series-1)",
  "Partially won": "var(--series-2)",
  "Settled": "var(--series-3)",
  "Takedown achieved": "var(--series-4)",
  "Lost": "var(--series-5)",
  "Withdrawn": "var(--series-6)",
};

/** Outcome identity matches the outcome chart: a coloured dot beside ink text (text never wears the data colour). */
export function Outcome({ outcome }: { outcome: string }) {
  const color = OUTCOME_SLOTS[outcome];
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-[13px] font-medium text-ink">
      <span className="size-2 rounded-full" style={{ background: color ?? "var(--viz-axis)" }} aria-hidden />
      {outcome}
    </span>
  );
}

// ---------- people ----------
const AVATAR_HUES = ["#2563eb", "#0f766e", "#4f46e5", "#7c3aed", "#0e7490", "#be185d", "#475569", "#15803d"];

/** Initials on a tint picked from the name, so the same person is the same colour everywhere. */
export function Avatar({ name, size = 36, className }: { name: string; size?: number; className?: string }) {
  let h = 0;
  for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  const hue = AVATAR_HUES[h % AVATAR_HUES.length];
  const style: CSSProperties = {
    width: size, height: size, fontSize: Math.max(10, Math.round(size * 0.36)),
    background: `color-mix(in srgb, ${hue} 20%, var(--surface))`,
    color: `color-mix(in srgb, ${hue} 52%, var(--ink))`,
  };
  return (
    <span className={clsx("grid shrink-0 place-items-center rounded-full font-semibold tracking-[0.01em]", className)} style={style} aria-hidden>
      {initials(name)}
    </span>
  );
}

// ---------- figures ----------
/** A row of figures in one card, ruled between (the rules follow however the row wraps). */
export function StatStrip({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={clsx("grid gap-px overflow-hidden rounded-xl border border-line bg-line shadow-card", className)}>
      {children}
    </div>
  );
}

export function StatTile({ label, value, sub, status, className }:
  { label: ReactNode; value: ReactNode; sub?: ReactNode; status?: { kind: keyof typeof STATUS; text: string }; className?: string }) {
  return (
    <div className={clsx("flex min-w-0 flex-col bg-surface px-5 py-4", className)}>
      <div className="text-[12.5px] font-medium text-muted">{label}</div>
      <div className="tabular mt-1.5 text-[26px] font-semibold leading-none tracking-[-0.02em] text-ink">{value}</div>
      {sub && <div className="mt-2 text-[12.5px] leading-snug text-ink-2">{sub}</div>}
      {status && <div className="mt-2.5"><StatusPill kind={status.kind}>{status.text}</StatusPill></div>}
    </div>
  );
}

// ---------- structure ----------
/** `plain`: inside a card already, so no card of its own. */
export function EmptyState({ icon: IconCmp, title, children, action, plain = false }:
  { icon: Icon; title: string; children?: ReactNode; action?: ReactNode; plain?: boolean }) {
  const body = (
    <>
      <div className="grid size-12 place-items-center rounded-full border border-accent-line bg-accent-soft text-accent-ink">
        <IconCmp size={21} strokeWidth={1.7} />
      </div>
      <div className="text-[16px] font-semibold text-ink">{title}</div>
      {children && <div className="max-w-md text-[13.5px] leading-relaxed text-ink-2">{children}</div>}
      {action && <div className="mt-1">{action}</div>}
    </>
  );
  return plain
    ? <div className="flex flex-col items-center gap-2.5 px-6 py-10 text-center">{body}</div>
    : <Card className="flex flex-col items-center gap-2.5 px-6 py-14 text-center">{body}</Card>;
}

export function SectionTitle({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
      <h2 className="text-[15px] font-semibold text-ink">{children}</h2>
      {aside}
    </div>
  );
}

/** Underlined tabs over a rule; scrolls sideways on narrow screens. */
export function Tabs<T extends string>({ value, onChange, tabs, label, className }: {
  value: T; onChange: (v: T) => void; tabs: { value: T; label: ReactNode; count?: number | null }[]; label: string; className?: string;
}) {
  const row = useRef<HTMLDivElement>(null);
  // Sideways only: the page itself must not jump to the tabs when one is chosen from a link.
  useEffect(() => {
    const box = row.current;
    const tab = box?.querySelector<HTMLElement>("[aria-selected=true]");
    if (!box || !tab) return;
    const left = tab.offsetLeft - box.offsetLeft;
    if (left < box.scrollLeft) box.scrollLeft = left - 12;
    else if (left + tab.offsetWidth > box.scrollLeft + box.clientWidth) box.scrollLeft = left + tab.offsetWidth - box.clientWidth + 12;
  }, [value, tabs.length]);
  return (
    <div ref={row} role="tablist" aria-label={label} className={clsx("no-scrollbar flex gap-1 overflow-x-auto border-b border-line", className)}>
      {tabs.map((t) => {
        const active = t.value === value;
        return (
          <button key={t.value} type="button" role="tab" aria-selected={active} onClick={() => onChange(t.value)}
            className={clsx("relative flex items-center gap-2 whitespace-nowrap px-3 pb-3 pt-2 text-[13.5px] font-medium transition-colors",
              active ? "text-ink" : "text-muted hover:text-ink")}>
            {t.label}
            {t.count != null && t.count > 0 && (
              <span className={clsx("tabular rounded-full px-1.5 py-px text-[11px] font-semibold",
                active ? "bg-accent-soft text-accent-ink" : "bg-surface-3 text-ink-2")}>{t.count}</span>
            )}
            {active && <span aria-hidden className="absolute inset-x-2 -bottom-px h-[2px] rounded-full bg-accent" />}
          </button>
        );
      })}
    </div>
  );
}

/** A notice inside a page or a dialog. */
export function Callout({ tone = "neutral", icon: IconCmp, title, children, action, className }: {
  tone?: "neutral" | "warning" | "critical" | "good" | "accent"; icon: Icon; title?: ReactNode; children?: ReactNode; action?: ReactNode; className?: string;
}) {
  const look = {
    neutral: "border-line bg-surface-2", warning: "border-warning-line bg-warning-soft", critical: "border-critical-line bg-critical-soft",
    good: "border-good-line bg-good-soft", accent: "border-accent-line bg-accent-soft",
  }[tone];
  const ink = { neutral: "text-accent-ink", warning: "text-warning", critical: "text-critical", good: "text-good", accent: "text-accent-ink" }[tone];
  return (
    <div className={clsx("flex flex-wrap items-start gap-x-3 gap-y-2 rounded-xl border p-3.5", look, className)}>
      <IconCmp size={17} className={clsx("mt-0.5 shrink-0", ink)} />
      <div className="min-w-0 flex-1 text-[13px] leading-relaxed text-ink-2">
        {title && <div className="text-[13.5px] font-semibold text-ink">{title}</div>}
        {children}
      </div>
      {action}
    </div>
  );
}
