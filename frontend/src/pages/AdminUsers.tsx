import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Copy, KeyRound, Lock, Pencil, Power, Repeat, Search, ShieldCheck, UserPlus, Wand2 } from "lucide-react";
import { api } from "../api";
import { Dialog } from "../components/Dialog";
import { Field, FormError, SelectInput, TextInput } from "../components/forms";
import { Avatar, Button, Card, Chip, EmptyState, PageHeader, SearchField, StatusPill } from "../components/ui";
import { fmtDateTime } from "../lib/format";
import { useApi } from "../lib/hooks";
import { useToast } from "../lib/toast";
import { useSession } from "../session";
import type { AdminUser, AdminUsers as Listing } from "../types";

/** A random temporary password: 14 characters from an alphabet without look-alikes (0/O, 1/l/I). */
export function generatePassword(): string {
  const alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const pick = (n: number) => Array.from(crypto.getRandomValues(new Uint32Array(n)), (x) => alphabet[x % alphabet.length]).join("");
  return `${pick(4)}-${pick(4)}-${pick(4)}`;
}

const PASSWORD_LABEL: Record<AdminUser["password"], [string, "good" | "pending" | "neutral" | "warning" | "locked"]> = {
  configured: ["Set on the server", "locked"],
  own: ["Own password", "good"],
  temporary: ["Temporary password", "pending"],
  starting: ["Starting password", "neutral"],
  "not set": ["No password yet", "warning"],
};

