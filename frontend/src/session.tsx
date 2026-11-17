import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { ApiError, api } from "./api";
import { useLocalStorage } from "./lib/hooks";
import type { Me, Meta, PublicInfo, User } from "./types";

interface AssistantState {
  open: boolean;
  caseId: string | null;
  prompt: string | null;
  nonce: number; // bumps on every open, so the same case can be reopened fresh
}

export type AuthStatus = "loading" | "signed-out" | "signed-in";

interface Session {
  status: AuthStatus;
  /** Set when the last session ended without signing out (expired, or signed out elsewhere). */
  expired: boolean;
  publicInfo: PublicInfo | null;
  meta: Meta | null;
  users: User[];
  user: Me | null;
  signIn: (login: string, password: string, remember: boolean) => Promise<void>;
  signOut: () => Promise<void>;
  refreshUser: () => Promise<void>;
  theme: "light" | "dark";
  toggleTheme: () => void;
  assistant: AssistantState;
  openAssistant: (caseId?: string | null, prompt?: string | null) => void;
  closeAssistant: () => void;
  bootError: string | null;
}

const SessionContext = createContext<Session | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [expired, setExpired] = useState(false);
  const [user, setUser] = useState<Me | null>(null);
  const [publicInfo, setPublicInfo] = useState<PublicInfo | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [bootError, setBootError] = useState<string | null>(null);
  const [theme, setTheme] = useLocalStorage(
    "ferrero.theme",
    document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light",
  );
  const [assistant, setAssistant] = useState<AssistantState>({ open: false, caseId: null, prompt: null, nonce: 0 });

  /** After sign-in (or on load with a live session): the reference data every page uses. */
  const enter = useCallback(async (me: Me) => {
    const [m, u] = await Promise.all([api.meta(), api.users()]);
    setUser(me);
    setMeta(m);
    setUsers(u);
    setExpired(false);
    setStatus("signed-in");
  }, []);

  const leave = useCallback((sessionEnded: boolean) => {
    setUser(null);
    setMeta(null);
    setUsers([]);
    setAssistant((a) => ({ ...a, open: false }));
    setExpired(sessionEnded);
    setStatus("signed-out");
  }, []);

  useEffect(() => {
    api.publicInfo().then(setPublicInfo).catch(() => { /* the sign-in page still works without it */ });
    api.me()
      .then((me) => (me ? enter(me) : leave(false)))
      .catch((e: unknown) => {
        if (e instanceof ApiError && e.status === 401) leave(false);
        else setBootError((e as Error).message);
      });
  }, [enter, leave]);

  // any request answered 401 means the session is over: back to signed-out (the router sends the user to sign in)
  useEffect(() => {
    const onEnded = () => { if (status === "signed-in") leave(true); };
    window.addEventListener("ferrero:signed-out", onEnded);
    return () => window.removeEventListener("ferrero:signed-out", onEnded);
  }, [status, leave]);

  useEffect(() => { document.documentElement.setAttribute("data-theme", theme); }, [theme]);

  const signIn = useCallback(async (login: string, password: string, remember: boolean) => {
    const me = await api.login(login, password, remember);
    await enter(me);
  }, [enter]);

  const signOut = useCallback(async () => {
    try { await api.logout(); } finally { leave(false); }
  }, [leave]);

  const refreshUser = useCallback(async () => {
    const me = await api.me();
    if (me) setUser(me);
    else leave(true);
  }, [leave]);

  const toggleTheme = useCallback(() => setTheme(theme === "dark" ? "light" : "dark"), [theme, setTheme]);
  const openAssistant = useCallback((caseId: string | null = null, prompt: string | null = null) =>
    setAssistant((a) => ({ open: true, caseId, prompt, nonce: a.nonce + 1 })), []);
  const closeAssistant = useCallback(() => setAssistant((a) => ({ ...a, open: false })), []);

  const value = useMemo<Session>(() => ({
    status, expired, publicInfo, meta, users, user, signIn, signOut, refreshUser,
    theme: theme === "dark" ? "dark" : "light", toggleTheme, assistant, openAssistant, closeAssistant, bootError,
  }), [status, expired, publicInfo, meta, users, user, signIn, signOut, refreshUser, theme, toggleTheme, assistant,
    openAssistant, closeAssistant, bootError]);

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): Session {
  const s = useContext(SessionContext);
  if (!s) throw new Error("useSession outside SessionProvider");
  return s;
}
