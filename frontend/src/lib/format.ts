const compact = new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 });
const whole = new Intl.NumberFormat("en");
const DAY = 86_400_000;

export const fmtInt = (n: number | null | undefined) => (n == null ? "–" : whole.format(Math.round(n)));
export const fmtCompact = (n: number | null | undefined) => (n == null ? "–" : compact.format(n));
export const fmtAED = (n: number | null | undefined, short = true) =>
  n == null ? "–" : `AED ${short && Math.abs(n) >= 10_000 ? compact.format(n) : whole.format(n)}`;
export const fmtMoney = (n: number | null | undefined, currency: string) =>
  n == null ? "–" : `${currency} ${Math.abs(n) >= 1_000_000 ? compact.format(n) : whole.format(n)}`;
export const fmtPct = (r: number | null | undefined, digits = 1) => (r == null ? "–" : `${(r * 100).toFixed(digits)}%`);

export function fmtDate(iso: string | null | undefined, opts: Intl.DateTimeFormatOptions = { day: "numeric", month: "short", year: "numeric" }) {
  if (!iso) return "–";
  const d = new Date(`${iso.slice(0, 10)}T00:00:00`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-GB", opts);
}

/** Whole days from `today` to `iso` (negative = in the past). */
export function daysFrom(today: string, iso: string | null | undefined): number | null {
  if (!iso) return null;
  return Math.round((Date.parse(`${iso.slice(0, 10)}T00:00:00Z`) - Date.parse(`${today}T00:00:00Z`)) / DAY);
}

export function relativeDays(days: number | null): string {
  if (days == null) return "";
  if (days === 0) return "today";
  if (days > 0) return days === 1 ? "tomorrow" : `in ${days} days`;
  return days === -1 ? "1 day overdue" : `${-days} days overdue`;
}

export const initials = (name: string) =>
  name.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]).join("").toUpperCase();

export function greeting(date = new Date()) {
  const h = date.getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

export function fmtBytes(n: number | null | undefined) {
  if (n == null) return "–";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(n < 10 * 1024 ? 1 : 0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

/** A UTC timestamp in the reader's time zone: "17 Nov 2026, 10:32". */
export function fmtDateTime(iso: string | null | undefined) {
  if (!iso) return "–";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso
    : d.toLocaleString("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

/** "3 min ago", "2 h ago", "yesterday", or the date. */
export function timeAgo(iso: string | null | undefined, now = Date.now()) {
  if (!iso) return "";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "";
  const min = Math.round((now - t) / 60_000);
  if (min < 1) return "just now";
  if (min < 60) return `${min} min ago`;
  const h = Math.round(min / 60);
  if (h < 24) return `${h} h ago`;
  return h < 48 ? "yesterday" : fmtDate(iso.slice(0, 10));
}

/** Add whole days to an ISO date. */
export function addDays(iso: string, days: number) {
  const d = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}
