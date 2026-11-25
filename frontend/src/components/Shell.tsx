import clsx from "clsx";
import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  BriefcaseBusiness, CalendarClock, CalendarDays, ChartPie, ExternalLink, Eye, FileText, LayoutDashboard, Menu, Moon, Search,
  Sparkles, Sun, Undo2, UsersRound, X,
} from "lucide-react";
import { useToast } from "../lib/toast";
import { fmtDate } from "../lib/format";
import { useSession } from "../session";
import { Brand, Monogram } from "./Brand";
import { Chat } from "./Chat";
import { NotificationBell } from "./NotificationBell";
import { UserMenu } from "./UserMenu";
import { Button, IconButton, type Icon } from "./ui";

const NAV: { to: string; label: string; icon: Icon; end?: boolean }[] = [
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
      <div className={clsx("fixed inset-0 z-40 bg-scrim/55 backdrop-blur-[2px] lg:hidden", menuOpen ? "block" : "hidden")} onClick={() => setMenuOpen(false)} />
      <aside className={clsx(
        "fixed inset-y-0 start-0 z-50 w-[256px] shrink-0 transition-transform duration-200 lg:static lg:translate-x-0",
        menuOpen ? "translate-x-0" : "-translate-x-full",
      )}>
        <Sidebar />
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <ActingBanner />
        <Topbar onMenu={() => setMenuOpen(true)} />
        <main className="min-h-0 flex-1 overflow-y-auto">
          {bootError ? (
            <div className="mx-auto max-w-xl px-6 py-24 text-center text-ink-2">
              <div className="font-display text-[22px] font-[540] text-ink">Ferrero is temporarily unavailable</div>
              <p className="mt-2 text-[14px]">Please refresh the page in a moment.</p>
            </div>
          ) : (
            <div className="mx-auto w-full max-w-[1400px] px-5 pb-12 pt-8 sm:px-8 2xl:px-10">
              <Outlet />
            </div>
          )}
        </main>
      </div>
      <AssistantDrawer />
    </div>
  );
}

