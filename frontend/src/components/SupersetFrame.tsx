import { useEffect, useRef, useState } from "react";
import { embedDashboard, type EmbeddedDashboard } from "@superset-ui/embedded-sdk";
import { AlertTriangle, LoaderCircle } from "lucide-react";
import { api } from "../api";

const LOAD_TIMEOUT_MS = 25_000;

/**
 * One embedded dashboard. The browser never signs in to the dashboard server: every load (and every
 * refresh before the token expires) asks Ferrero's backend for a short-lived guest token for this
 * persona, which carries the persona's row rules. Changing persona, dashboard or case re-embeds.
 */
export function SupersetFrame({ uuid, domain, userId, caseId, title, theme, blockedHint }: {
  uuid: string;
  domain: string;
  userId: string;
  caseId?: string | null;
  title: string;
  theme: "light" | "dark";
  blockedHint?: string | null;
}) {
  const mount = useRef<HTMLDivElement>(null);
  const handle = useRef<EmbeddedDashboard | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const el = mount.current;
    if (!el) return;
    let cancelled = false;
    let failed = false;
    setState("loading");
    setError(null);
    const fail = (message: string) => {
      if (cancelled || failed) return;
      failed = true;
      setError(message);
      setState("error");
    };
    const timer = window.setTimeout(() => fail(blockedHint ?? "The dashboard didn't finish loading. Please try again."), LOAD_TIMEOUT_MS);

    embedDashboard({
      id: uuid,
      supersetDomain: domain,
      mountPoint: el,
      iframeTitle: title,
      fetchGuestToken: async () => {
        try {
          return await api.guestToken(userId, uuid, caseId);
        } catch (e) {
          window.clearTimeout(timer);
          fail((e as Error).message || "This dashboard can't be opened right now.");
          throw e;
        }
      },
      dashboardUiConfig: { hideTitle: true, filters: { expanded: false } },
    })
      .then((d) => {
        window.clearTimeout(timer);
        if (cancelled) { d.unmount(); return; }
        handle.current = d;
        setState("ready");
        try { d.setThemeMode(theme === "dark" ? "dark" : "default"); } catch { /* older servers have no theme modes */ }
      })
      .catch(() => { window.clearTimeout(timer); fail("This dashboard can't be opened right now."); });

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      handle.current?.unmount();
      handle.current = null;
      el.replaceChildren();
    };
    // theme is applied separately below, without re-embedding
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uuid, domain, userId, caseId, title]);

  useEffect(() => {
    try { handle.current?.setThemeMode(theme === "dark" ? "dark" : "default"); } catch { /* not supported */ }
  }, [theme]);

  return (
    <div className="relative h-[calc(100dvh-15.5rem)] min-h-[560px] w-full bg-surface">
      <div ref={mount} className="h-full w-full [&>iframe]:h-full [&>iframe]:w-full [&>iframe]:border-0" />
      {state === "loading" && (
        <div className="absolute inset-0 grid place-items-center bg-surface">
          <div className="flex items-center gap-2 text-[13.5px] text-ink-2">
            <LoaderCircle size={16} className="animate-spin text-accent" /> Loading {title}…
          </div>
        </div>
      )}
      {state === "error" && (
        <div className="absolute inset-0 grid place-items-center bg-surface p-6">
          <div className="flex max-w-md flex-col items-center gap-3 text-center">
            <span className="grid size-11 place-items-center rounded-2xl bg-accent-soft text-accent-ink"><AlertTriangle size={20} /></span>
            <div className="text-[15px] font-semibold text-ink">This dashboard couldn't be shown</div>
            <p className="text-[13px] leading-relaxed text-ink-2">{error}</p>
          </div>
        </div>
      )}
    </div>
  );
}
