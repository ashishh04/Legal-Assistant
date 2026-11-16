import clsx from "clsx";
import type { ComponentType, ReactNode, SVGProps } from "react";
import { CircleCheck, Clock3, Lock, ScanLine, TriangleAlert, CircleDashed } from "lucide-react";

type Icon = ComponentType<SVGProps<SVGSVGElement> & { size?: number | string; strokeWidth?: number | string }>;

export function Card({ className, children, ...rest }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={clsx("rounded-2xl border border-line bg-surface shadow-card", className)} {...rest}>
      {children}
    </div>
  );
}

export function PageHeader({ eyebrow, title, subtitle, actions }: { eyebrow?: string; title: ReactNode; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4 animate-fade-up">
      <div className="min-w-0">
        {eyebrow && <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-accent-ink">{eyebrow}</div>}
        <h1 className="text-[26px] font-semibold leading-tight tracking-[-0.02em] text-ink">{title}</h1>
        {subtitle && <p className="mt-1.5 max-w-3xl text-[14px] text-ink-2">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Button({ variant = "secondary", icon: IconCmp, className, children, ...rest }:
  React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "gold"; icon?: Icon }) {
  return (
    <button
      type="button"
      className={clsx(
        "inline-flex items-center justify-center gap-2 rounded-xl px-3.5 py-2 text-[13.5px] font-medium transition",
        "disabled:cursor-not-allowed disabled:opacity-50",
        variant === "primary" && "bg-primary text-primary-ink hover:opacity-90",
        variant === "gold" && "bg-accent text-[#141519] hover:brightness-105",
        variant === "secondary" && "border border-line-strong bg-surface text-ink hover:bg-surface-2",
        variant === "ghost" && "text-ink-2 hover:bg-surface-2 hover:text-ink",
        className,
      )}
      {...rest}
    >
      {IconCmp && <IconCmp size={16} strokeWidth={1.8} />}
      {children}
    </button>
  );
}

export function Select({ label, value, onChange, options, className }:
  { label: string; value: string; onChange: (v: string) => void; options: { value: string; label: string }[]; className?: string }) {
  return (
    <label className={clsx("flex items-center gap-2 rounded-xl border border-line-strong bg-surface px-3 py-1.5 text-[13px]", className)}>
      <span className="text-muted">{label}</span>
      <select
        className="cursor-pointer bg-transparent pe-1 font-medium text-ink outline-none"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>
  );
}

export function Chip({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span className={clsx("inline-flex items-center gap-1.5 rounded-full border border-line bg-surface-2 px-2.5 py-0.5 text-[12px] font-medium text-ink-2", className)}>
      {children}
    </span>
  );
}

/** Status is never colour alone: an icon in the reserved status colour, plus a text label in ink. */
const STATUS: Record<string, { icon: Icon; color: string }> = {
  good: { icon: CircleCheck, color: "var(--good)" },
  warning: { icon: TriangleAlert, color: "var(--warning)" },
  serious: { icon: TriangleAlert, color: "var(--serious)" },
  critical: { icon: TriangleAlert, color: "var(--critical)" },
  pending: { icon: Clock3, color: "var(--warning)" },
  locked: { icon: Lock, color: "var(--muted)" },
  scan: { icon: ScanLine, color: "var(--muted)" },
  neutral: { icon: CircleDashed, color: "var(--muted)" },
};

export function StatusPill({ kind, children }: { kind: keyof typeof STATUS; children: ReactNode }) {
  const s = STATUS[kind];
  const IconCmp = s.icon;
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border border-line bg-surface-2 py-0.5 ps-1.5 pe-2.5 text-[12px] font-medium text-ink-2">
      <IconCmp size={13} strokeWidth={2.2} style={{ color: s.color }} aria-hidden />
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
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-[13px] text-ink">
      <span className="size-2 rounded-full" style={{ background: color ?? "var(--viz-axis)" }} aria-hidden />
      {outcome}
    </span>
  );
}

export function StatTile({ label, value, sub, status, className }:
  { label: string; value: ReactNode; sub?: ReactNode; status?: { kind: keyof typeof STATUS; text: string }; className?: string }) {
  return (
    <Card className={clsx("flex min-w-0 flex-col gap-1 p-5", className)}>
      <div className="text-[13px] text-ink-2">{label}</div>
      <div className="text-[28px] font-semibold leading-tight tracking-[-0.02em] text-ink">{value}</div>
      {sub && <div className="text-[12.5px] text-muted">{sub}</div>}
      {status && <div className="mt-1"><StatusPill kind={status.kind}>{status.text}</StatusPill></div>}
    </Card>
  );
}

/** The one number a view leads with (exactly one per page). */
export function HeroFigure({ label, value, sub, children }: { label: string; value: ReactNode; sub?: ReactNode; children?: ReactNode }) {
  return (
    <Card className="relative flex min-w-0 flex-col justify-between overflow-hidden p-6">
      <div aria-hidden className="pointer-events-none absolute -end-16 -top-16 size-56 rounded-full bg-[radial-gradient(circle,var(--accent-soft),transparent_70%)]" />
      <div className="relative">
        <div className="text-[13px] font-medium text-ink-2">{label}</div>
        <div className="mt-2 text-[56px] font-semibold leading-none tracking-[-0.035em] text-ink">{value}</div>
        {sub && <div className="mt-3 text-[13px] text-ink-2">{sub}</div>}
      </div>
      {children && <div className="relative mt-5">{children}</div>}
    </Card>
  );
}

export function EmptyState({ icon: IconCmp, title, children, action }: { icon: Icon; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <Card className="flex flex-col items-center gap-3 px-6 py-14 text-center">
      <div className="grid size-12 place-items-center rounded-2xl bg-accent-soft text-accent-ink"><IconCmp size={22} strokeWidth={1.7} /></div>
      <div className="text-[16px] font-semibold text-ink">{title}</div>
      {children && <div className="max-w-md text-[13.5px] leading-relaxed text-ink-2">{children}</div>}
      {action}
    </Card>
  );
}

export function SectionTitle({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="mb-3 flex items-center justify-between gap-3">
      <h2 className="text-[15px] font-semibold tracking-[-0.01em] text-ink">{children}</h2>
      {aside}
    </div>
  );
}
