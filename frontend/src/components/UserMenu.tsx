import clsx from "clsx";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronsUpDown, Eye, KeyRound, LogOut, Repeat, ShieldAlert, Undo2, UsersRound } from "lucide-react";
import { ApiError, api } from "../api";
import { initials } from "../lib/format";
import { useToast } from "../lib/toast";
import { useSession } from "../session";
import { Dialog } from "./Dialog";
import { Field, FormError, TextInput } from "./forms";
import { SwitchUserDialog } from "./SwitchUserDialog";
import { Button } from "./ui";

export function Avatar({ name, small }: { name: string; small?: boolean }) {
  return (
    <span className={clsx("grid shrink-0 place-items-center rounded-full bg-gradient-to-br from-[#e8cf9a] to-[#9c7a3f] font-semibold text-[#141519]",
      small ? "size-7 text-[11px]" : "size-9 text-[12.5px]")}>
      {initials(name)}
    </span>
  );
}

/** The signed-in person at the bottom of the sidebar: their access, password, switching account and signing out. */
export function UserMenu() {
  const { user, signOut, switchBack } = useSession();
  const navigate = useNavigate();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [changing, setChanging] = useState(false);
  const [switching, setSwitching] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onDoc); document.removeEventListener("keydown", onKey); };
  }, [open]);
  if (!user) return null;

  const item = "flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-start text-[13px] text-sidebar-ink transition hover:bg-white/5";
  const acting = user.acting_by ?? null;
  const administrator = Boolean(user.is_admin || acting);  // the real person is the administrator
  const goBack = async () => {
    setOpen(false);
    try {
      await switchBack();
      navigate("/admin/users");
      toast("info", "You are back in the administrator's view.");
    } catch (e) {
      toast("error", (e as Error).message);
    }
  };
  return (
    <div ref={ref} className="relative">
      {open && (
        <div className="absolute bottom-full start-0 mb-2 w-full rounded-2xl border border-white/10 bg-sidebar-2 p-1.5 shadow-2xl animate-fade-up" role="menu" aria-label="Account">
          <div className="px-2.5 pb-2.5 pt-2">
            <div className="truncate text-[13.5px] font-medium text-white">{user.full_name}</div>
            <div className="truncate text-[11.5px] text-sidebar-muted">{user.email}</div>
            <div className="mt-2 text-[11.5px] leading-relaxed text-sidebar-muted">
              <span className="me-1.5 rounded-full border border-white/10 px-1.5 py-px text-[10px] text-sidebar-ink">{user.entra_group}</span>
              Sees {user.access}{user.can_edit ? "" : " (read only)"}.
            </div>
          </div>
          {acting && (
            <button type="button" role="menuitem" onClick={goBack}
              className="mb-1 flex w-full items-start gap-2.5 rounded-xl border border-accent/40 bg-accent/10 px-2.5 py-2 text-start text-[12px] leading-relaxed text-sidebar-ink">
              <Undo2 size={15} className="mt-0.5 shrink-0 text-accent" />
              <span>Viewing as {user.full_name}. <span className="font-medium text-white">Return to {acting.full_name}</span></span>
            </button>
          )}
          {!user.own_password && (
            <button type="button" role="menuitem" onClick={() => { setOpen(false); setChanging(true); }}
              className="mb-1 flex w-full items-start gap-2.5 rounded-xl border border-warning/30 bg-warning/10 px-2.5 py-2 text-start text-[12px] leading-relaxed text-sidebar-ink">
              <ShieldAlert size={15} className="mt-0.5 shrink-0 text-[var(--warning)]" />
              You are signed in with a temporary password. Please set a personal one.
            </button>
          )}
          <div className="border-t border-white/10 pt-1">
            {administrator && (
              <button type="button" role="menuitem" className={item} onClick={() => { setOpen(false); setSwitching(true); }}>
                <Eye size={15} className="text-sidebar-muted" /> Switch user
              </button>
            )}
            {user.is_admin && (
              <button type="button" role="menuitem" className={item} onClick={() => { setOpen(false); navigate("/admin/users"); }}>
                <UsersRound size={15} className="text-sidebar-muted" /> Users
              </button>
            )}
            {!administrator && <>
              <button type="button" role="menuitem" className={item} onClick={() => { setOpen(false); setChanging(true); }}>
                <KeyRound size={15} className="text-sidebar-muted" /> Change password
              </button>
              <button type="button" role="menuitem" className={item}
                onClick={async () => { setOpen(false); await signOut(); navigate("/login"); }}>
                <Repeat size={15} className="text-sidebar-muted" /> Switch account
              </button>
            </>}
            <button type="button" role="menuitem" className={item} onClick={() => { setOpen(false); navigate("/logout"); }}>
              <LogOut size={15} className="text-sidebar-muted" /> Sign out
            </button>
          </div>
        </div>
      )}
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-haspopup="menu"
        className="flex w-full items-center gap-3 rounded-2xl border border-white/10 bg-sidebar-2 p-2.5 text-start transition hover:border-white/20">
        <span className="relative">
          <Avatar name={user.full_name} />
          {!user.own_password && <span className="absolute -end-0.5 -top-0.5 size-2.5 rounded-full bg-warning ring-2 ring-sidebar-2" aria-label="Set a personal password" />}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[13.5px] font-medium text-white">{user.full_name}</span>
          <span className="block truncate text-[11.5px] text-sidebar-muted">
            {acting ? `Viewing as · ${user.entra_group}` : user.is_admin ? "Platform administrator" : `${user.entra_group} · ${user.job_title}`}
          </span>
        </span>
        <ChevronsUpDown size={15} className="text-sidebar-muted" />
      </button>
      <ChangePasswordDialog open={changing} onClose={() => setChanging(false)} />
      <SwitchUserDialog open={switching} onClose={() => setSwitching(false)} />
    </div>
  );
}

export function ChangePasswordDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { user, refreshUser } = useSession();
  const toast = useToast();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [again, setAgain] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) { setCurrent(""); setNext(""); setAgain(""); setError(null); } }, [open]);

  const save = async () => {
    if (next.length < 10) { setError("Use at least 10 characters for the new password."); return; }
    if (next !== again) { setError("The new passwords do not match."); return; }
    setBusy(true);
    setError(null);
    try {
      await api.changePassword(current, next);
      await refreshUser();
      toast("success", "Password changed. Other devices signed in to your account have been signed out.");
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "The password couldn't be changed. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} busy={busy} icon={<KeyRound size={17} />} title="Change your password"
      subtitle={user ? `${user.full_name} · ${user.email}` : undefined}
      footer={<>
        <Button variant="ghost" onClick={onClose} disabled={busy}>Cancel</Button>
        <Button variant="primary" onClick={save} disabled={busy || !current || !next || !again}>{busy ? "Saving…" : "Change password"}</Button>
      </>}>
      <form onSubmit={(e) => { e.preventDefault(); save(); }} className="grid gap-4">
        <FormError>{error}</FormError>
        {user && !user.own_password && (
          <p className="-mt-1 text-[12.5px] leading-relaxed text-ink-2">
            You are signed in with a temporary password. Please choose a personal password known only to you.
          </p>
        )}
        <Field label="Current password">
          <TextInput type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
        </Field>
        <Field label="New password" hint="At least 10 characters, without your name or e-mail address. A short sentence works well.">
          <TextInput type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />
        </Field>
        <Field label="New password again">
          <TextInput type="password" autoComplete="new-password" value={again} onChange={(e) => setAgain(e.target.value)} />
        </Field>
        <button type="submit" className="hidden" aria-hidden tabIndex={-1} />
      </form>
    </Dialog>
  );
}
