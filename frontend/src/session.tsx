import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "./api";
import { useLocalStorage } from "./lib/hooks";
import type { Meta, User } from "./types";

interface AssistantState {
  open: boolean;
  caseId: string | null;
  prompt: string | null;
  nonce: number; // bumps on every open, so the same case can be reopened fresh
}

interface Session {
  meta: Meta | null;
  users: User[];
  user: User | null;
  setUserId: (id: string) => void;
  theme: "light" | "dark";
  toggleTheme: () => void;
  assistant: AssistantState;
  openAssistant: (caseId?: string | null, prompt?: string | null) => void;
  closeAssistant: () => void;
  bootError: string | null;
}

const SessionContext = createContext<Session | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [bootError, setBootError] = useState<string | null>(null);
  const [userId, setUserId] = useLocalStorage("ferrero.user", "U-08");
  const [theme, setTheme] = useLocalStorage(
    "ferrero.theme",
    document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light",
  );
  const [assistant, setAssistant] = useState<AssistantState>({ open: false, caseId: null, prompt: null, nonce: 0 });

  useEffect(() => {
    Promise.all([api.meta(), api.users()])
      .then(([m, u]) => { setMeta(m); setUsers(u); })
      .catch((e: Error) => setBootError(e.message));
  }, []);

  useEffect(() => { document.documentElement.setAttribute("data-theme", theme); }, [theme]);

  const user = users.find((u) => u.user_id === userId) ?? users.find((u) => u.user_id === "U-08") ?? users[0] ?? null;
  const toggleTheme = useCallback(() => setTheme(theme === "dark" ? "light" : "dark"), [theme, setTheme]);
  const openAssistant = useCallback((caseId: string | null = null, prompt: string | null = null) =>
    setAssistant((a) => ({ open: true, caseId, prompt, nonce: a.nonce + 1 })), []);
  const closeAssistant = useCallback(() => setAssistant((a) => ({ ...a, open: false })), []);

  const value = useMemo<Session>(() => ({
    meta, users, user, setUserId, theme: theme === "dark" ? "dark" : "light", toggleTheme,
    assistant, openAssistant, closeAssistant, bootError,
  }), [meta, users, user, setUserId, theme, toggleTheme, assistant, openAssistant, closeAssistant, bootError]);

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): Session {
  const s = useContext(SessionContext);
  if (!s) throw new Error("useSession outside SessionProvider");
  return s;
}
