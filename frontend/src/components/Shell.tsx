import clsx from "clsx";
import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  BriefcaseBusiness, CalendarClock, CalendarDays, ChartPie, ExternalLink, FileText, LayoutDashboard, Menu, Moon, Search,
  Sparkles, Sun, X,
} from "lucide-react";
import { fmtDate } from "../lib/format";
import { useSession } from "../session";
import { Monogram } from "./Brand";
import { Chat } from "./Chat";
import { NotificationBell } from "./NotificationBell";
import { UserMenu } from "./UserMenu";

const NAV = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/cases", label: "Cases", icon: BriefcaseBusiness },
  { to: "/follow-ups", label: "Follow-ups", icon: CalendarClock },
  { to: "/assistant", label: "Assistant", icon: Sparkles },
  { to: "/documents", label: "Documents", icon: FileText },
  { to: "/dashboards", label: "Dashboards", icon: ChartPie },
];

export function Shell() {
  const { openAssistant, bootError } = useSession();
  const location = useLocation();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);

  // Deep link from Power BI / Superset: /?case=TM-2024-428[&ask=...] opens the case with Ferrero beside it.
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const caseId = params.get("case");
    if (caseId && location.pathname === "/") {
      navigate(`/cases/${caseId.toUpperCase()}`, { replace: true });
      openAssistant(caseId.toUpperCase(), params.get("ask"));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => setMenuOpen(false), [location.pathname]);

  return (
    <div className="flex h-full">
      <div className={clsx("fixed inset-0 z-40 bg-black/40 lg:hidden", menuOpen ? "block" : "hidden")} onClick={() => setMenuOpen(false)} />
      <aside className={clsx(
        "fixed inset-y-0 start-0 z-50 w-[264px] shrink-0 transition-transform lg:static lg:translate-x-0",
        menuOpen ? "translate-x-0" : "-translate-x-full",
      )}>
        <Sidebar />
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onMenu={() => setMenuOpen(true)} />
        <main className="min-h-0 flex-1 overflow-y-auto">
          {bootError ? (
            <div className="mx-auto max-w-xl px-6 py-20 text-center text-ink-2">
              <div className="text-[16px] font-semibold text-ink">Ferrero is temporarily unavailable</div>
              <p className="mt-2 text-[13.5px]">Please refresh the page in a moment.</p>
            </div>
          ) : (
            <div className="mx-auto w-full max-w-[1360px] px-5 py-7 sm:px-8 lg:px-10">
              <Outlet />
            </div>
          )}
        </main>
      </div>
      <AssistantDrawer />
    </div>
  );
}

function Sidebar() {
  const { meta } = useSession();
  return (
    <div className="flex h-full flex-col bg-sidebar text-sidebar-ink">
      <div className="flex items-center gap-3 px-5 pb-6 pt-6">
        <Monogram size={38} />
        <div>
          <div className="text-[16px] font-semibold tracking-[-0.01em] text-white">Ferrero</div>
          <div className="text-[12px] text-sidebar-muted">Case intelligence</div>
        </div>
      </div>
      <nav className="flex flex-col gap-0.5 px-3" aria-label="Main">
        <div className="px-3 pb-2 text-[10.5px] font-semibold uppercase tracking-[0.16em] text-sidebar-muted">Workspace</div>
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink key={to} to={to} end={end}
            className={({ isActive }) => clsx(
              "group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-[14px] transition",
              isActive ? "bg-sidebar-2 font-medium text-white" : "text-sidebar-muted hover:bg-sidebar-2/60 hover:text-sidebar-ink",
            )}>
            {({ isActive }) => (
              <>
                <span className={clsx("absolute inset-y-2 start-0 w-[3px] rounded-full transition", isActive ? "bg-accent" : "bg-transparent")} />
                <Icon size={18} strokeWidth={1.7} className={isActive ? "text-accent" : ""} />
                {label}
              </>
            )}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto flex flex-col gap-3 p-3">
        <UserMenu />
        {meta && (
          <div className="px-2 pb-1 text-[11px] leading-relaxed text-sidebar-muted">
            {meta.org_name}<br />Legal &amp; Brand Protection
          </div>
        )}
      </div>
    </div>
  );
}

const TITLES: [RegExp, string][] = [
  [/^\/$/, "Overview"], [/^\/cases\/[^/]+/, "Case"], [/^\/cases/, "Cases"], [/^\/assistant/, "Assistant"],
  [/^\/documents/, "Documents"], [/^\/dashboards/, "Dashboards"], [/^\/follow-ups/, "Follow-ups"],
];