/** The platform administrator's page: everyone with an account, adding people, passwords, access and switching. */
export default function AdminUsers() {
  const { user, reloadUsers, switchTo } = useSession();
  const navigate = useNavigate();
  const toast = useToast();
  const { data, error, reload } = useApi<Listing | null>(() => (user?.is_admin ? api.adminUsers() : Promise.resolve(null)), [user?.user_id]);
  const [q, setQ] = useState("");
  const [editing, setEditing] = useState<AdminUser | "new" | null>(null);
  const [password, setPassword] = useState<AdminUser | null>(null);
  const [access, setAccess] = useState<AdminUser | null>(null);

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return (data?.users ?? []).filter((u) => !needle ||
      [u.full_name, u.email, u.job_title, u.entra_group, u.country].some((v) => v.toLowerCase().includes(needle)));
  }, [data, q]);

  if (!user?.is_admin) {
    return (
      <div className="mx-auto max-w-xl pt-6">
        <EmptyState icon={Lock} title="This page is for the platform administrator">
          {user?.acting_by ? "Return to the administrator's own view to manage users." : "Ask the administrator if you need an account changed."}
        </EmptyState>
      </div>
    );
  }

  const changed = async () => { reload(); await reloadUsers(); };
  const switchInto = async (u: AdminUser) => {
    try {
      await switchTo(u.user_id);
      navigate("/");
      toast("success", `You are now viewing Ferrero as ${u.full_name}.`);
    } catch (e) {
      toast("error", (e as Error).message);
    }
  };

  return (
    <>
      <PageHeader eyebrow="Administration" title="Users"
        subtitle="Add people, give temporary passwords, turn access off and on, and view the portal as any user."
        actions={<Button variant="primary" icon={UserPlus} onClick={() => setEditing("new")}>Add user</Button>} />

      <div className="mb-4 flex flex-wrap items-center gap-3 animate-fade-up">
        <SearchField icon={Search} value={q} onChange={setQ} placeholder="Name, e-mail, role or country" label="Find a user" className="flex-1 sm:max-w-[300px]" />
        {data && <span className="tabular text-[13px] text-muted">{data.users.length} accounts · {data.users.filter((u) => !u.active).length} disabled</span>}
      </div>

      {error && <Card className="mb-4 p-6 text-[14px] text-critical-ink">The users couldn't be loaded. Please try again.</Card>}
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1040px] table-fixed text-[13.5px]">
            <colgroup>
              <col className="w-[25%]" /><col className="w-[20%]" /><col className="w-[15%]" />
              <col className="w-[13%]" /><col className="w-[9%]" /><col className="w-[18%]" />
            </colgroup>
            <thead className="border-b border-line bg-surface-2 text-left text-[12.5px] text-muted">
              <tr>
                <th className="py-3 pe-3 ps-5 font-medium">Person</th>
                <th className="px-3 py-3 font-medium">Role</th>
                <th className="px-3 py-3 font-medium">Sign-in</th>
                <th className="whitespace-nowrap px-3 py-3 font-medium">Last signed in</th>
                <th className="px-3 py-3 font-medium">Access</th>
                <th className="py-3 pe-5 ps-3 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {!data && !error && <tr><td colSpan={6} className="px-4 py-10 text-center text-muted">Loading…</td></tr>}
              {shown.map((u) => {
                const admin = u.source === "administrator";
                const [label, kind] = PASSWORD_LABEL[u.password];
                return (
                  <tr key={u.user_id} className={`border-b border-line align-middle transition-colors last:border-0 hover:bg-surface-2 ${u.active ? "" : "opacity-70"}`}>
                    <td className="py-3 pe-3 ps-5">
                      <span className="flex items-center gap-3">
                        <Avatar name={u.full_name} size={34} />
                        <span className="min-w-0">
                          <span className="flex items-center gap-2">
                            <span className="truncate font-medium text-ink">{u.full_name}</span>
                            {u.source === "added" && <Chip tone="outline" className="px-1.5 py-0 text-[10.5px]">Added</Chip>}
                          </span>
                          <span className="block truncate text-[12.5px] text-muted">{u.email}</span>
                        </span>
                      </span>
                    </td>
                    <td className="px-3 py-3">
                      <span className="block truncate font-medium text-ink">{admin ? "Platform administrator" : u.entra_group}</span>
                      <span className="block truncate text-[12.5px] text-muted">{admin ? "All countries · user administration" : `${u.job_title}${u.country ? ` · ${u.country}` : ""}`}</span>
                    </td>
                    <td className="px-3 py-3"><StatusPill kind={kind}>{label}</StatusPill></td>
                    <td className="tabular whitespace-nowrap px-3 py-3 text-[13px] text-ink-2">{u.last_sign_in ? fmtDateTime(u.last_sign_in) : <span className="text-muted">Never</span>}</td>
                    <td className="px-3 py-3">{u.active ? <StatusPill kind="good">Active</StatusPill> : <StatusPill kind="critical">Disabled</StatusPill>}</td>
                    <td className="py-3 pe-4 ps-3">
                      {admin ? <span className="flex items-center justify-end gap-1.5 pe-1 text-[12.5px] text-muted"><ShieldCheck size={14} /> You</span> : (
                        <span className="flex flex-nowrap items-center justify-end gap-0.5 whitespace-nowrap">
                          {u.active && <Action icon={Repeat} label="Switch to" onClick={() => switchInto(u)} />}
                          <Action icon={KeyRound} label={u.password === "not set" ? "Set a password" : "Reset the password"} iconOnly onClick={() => setPassword(u)} />
                          {u.source === "added" && <Action icon={Pencil} label="Edit details" iconOnly onClick={() => setEditing(u)} />}
                          <Action icon={Power} label={u.active ? "Disable the account" : "Enable the account"} iconOnly onClick={() => setAccess(u)} />
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
      {data && !data.starting_password && (
        <p className="mt-4 max-w-3xl text-[13px] leading-relaxed text-muted">People from the company directory sign in once you set them a temporary password; until then, you can view the portal as them with Switch to.</p>
      )}

      {data && editing && <UserDialog listing={data} user={editing === "new" ? null : editing} onClose={() => setEditing(null)} onSaved={changed} />}
      {password && <PasswordDialog user={password} onClose={() => setPassword(null)} onSaved={changed} />}
      {access && <AccessDialog user={access} onClose={() => setAccess(null)} onSaved={changed} />}
    </>
  );
}

function Action({ icon: Icon, label, onClick, iconOnly = false }: { icon: typeof Repeat; label: string; onClick: () => void; iconOnly?: boolean }) {
  return (
    <button type="button" onClick={onClick} title={label} aria-label={label}
      className="inline-flex h-8 items-center gap-1.5 rounded-md px-2 text-[13px] font-medium text-ink-2 transition-colors hover:bg-surface-3 hover:text-ink">
      <Icon size={15} />{!iconOnly && label}
    </button>
  );
}

/** Shown once after a password is set: the details to pass on, with a copy button. */
function Credentials({ email, password }: { email: string; password: string }) {
  const toast = useToast();
  const text = `E-mail: ${email}\nTemporary password: ${password}`;
  return (
    <div className="rounded-xl border border-good-line bg-good-soft p-4">
      <div className="text-[14px] font-semibold text-ink">Share these sign-in details</div>
      <p className="mt-0.5 text-[13px] leading-relaxed text-ink-2">They are shown only now. The user is asked to choose a personal password when they first sign in.</p>
      <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[13.5px]">
        <dt className="text-muted">E-mail</dt><dd className="font-medium text-ink">{email}</dd>
        <dt className="text-muted">Temporary password</dt><dd className="font-mono text-[13px] font-medium text-ink">{password}</dd>
      </dl>
      <Button className="mt-3" icon={Copy} onClick={() => navigator.clipboard.writeText(text).then(() => toast("success", "Copied."), () => toast("error", "Couldn't copy: select the text instead."))}>
        Copy
      </Button>
    </div>
  );
}

function PasswordField({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <Field label="Temporary password" hint="At least 10 characters. The user is asked to change it when they first sign in.">
      <span className="flex gap-2">
        <TextInput value={value} onChange={(e) => onChange(e.target.value)} className="font-mono" autoComplete="off" spellCheck={false} />
        <Button icon={Wand2} onClick={() => onChange(generatePassword())}>Generate</Button>
      </span>
    </Field>
  );
}

function UserDialog({ listing, user, onClose, onSaved }: { listing: Listing; user: AdminUser | null; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [form, setForm] = useState({
    full_name: user?.full_name ?? "", email: user?.email ?? "", job_title: user?.job_title ?? "",
    entra_group: user?.entra_group ?? "", country: user?.country ?? "UAE", password: user ? "" : generatePassword(),
  });
  const [done, setDone] = useState<{ email: string; password: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (patch: Partial<typeof form>) => setForm((f) => ({ ...f, ...patch }));
  const role = listing.roles.find((r) => r.group === form.entra_group);

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      if (user) {
        await api.updateUser(user.user_id, { full_name: form.full_name, job_title: form.job_title, entra_group: form.entra_group, country: form.country });
        toast("success", `${form.full_name} updated.`);
        onSaved();
        onClose();
      } else {
        const added = await api.addUser(form);
        onSaved();
        setDone({ email: added.email, password: form.password });
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onClose={onClose} busy={busy} icon={user ? <Pencil size={17} /> : <UserPlus size={17} />}
      title={user ? `Edit ${user.full_name}` : done ? "User added" : "Add a user"}
      subtitle={user ? user.email : "They sign in with their work e-mail address and the temporary password below."}
      footer={done ? <Button variant="primary" onClick={onClose}>Done</Button> : <>
        <Button variant="ghost" onClick={onClose} disabled={busy}>Cancel</Button>
        <Button variant="primary" onClick={save} disabled={busy}>{busy ? "Saving…" : user ? "Save changes" : "Add user"}</Button>
      </>}>
      {done ? <Credentials {...done} /> : <>
        <FormError>{error}</FormError>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Full name"><TextInput value={form.full_name} onChange={(e) => set({ full_name: e.target.value })} maxLength={120} data-autofocus /></Field>
          <Field label="Work e-mail">
            <TextInput type="email" value={form.email} onChange={(e) => set({ email: e.target.value })} disabled={!!user} maxLength={200} />
          </Field>
          <Field label="Job title"><TextInput value={form.job_title} onChange={(e) => set({ job_title: e.target.value })} maxLength={120} placeholder="e.g. IP Counsel" /></Field>
          <Field label="Country">
            <SelectInput value={form.country} onChange={(e) => set({ country: e.target.value })} options={listing.countries} />
          </Field>
          <Field label="Role" className="sm:col-span-2" hint={role ? `Sees ${role.description}.` : "The role decides which cases and documents they see."}>
            <SelectInput value={form.entra_group} onChange={(e) => set({ entra_group: e.target.value })} placeholder="Choose the role"
              options={listing.roles.map((r) => ({ value: r.group, label: r.group }))} />
          </Field>
          {!user && <div className="sm:col-span-2"><PasswordField value={form.password} onChange={(password) => set({ password })} /></div>}
        </div>
      </>}
    </Dialog>
  );
}

function PasswordDialog({ user, onClose, onSaved }: { user: AdminUser; onClose: () => void; onSaved: () => void }) {
  const [password, setPassword] = useState(generatePassword());
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { setError(null); }, [password]);
  const save = async () => {
    setBusy(true);
    try {
      await api.setUserPassword(user.user_id, password);
      onSaved();
      setDone(true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open onClose={onClose} busy={busy} icon={<KeyRound size={17} />} title={`${user.password === "not set" ? "Set" : "Reset"} ${user.full_name}'s password`}
      subtitle="A temporary password; any session they have open ends."
      footer={done ? <Button variant="primary" onClick={onClose}>Done</Button> : <>
        <Button variant="ghost" onClick={onClose} disabled={busy}>Cancel</Button>
        <Button variant="primary" onClick={save} disabled={busy || !password}>{busy ? "Saving…" : "Set password"}</Button>
      </>}>
      {done ? <Credentials email={user.email} password={password} /> : <>
        <FormError>{error}</FormError>
        <PasswordField value={password} onChange={setPassword} />
      </>}
    </Dialog>
  );
}

function AccessDialog({ user, onClose, onSaved }: { user: AdminUser; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const turningOff = user.active;
  const save = async () => {
    setBusy(true);
    try {
      await api.updateUser(user.user_id, { active: !turningOff });
      toast("success", turningOff ? `${user.full_name}'s access is off.` : `${user.full_name}'s access is on again.`);
      onSaved();
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open onClose={onClose} busy={busy} icon={<Power size={17} />} title={turningOff ? `Disable ${user.full_name}?` : `Enable ${user.full_name}?`}
      footer={<>
        <Button variant="ghost" onClick={onClose} disabled={busy}>Cancel</Button>
        <Button variant="primary" onClick={save} disabled={busy}>{busy ? "Saving…" : turningOff ? "Disable" : "Enable"}</Button>
      </>}>
      <FormError>{error}</FormError>
      <p className="text-[13.5px] leading-relaxed text-ink-2">
        {turningOff
          ? "They are signed out at once and can't sign in, own cases or receive reminders until access is turned on again. Their past changes stay on record."
          : "They can sign in again with their current password, and can own cases and receive reminders."}
      </p>
    </Dialog>
  );
}
