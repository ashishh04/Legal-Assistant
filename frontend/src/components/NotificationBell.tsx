import clsx from "clsx";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, BellRing, CalendarClock, CheckCheck, Gavel, TriangleAlert, UserPlus } from "lucide-react";
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
        className="relative grid size-9 place-items-center rounded-xl border border-line bg-surface text-ink-2 transition hover:text-ink">
        {unread ? <BellRing size={16} /> : <Bell size={16} />}
        {unread > 0 && (
          <span className="tabular absolute -end-1.5 -top-1.5 grid h-[18px] min-w-[18px] place-items-center rounded-full bg-critical px-1 text-[10.5px] font-semibold text-white ring-2 ring-page">
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>
      {open && (
        <div role="dialog" aria-label="Notifications"
          className="absolute end-0 top-full z-50 mt-2 w-[min(400px,calc(100vw-2rem))] overflow-hidden rounded-2xl border border-line bg-surface shadow-2xl animate-fade-up">
          <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
            <div>
              <div className="text-[14px] font-semibold text-ink">Notifications</div>
              <div className="text-[12px] text-muted">{unread ? `${unread} unread` : "All caught up"} · deadlines on your cases</div>
            </div>
            {unread > 0 && (
              <button type="button" onClick={markAll} className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-[12.5px] font-medium text-ink-2 hover:bg-surface-2 hover:text-ink">
                <CheckCheck size={14} /> Mark all read
              </button>
            )}
          </div>
          <ul className="max-h-[60vh] divide-y divide-line overflow-y-auto">
            {data && data.items.length === 0 && (
              <li className="px-5 py-10 text-center">
                <div className="mx-auto mb-3 grid size-10 place-items-center rounded-2xl bg-accent-soft text-accent-ink"><Bell size={18} /></div>
                <div className="text-[13.5px] font-medium text-ink">No reminders yet</div>
                <p className="mx-auto mt-1 max-w-[280px] text-[12.5px] leading-relaxed text-muted">
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
                    className={clsx("flex w-full gap-3 px-4 py-3 text-start transition hover:bg-surface-2", !n.read && "bg-accent-soft/40")}>
                    <span className={clsx("mt-0.5 grid size-8 shrink-0 place-items-center rounded-xl",
                      urgent ? "bg-critical/10 text-critical" : "bg-surface-2 text-ink-2")}>
                      <Icon size={15} />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="flex items-start gap-2">
                        <span className={clsx("min-w-0 flex-1 text-[13px] leading-snug text-ink", !n.read && "font-semibold")}>{n.title}</span>
                        {!n.read && <span className="mt-1.5 size-2 shrink-0 rounded-full bg-accent" aria-label="Unread" />}
                      </span>
                      <span className="mt-0.5 block text-[12.5px] leading-relaxed text-ink-2">{n.body}</span>
                      <span className="mt-1 block text-[11.5px] text-muted">
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
              className="text-[12.5px] font-medium text-accent-ink hover:underline">Open all follow-ups</button>
          </div>
        </div>
      )}
    </div>
  );
}