function Topbar({ onMenu }: { onMenu: () => void }) {
  const { meta, theme, toggleTheme, openAssistant } = useSession();
  const location = useLocation();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);
  const title = TITLES.find(([re]) => re.test(location.pathname))?.[1] ?? "Ferrero";

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); searchRef.current?.focus(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const submit = () => {
    const text = q.trim();
    if (!text) return;
    const id = text.match(/TM-\d{4}-\d{3}/i)?.[0];
    navigate(id ? `/cases/${id.toUpperCase()}` : `/cases?q=${encodeURIComponent(text)}`);
    setQ("");
    searchRef.current?.blur();
  };

  return (
    <header className="sticky top-0 z-30 flex h-16 shrink-0 items-center gap-3 border-b border-line bg-page/80 px-4 backdrop-blur-xl sm:px-6 lg:px-10">
      <button type="button" className="grid size-9 place-items-center rounded-xl text-ink-2 hover:bg-surface-2 lg:hidden" onClick={onMenu} aria-label="Open menu">
        <Menu size={19} />
      </button>
      <div className="hidden text-[14px] font-medium text-ink-2 sm:block">{title}</div>
      <form className="ms-auto flex min-w-0 max-w-md flex-1 sm:ms-6" onSubmit={(e) => { e.preventDefault(); submit(); }}>
        <label className="flex w-full items-center gap-2 rounded-xl border border-line bg-surface px-3 py-2 text-[13.5px] focus-within:border-accent">
          <Search size={16} className="text-muted" />
          <input ref={searchRef} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search cases, parties, marks…"
            className="min-w-0 flex-1 bg-transparent text-ink outline-none placeholder:text-muted" aria-label="Search cases" />
          <kbd className="hidden rounded-md border border-line px-1.5 text-[11px] text-muted md:inline">Ctrl K</kbd>
        </label>
      </form>
      <div className="ms-auto flex items-center gap-2">
        {meta && (
          <span className="hidden items-center gap-1.5 rounded-xl border border-line bg-surface px-2.5 py-1.5 text-[12.5px] text-ink-2 md:inline-flex" title="Reporting date">
            <CalendarDays size={14} className="text-accent-ink" /> {fmtDate(meta.demo_today)}
          </span>
        )}
        <NotificationBell />
        <button type="button" onClick={toggleTheme} aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
          className="grid size-9 place-items-center rounded-xl border border-line bg-surface text-ink-2 transition hover:text-ink">
          {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
        </button>
        <button type="button" onClick={() => openAssistant(null)}
          className="inline-flex items-center gap-2 rounded-xl bg-primary px-3.5 py-2 text-[13.5px] font-medium text-primary-ink transition hover:opacity-90">
          <Sparkles size={15} className="text-accent" /> <span className="hidden sm:inline">Ask Ferrero</span>
        </button>
      </div>
    </header>
  );
}

function AssistantDrawer() {
  const { assistant, closeAssistant, user } = useSession();
  const navigate = useNavigate();
  useEffect(() => {
    if (!assistant.open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") closeAssistant(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [assistant.open, closeAssistant]);
  if (!assistant.open || !user) return null;
  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/25 backdrop-blur-[2px]" onClick={closeAssistant} />
      <section role="dialog" aria-label="Ferrero assistant"
        className="absolute inset-y-0 end-0 flex w-[min(600px,100vw)] flex-col border-s border-line bg-page shadow-2xl animate-slide-in">
        <div className="flex items-center gap-3 border-b border-line bg-surface px-5 py-3.5">
          <Monogram size={32} />
          <div className="min-w-0 flex-1">
            <div className="text-[14.5px] font-semibold text-ink">Ferrero</div>
            <div className="truncate text-[12px] text-muted">
              {assistant.caseId ? `Focused on ${assistant.caseId}` : "All cases and documents you can access"} · as {user.full_name}
            </div>
          </div>
          <button type="button" aria-label="Open the full assistant page" title="Open full page"
            onClick={() => { closeAssistant(); navigate(assistant.caseId ? `/assistant?case=${assistant.caseId}` : "/assistant"); }}
            className="grid size-8 place-items-center rounded-lg text-ink-2 hover:bg-surface-2 hover:text-ink">
            <ExternalLink size={16} />
          </button>
          <button type="button" aria-label="Close" onClick={closeAssistant}
            className="grid size-8 place-items-center rounded-lg text-ink-2 hover:bg-surface-2 hover:text-ink">
            <X size={18} />
          </button>
        </div>
        <div className="min-h-0 flex-1">
          <Chat key={`${assistant.nonce}-${user.user_id}`} caseId={assistant.caseId} prompt={assistant.prompt} compact />
        </div>
      </section>
    </div>
  );
}
