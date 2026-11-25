import clsx from "clsx";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Bell, BellRing, CalendarClock, CheckCheck, Gavel, TriangleAlert, UserPlus } from "lucide-react";
import { api } from "../api";
import { relativeDays, timeAgo } from "../lib/format";
import { useSession } from "../session";
import type { NotificationItem, Notifications } from "../types";

const POLL_MS = 60_000;

/** "due in 7 days", "due today", "2 days overdue", "hearing in 6 days": against the reporting date. */
function whenDue(n: NotificationItem): string {
  const d = n.days_left ?? 0;
  const noun = n.kind === "hearing" ? "hearing" : "due";
  if (d < 0) return n.kind === "hearing" ? `hearing was ${-d} day${d === -1 ? "" : "s"} ago` : relativeDays(d);
  return d === 0 ? `${noun} today` : `${noun} ${relativeDays(d)}`;
}

function iconFor(n: NotificationItem) {
  if (n.kind === "assigned") return UserPlus;
  if (n.kind === "hearing") return Gavel;
  if (n.stage === "overdue") return TriangleAlert;
  if (n.stage === "due") return BellRing;
  return CalendarClock;
}

/** Reminders for the signed-in user's case deadlines: checked every minute, on focus, and after every change. */
export function NotificationBell() {
  const { user } = useSession();
  const navigate = useNavigate();
  const [data, setData] = useState<Notifications | null>(null);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const userId = user?.user_id;

  const load = useCallback(() => {
    if (!userId) return;
    api.notifications().then((d) => setData(d)).catch(() => { /* keep the last list; retried at the next poll */ });
  }, [userId]);

  useEffect(() => {
    setData(null);
    load();
    const timer = window.setInterval(load, POLL_MS);
    window.addEventListener("focus", load);
    window.addEventListener("ferrero:records", load);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", load);
      window.removeEventListener("ferrero:records", load);
    };
  }, [load]);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onDoc); document.removeEventListener("keydown", onKey); };
  }, [open]);

  if (!user) return null;
  const unread = data?.unread ?? 0;

  const markAll = () => {
    setData((d) => d && { ...d, unread: 0, items: d.items.map((n) => ({ ...n, read: true })) });
    api.markRead().catch(load);
  };
  const openItem = (n: NotificationItem) => {
    if (!n.read) {
      setData((d) => d && { ...d, unread: Math.max(0, d.unread - 1), items: d.items.map((x) => (x.id === n.id ? { ...x, read: true } : x)) });
      api.markRead([n.id]).catch(load);
    }
    setOpen(false);
    navigate(n.link);
  };

  return (
    <div ref={ref} className="relative">
      <button type="button" onClick={() => { setOpen((o) => !o); if (!open) load(); }} aria-expanded={open} aria-haspopup="dialog"
        aria-label={unread ? `Notifications: ${unread} unread` : "Notifications"}
        className={clsx("relative grid size-9 place-items-center rounded-lg text-ink-2 transition-colors hover:bg-surface-3 hover:text-ink", open && "bg-surface-3 text-ink")}>
        {unread ? <BellRing size={17} strokeWidth={1.9} /> : <Bell size={17} strokeWidth={1.9} />}
        {unread > 0 && (
          <span className="tabular absolute end-0.5 top-0.5 grid h-[17px] min-w-[17px] place-items-center rounded-full bg-critical px-1 text-[10.5px] font-semibold leading-none text-white ring-2 ring-page">
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>
      {open && (
        <div role="dialog" aria-label="Notifications"
          className="absolute end-0 top-full z-50 mt-2 w-[min(408px,calc(100vw-1.5rem))] overflow-hidden rounded-xl border border-line bg-surface shadow-overlay animate-pop-in">
          <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
            <div>
              <div className="text-[14.5px] font-semibold text-ink">Notifications</div>
              <div className="text-[12.5px] text-muted">{unread ? `${unread} unread` : "All caught up"} · deadlines on your cases</div>
            </div>
            {unread > 0 && (
              <button type="button" onClick={markAll} className="inline-flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-[12.5px] font-medium text-ink-2 transition-colors hover:bg-surface-3 hover:text-ink">
                <CheckCheck size={14} /> Mark all read
              </button>
            )}
          </div>
          <ul className="max-h-[60vh] divide-y divide-line overflow-y-auto">
            {data && data.items.length === 0 && (
              <li className="px-5 py-10 text-center">
                <div className="mx-auto mb-3 grid size-11 place-items-center rounded-full border border-accent-line bg-accent-soft text-accent-ink"><Bell size={18} /></div>
                <div className="text-[14px] font-medium text-ink">No reminders yet</div>
                <p className="mx-auto mt-1 max-w-[290px] text-[13px] leading-relaxed text-muted">
                  Reminders appear here when a deadline on one of your cases is approaching, due or overdue{data.email ? ", and are also sent by e-mail" : ""}.
                </p>
              </li>
            )}
            {!data && <li className="px-5 py-8 text-center text-[13px] text-muted">Loading…</li>}
            {data?.items.map((n) => {
              const Icon = iconFor(n);
              const urgent = n.stage === "overdue" || n.stage === "due" || n.stage === "today";
              return (
                <li key={n.id}>
                  <button type="button" onClick={() => openItem(n)}
                    className={clsx("relative flex w-full gap-3 px-4 py-3 text-start transition-colors hover:bg-surface-2", !n.read && "bg-accent-soft/45")}>
                    {!n.read && <span aria-hidden className="absolute inset-y-0 start-0 w-[3px] bg-accent" />}
                    <span className={clsx("mt-0.5 grid size-8 shrink-0 place-items-center rounded-full",
                      urgent ? "bg-critical-soft text-critical-ink" : "bg-surface-3 text-ink-2")}>
                      <Icon size={15} />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className={clsx("block text-[13.5px] leading-snug text-ink", !n.read && "font-semibold")}>
                        {n.title}{!n.read && <span className="sr-only"> (unread)</span>}
                      </span>
                      <span className="mt-0.5 block text-[12.5px] leading-relaxed text-ink-2">{n.body}</span>
                      <span className="mt-1 block text-[12px] text-muted">
                        {n.case_id}{n.days_left != null ? ` · ${whenDue(n)}` : ""} · {timeAgo(n.created_at)}
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
          <div className="border-t border-line bg-surface-2 px-4 py-2.5 text-end">
            <button type="button" onClick={() => { setOpen(false); navigate("/follow-ups"); }}
              className="inline-flex items-center gap-1 text-[13px] font-medium text-accent-ink hover:underline">Open all follow-ups <ArrowRight size={13} /></button>
          </div>
        </div>
      )}
    </div>
  );
}
