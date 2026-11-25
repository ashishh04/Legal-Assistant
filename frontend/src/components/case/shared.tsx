import clsx from "clsx";
import { useMemo, type ReactNode } from "react";
import { Handshake } from "lucide-react";
import { fmtBytes, fmtDate } from "../../lib/format";
import { useSession } from "../../session";
import type { User } from "../../types";
import { Field, TextArea } from "../forms";
import { StatusPill } from "../ui";

/** Who can own a case or a follow-up: people who can change cases and can see this case's country group. */
export function useOwners(accessGroup: string): User[] {
  const { users } = useSession();
  return useMemo(() => users.filter((u) => u.can_edit && u.can_own !== false && u.active !== false
    && u.case_groups.includes(accessGroup)), [users, accessGroup]);
}

/** High / Medium / Low as three bars plus the word (never colour alone). */
export function Level({ value, empty = "Not assessed" }: { value: string | null | undefined; empty?: string }) {
  const filled = value === "High" ? 3 : value === "Medium" ? 2 : value === "Low" ? 1 : 0;
  return (
    <span className="inline-flex items-center gap-2 whitespace-nowrap text-[13.5px] font-medium text-ink">
      <span className="flex items-end gap-[2px]" aria-hidden>
        {[1, 2, 3].map((i) => (
          <span key={i} className={clsx("w-[4px] rounded-[1.5px]", i <= filled ? "bg-accent" : "bg-line-strong")} style={{ height: 4 + i * 3 }} />
        ))}
      </span>
      {value ?? <span className="font-normal text-muted">{empty}</span>}
    </span>
  );
}

export function ConsultationBadge({ required, status }: { required: boolean | number | null; status: string | null }) {
  if (required == null) return <StatusPill kind="neutral">Not assessed</StatusPill>;
  if (!required) return <StatusPill kind="neutral">Not required</StatusPill>;
  if (status === "Cleared to proceed") return <StatusPill kind="good">Business cleared enforcement</StatusPill>;
  if (status === "Hold enforcement") return <StatusPill kind="critical">Business asked to hold enforcement</StatusPill>;
  return <StatusPill kind="pending">{status === "In progress" ? "Consultation in progress" : "Consultation not started"}</StatusPill>;
}

/** Whether enforcement on the case still waits for the business. */
export const awaitingBusiness = (c: { consultation_required: boolean | number | null; consultation_status: string | null }) =>
  Boolean(c.consultation_required) && c.consultation_status !== "Cleared to proceed";

/** Shown when a change would start enforcement before the business has cleared it. */
export function GateNotice({ message, reason, setReason }: { message: string; reason: string; setReason: (v: string) => void }) {
  return (
    <div className="mb-4 rounded-xl border border-warning-line bg-warning-soft p-4" role="alert">
      <div className="flex gap-3">
        <Handshake size={18} className="mt-0.5 shrink-0 text-warning" />
        <div>
          <div className="text-[14px] font-semibold text-ink">Business consultation comes first</div>
          <p className="mt-0.5 text-[13px] leading-relaxed text-ink-2">{message}</p>
        </div>
      </div>
      <Field label="Reason for going ahead without business clearance" className="mt-3"
        hint="Recorded in the audit trail as enforcement without business clearance.">
        <TextArea value={reason} onChange={(e) => setReason(e.target.value)} rows={2} data-autofocus
          placeholder="e.g. Counterfeit product is a health risk and must come off the shelves now" />
      </Field>
    </div>
  );
}

const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;

/** An audit value in plain words: dates, Yes/No, people's names, sizes, fingerprints. */
export function valueText(field: string, value: unknown, users: User[]): ReactNode {
  if (value == null || value === "") return <span className="text-muted">–</span>;
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (field === "size_bytes" && typeof value === "number") return fmtBytes(value);
  if (field === "sha256" && typeof value === "string")
    return <span className="font-mono text-[11.5px]" title={value}>{value.slice(0, 12)}…{value.slice(-8)}</span>;
  const text = String(value);
  if (ISO_DAY.test(text)) return fmtDate(text);
  if (/^U-\d{2,3}$/.test(text)) return users.find((u) => u.user_id === text)?.full_name ?? text;
  return text;
}