/** While the administrator views the portal as someone else: whose view it is, and the way back. */
function ActingBanner() {
  const { user, switchBack } = useSession();
  const navigate = useNavigate();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  if (!user?.acting_by) return null;
  const back = async () => {
    setBusy(true);
    try {
      await switchBack();
      navigate("/admin/users");
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 border-b border-warning-line bg-warning-soft px-5 py-2 text-[13px] text-ink sm:px-8 2xl:px-10" role="status">
      <Eye size={15} className="shrink-0 text-warning" />
      <span className="min-w-0 flex-1">
        Viewing Ferrero as <strong className="font-semibold">{user.full_name}</strong> ({user.job_title}).
        <span className="hidden md:inline"> Changes are recorded as {user.acting_by.full_name} as {user.full_name}.</span>
      </span>
      <button type="button" onClick={back} disabled={busy}
        className="inline-flex h-7 items-center gap-1.5 rounded-md border border-line-strong bg-surface px-2.5 text-[12.5px] font-medium text-ink shadow-card transition-colors hover:bg-surface-2 disabled:opacity-60">
        <Undo2 size={14} /> {busy ? "Returning…" : `Return to ${user.acting_by.full_name}`}
      </button>
    </div>
  );
}

function NavItem({ to, label, icon: IconCmp, end }: { to: string; label: string; icon: Icon; end?: boolean }) {
  return (
    <NavLink to={to} end={end}
      className={({ isActive }) => clsx(
        "group relative flex h-10 items-center gap-3 rounded-lg px-3 text-[14px] transition-colors",
        isActive ? "bg-sidebar-2 font-medium text-on-brand" : "text-sidebar-muted hover:bg-sidebar-2 hover:text-on-brand",
      )}>
      {({ isActive }) => (
        <>
          <span aria-hidden className={clsx("absolute inset-y-2.5 -start-3 w-[3px] rounded-e-full transition-colors", isActive ? "bg-brand-accent" : "bg-transparent")} />
          <IconCmp size={18} strokeWidth={1.7} className={clsx("shrink-0 transition-colors", isActive ? "text-brand-accent" : "text-sidebar-muted group-hover:text-on-brand")} />
          {label}
        </>
      )}
    </NavLink>
  );
}

function NavLabel({ children }: { children: string }) {
  return <div className="px-3 pb-2 pt-1 text-[10.5px] font-semibold uppercase tracking-[0.16em] text-sidebar-muted/75">{children}</div>;
}

function Sidebar() {
  const { meta, user } = useSession();
  return (
    <div className="sidebar-surface flex h-full flex-col text-sidebar-ink">
      <Link to="/" className="flex h-16 shrink-0 items-center px-5" aria-label="Ferrero Case Intelligence: overview">
        <Brand onDark />
      </Link>
      <div className="brand-rule mx-5 opacity-60" />
      <nav className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto px-3 pt-5" aria-label="Main">
        <NavLabel>Workspace</NavLabel>
        {NAV.map((item) => <NavItem key={item.to} {...item} />)}
        {user?.is_admin && <>
          <div className="pt-5"><NavLabel>Administration</NavLabel></div>
          <NavItem to="/admin/users" label="Users" icon={UsersRound} />
        </>}
      </nav>
      <div className="flex flex-col gap-3 p-3">
        <UserMenu />
        {meta && (
          <div className="px-2 pb-1 text-[11.5px] leading-relaxed text-sidebar-muted/80">
            {meta.org_name}<br />Legal &amp; Brand Protection
          </div>
        )}
      </div>
    </div>
  );
}

function Topbar({ onMenu }: { onMenu: () => void }) {
  const { meta, theme, toggleTheme, openAssistant } = useSession();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);

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
    <header className="sticky top-0 z-30 flex h-16 shrink-0 items-center gap-2 border-b border-line bg-page/85 px-3 backdrop-blur-xl sm:gap-3 sm:px-8 2xl:px-10">
      <IconButton icon={Menu} className="lg:hidden" onClick={onMenu} aria-label="Open menu" />
      <form className="flex min-w-0 max-w-[440px] flex-1" onSubmit={(e) => { e.preventDefault(); submit(); }}>
        <label className="flex h-9 w-full items-center gap-2.5 rounded-lg border border-line-strong bg-surface px-3 text-[13.5px] shadow-card transition-colors focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/20">
          <Search size={15} className="shrink-0 text-muted" />
          <input ref={searchRef} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search cases, parties, marks…"
            className="min-w-0 flex-1 bg-transparent text-ink outline-none placeholder:text-muted" aria-label="Search cases" />
          <kbd className="hidden rounded border border-line bg-surface-2 px-1.5 py-px font-sans text-[11px] font-medium text-muted md:inline">Ctrl K</kbd>
        </label>
      </form>
      <div className="ms-auto flex items-center gap-1 sm:gap-1.5">
        {meta && (
          <span className="me-1 hidden items-center gap-2 text-[13px] text-ink-2 xl:inline-flex"
            title={meta.today_fixed ? "Reporting date (fixed for this demonstration)" : "Today"}>
            <CalendarDays size={15} className="text-muted" /> {fmtDate(meta.demo_today)}
          </span>
        )}
        <span aria-hidden className="mx-1 hidden h-5 w-px bg-line-strong xl:block" />
        <NotificationBell />
        <IconButton icon={theme === "dark" ? Sun : Moon} onClick={toggleTheme}
          aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"} />
        <Button variant="primary" icon={Sparkles} onClick={() => openAssistant(null)} className="ms-1.5 max-sm:w-9 max-sm:px-0" aria-label="Ask Ferrero">
          <span className="hidden sm:inline">Ask Ferrero</span>
        </Button>
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
      <div className="absolute inset-0 bg-scrim/45 backdrop-blur-[2px] animate-fade-in" onClick={closeAssistant} />
      <section role="dialog" aria-label="Ferrero assistant"
        className="absolute inset-y-0 end-0 flex w-[min(600px,100vw)] flex-col border-s border-line bg-page shadow-overlay animate-slide-in">
        <div className="flex h-16 shrink-0 items-center gap-3 border-b border-line bg-surface px-5">
          <Monogram size={34} />
          <div className="min-w-0 flex-1">
            <div className="text-[14.5px] font-semibold text-ink">Ferrero Assistant</div>
            <div className="truncate text-[12.5px] text-muted">
              {assistant.caseId ? `Focused on ${assistant.caseId}` : "All cases and documents you can access"} · as {user.full_name}
            </div>
          </div>
          <IconButton icon={ExternalLink} size={34} aria-label="Open the full assistant page" title="Open full page"
            onClick={() => { closeAssistant(); navigate(assistant.caseId ? `/assistant?case=${assistant.caseId}` : "/assistant"); }} />
          <IconButton icon={X} size={34} aria-label="Close" onClick={closeAssistant} />
        </div>
        <div className="min-h-0 flex-1">
          <Chat key={`${assistant.nonce}-${user.user_id}`} caseId={assistant.caseId} prompt={assistant.prompt} compact />
        </div>
      </section>
    </div>
  );
}
