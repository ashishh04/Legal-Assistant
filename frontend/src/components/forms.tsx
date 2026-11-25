import clsx from "clsx";
import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";
import { CircleAlert } from "lucide-react";

export const inputCls =
  "w-full rounded-lg border border-line-strong bg-surface px-3 py-2 text-[13.5px] text-ink shadow-card outline-none transition-colors " +
  "placeholder:text-muted hover:border-muted/60 focus:border-accent focus:ring-2 focus:ring-accent/20 " +
  "disabled:cursor-not-allowed disabled:bg-surface-2 disabled:opacity-70 disabled:hover:border-line-strong";

/** A labelled control. `group`: the control is a set of buttons (Segmented), which carries its own name, so the
 *  caption is not a <label> (a label would rename the buttons and pass clicks on its text to the first one). */
export function Field({ label, hint, children, className, optional, group = false }:
  { label: ReactNode; hint?: ReactNode; children: ReactNode; className?: string; optional?: boolean; group?: boolean }) {
  const Caption = group ? "div" : "label";
  return (
    <div className={clsx("min-w-0", className)}>
      <Caption className="block">
        <span className="mb-1.5 flex items-baseline justify-between gap-2 text-[13px] font-medium text-ink">
          {label}{optional && <span className="text-[12px] font-normal text-muted">Optional</span>}
        </span>
        {children}
      </Caption>
      {hint && <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted">{hint}</p>}
    </div>
  );
}

export function TextInput({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={clsx(inputCls, "h-10", className)} {...rest} />;
}

export function TextArea({ className, rows = 3, ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea rows={rows} className={clsx(inputCls, "resize-y leading-relaxed", className)} {...rest} />;
}

export function SelectInput({ options, placeholder, className, ...rest }:
  SelectHTMLAttributes<HTMLSelectElement> & { options: (string | { value: string; label: string })[]; placeholder?: string }) {
  return (
    <select className={clsx(inputCls, "select-caret h-10 cursor-pointer truncate pe-9", className)} {...rest}>
      {placeholder !== undefined && <option value="">{placeholder}</option>}
      {options.map((o) => typeof o === "string"
        ? <option key={o} value={o}>{o}</option>
        : <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}

/** A row of mutually exclusive choices (pressed buttons). */
export function Segmented<T extends string>({ value, onChange, options, label, size = "md" }:
  { value: T; onChange: (v: T) => void; options: { value: T; label: ReactNode }[]; label: string; size?: "sm" | "md" }) {
  return (
    <div role="group" aria-label={label} className="inline-flex flex-wrap gap-0.5 rounded-lg bg-surface-3 p-[3px]">
      {options.map((o) => (
        <button key={o.value} type="button" aria-pressed={value === o.value} onClick={() => onChange(o.value)}
          className={clsx("rounded-md font-medium transition-colors", size === "sm" ? "px-2.5 py-1 text-[12.5px]" : "px-3 py-1.5 text-[13px]",
            value === o.value ? "bg-surface text-ink shadow-raised" : "text-ink-2 hover:text-ink")}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function FormError({ children }: { children: ReactNode }) {
  if (!children) return null;
  return (
    <div role="alert" className="mb-4 flex items-start gap-2.5 rounded-lg border border-critical-line bg-critical-soft px-3.5 py-2.5 text-[13px] text-ink">
      <CircleAlert size={16} className="mt-0.5 shrink-0 text-critical" />
      <span className="leading-relaxed">{children}</span>
    </div>
  );
}

export function FormSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="mb-6 last:mb-0">
      <legend className="mb-3.5 flex w-full items-center gap-3 text-[12px] font-semibold uppercase tracking-[0.08em] text-muted">
        {title}<span aria-hidden className="h-px flex-1 bg-line" />
      </legend>
      {children}
    </fieldset>
  );
}
