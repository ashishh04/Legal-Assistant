import clsx from "clsx";
import { useEffect, useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

/** A modal dialog: Escape and the backdrop close it, focus moves in and returns, the page behind doesn't scroll. */
export function Dialog({ open, onClose, title, subtitle, icon, children, footer, wide = false, busy = false }: {
  open: boolean; onClose: () => void; title: ReactNode; subtitle?: ReactNode; icon?: ReactNode; children: ReactNode;
  footer?: ReactNode; wide?: boolean; busy?: boolean;
}) {
  const titleId = useId();
  const panel = useRef<HTMLElement>(null);
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    if (!open) return;
    const before = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const first = panel.current?.querySelector<HTMLElement>("[data-autofocus], input:not([type=hidden]), select, textarea, button:not([data-close])");
    (first ?? panel.current)?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && !busy) { e.stopPropagation(); close.current(); } };
    window.addEventListener("keydown", onKey, true);
    return () => {
      window.removeEventListener("keydown", onKey, true);
      document.body.style.overflow = overflow;
      before?.focus?.();
    };
  }, [open, busy]);
  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-[60] flex items-start justify-center overflow-y-auto p-4 sm:items-center sm:p-6">
      <div className="fixed inset-0 bg-black/45 backdrop-blur-[2px]" onClick={() => { if (!busy) onClose(); }} />
      <section ref={panel} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}
        className={clsx("relative my-auto flex max-h-[calc(100vh-2rem)] w-full flex-col rounded-2xl border border-line bg-surface shadow-2xl outline-none animate-fade-up",
          wide ? "max-w-[880px]" : "max-w-[580px]")}>
        <header className="flex items-start gap-3 border-b border-line px-6 py-4">
          {icon && <span className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent-ink">{icon}</span>}
          <div className="min-w-0 flex-1">
            <h2 id={titleId} className="text-[16px] font-semibold tracking-[-0.01em] text-ink">{title}</h2>
            {subtitle && <p className="mt-0.5 text-[12.5px] text-ink-2">{subtitle}</p>}
          </div>
          <button type="button" data-close onClick={onClose} disabled={busy} aria-label="Close"
            className="grid size-8 shrink-0 place-items-center rounded-lg text-ink-2 hover:bg-surface-2 hover:text-ink disabled:opacity-40">
            <X size={17} />
          </button>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">{children}</div>
        {footer && <footer className="flex flex-wrap items-center justify-end gap-2 rounded-b-2xl border-t border-line bg-surface-2 px-6 py-3.5">{footer}</footer>}
      </section>
    </div>,
    document.body,
  );
}
