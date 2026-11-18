import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Repeat, Search } from "lucide-react";
import { useToast } from "../lib/toast";
import { useSession } from "../session";
import { Dialog } from "./Dialog";
import { FormError } from "./forms";
import { Avatar } from "./UserMenu";

const GROUP_ORDER = ["Legal-Ops", "Leadership", "Legal-UAE", "Legal-KSA", "Legal-MENA", "Procurement"];

/** The administrator picks a user and sees the portal exactly as they do, until switching back. */
export function SwitchUserDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { users, user, switchTo } = useSession();
  const navigate = useNavigate();
  const toast = useToast();
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { if (open) { setQ(""); setError(null); setBusy(null); } }, [open]);

  const groups = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const list = users.filter((u) => !u.admin && u.active !== false && u.case_groups.length > 0 &&
      (!needle || [u.full_name, u.job_title, u.entra_group, u.country].some((v) => v?.toLowerCase().includes(needle))));
    return GROUP_ORDER.map((g) => ({ group: g, people: list.filter((u) => u.entra_group === g) })).filter((g) => g.people.length);
  }, [users, q]);

  const pick = async (userId: string, name: string) => {
    setBusy(userId);
    setError(null);
    try {
      await switchTo(userId);
      onClose();
      navigate("/");
      toast("success", `You are now viewing Ferrero as ${name}.`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} busy={busy !== null} icon={<Repeat size={17} />} title="Switch user"
      subtitle="See Ferrero exactly as another user does. Changes you make are recorded under your name and theirs.">
      <FormError>{error}</FormError>
      <label className="mb-4 flex items-center gap-2 rounded-xl border border-line-strong bg-surface px-3 py-2 text-[13.5px] focus-within:border-accent">
        <Search size={15} className="text-muted" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name, role or country" data-autofocus
          className="min-w-0 flex-1 bg-transparent text-ink outline-none placeholder:text-muted" aria-label="Find a user" />
      </label>
      {!groups.length && <p className="py-6 text-center text-[13px] text-muted">No user matches.</p>}
      <div className="grid gap-4">
        {groups.map(({ group, people }) => (
          <section key={group}>
            <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">{group}</div>
            <ul className="grid gap-1">
              {people.map((u) => {
                const current = u.user_id === user?.user_id;
                return (
                  <li key={u.user_id}>
                    <button type="button" disabled={current || busy !== null} onClick={() => pick(u.user_id, u.full_name)}
                      className="flex w-full items-center gap-3 rounded-xl border border-transparent px-2.5 py-2 text-start transition hover:border-line hover:bg-surface-2 disabled:cursor-default disabled:opacity-60">
                      <Avatar name={u.full_name} small />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[13.5px] font-medium text-ink">{u.full_name}</span>
                        <span className="block truncate text-[12px] text-ink-2">{u.job_title} · sees {u.access}</span>
                      </span>
                      <span className="shrink-0 text-[12px] font-medium text-accent-ink">
                        {current ? "Viewing now" : busy === u.user_id ? "Switching…" : "Switch"}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </div>
    </Dialog>
  );
}
