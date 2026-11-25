import clsx from "clsx";
import { Download, History, ShieldAlert, ShieldCheck } from "lucide-react";
import { api } from "../../api";
import { fmtDate } from "../../lib/format";
import { useApi } from "../../lib/hooks";
import { AUDIT_ACTIONS } from "../../lib/labels";
import { useSession } from "../../session";
import type { AuditEntry, AuditTrail, CaseDetail } from "../../types";
import { Pagination, usePagination } from "../Pagination";
import { Avatar, Callout, Card, EmptyState, SectionTitle, buttonCls } from "../ui";
import { valueText } from "./shared";

/** Every change to the case: who, when, each value before and after, and why. */
export function AuditPanel({ c }: { c: CaseDetail }) {
  const { user } = useSession();
  const { data, error } = useApi<AuditTrail | null>(
    () => (user ? api.audit(c.case_id) : Promise.resolve(null)), [user?.user_id, c.case_id, c.counts.audit]);
  const entries = data?.entries ?? [];
  const pager = usePagination(entries, 10, c.case_id);
  const integrity = data?.integrity;

  return (
    <Card className="p-6">
      <SectionTitle aside={user && entries.length > 0 && (
        <a href={api.auditCsvUrl(c.case_id)} className={buttonCls("secondary", "sm")}>
          <Download size={14} /> Download CSV
        </a>
      )}>Audit trail</SectionTitle>
      <p className="-mt-1 mb-5 max-w-3xl text-[13.5px] leading-relaxed text-ink-2">
        Every change to this case is recorded with who made it, when, and each value before and after. Entries can't be
        edited or deleted, and each one is sealed to the one before it, so any tampering shows.
      </p>
      {integrity && (
        <div role={integrity.ok ? undefined : "alert"} className="mb-6">
          <Callout tone={integrity.ok ? "good" : "critical"} icon={integrity.ok ? ShieldCheck : ShieldAlert}
            title={integrity.ok ? "Tamper check passed" : "Tamper check failed"}>
            {integrity.ok
              ? `All ${integrity.entries} entries in the trail (every case) are intact and in order.`
              : `Entry ${integrity.first_bad}: ${integrity.problem}. Report this to Legal Operations.`}
          </Callout>
        </div>
      )}
      {error && <p className="text-[13px] text-critical-ink">The audit trail couldn't be loaded. Please try again.</p>}
      {!data && !error && <p className="py-8 text-center text-[13px] text-muted">Loading the audit trail…</p>}
      {data && !entries.length && (
        <EmptyState plain icon={History} title="No changes recorded yet">
          The case is as imported from the case tracker. Changes to its details, evidence and follow-ups will appear here.
        </EmptyState>
      )}
      <ol className="relative">
        {pager.slice.map((e, i) => {
          const day = e.at.slice(0, 10);
          const prev = pager.slice[i - 1];
          return (
            <li key={e.entry_id}>
              {(!prev || prev.at.slice(0, 10) !== day) && (
                <div className="mb-3 mt-1 flex items-center gap-3 text-[12.5px] font-semibold text-ink-2">
                  {fmtDate(new Date(e.at).toISOString().slice(0, 10))}<span aria-hidden className="h-px flex-1 bg-line" />
                </div>
              )}
              <Entry e={e} />
            </li>
          );
        })}
      </ol>
      <Pagination state={pager} noun="entries" compact />
    </Card>
  );
}

function Entry({ e }: { e: AuditEntry }) {
  const { users } = useSession();
  const override = e.action === "business.override";
  const time = new Date(e.at).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  return (
    <div className={clsx("mb-3 flex gap-3.5 rounded-lg border p-4", override ? "border-warning-line bg-warning-soft/60" : "border-line bg-surface")}>
      <Avatar name={e.actor_name} size={36} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-x-2 text-[13.5px]">
          <span className="font-semibold text-ink">{e.actor_name}</span>
          <span className="text-[12.5px] text-muted">{e.actor_role}</span>
          <span className="tabular ms-auto text-[12.5px] text-muted" title={e.at}>{time}</span>
        </div>
        <div className="mt-0.5 text-[13.5px] text-ink-2">
          <span>{AUDIT_ACTIONS[e.action] ?? e.action}</span>
          {e.ref_id && <span className="ms-1.5 text-[12.5px] text-muted">{e.ref_id}</span>}
        </div>
        {e.changes.length > 0 && (
          <table className="mt-3 w-full overflow-hidden rounded-md text-[13px]">
            <tbody>
              {e.changes.map((ch) => (
                <tr key={ch.field} className="border-t border-line first:border-0">
                  <th scope="row" className="w-[34%] py-2 pe-4 text-start align-top font-normal text-muted">{ch.label}</th>
                  <td className="py-2 align-top text-ink-2">
                    {ch.old != null && ch.old !== "" && (
                      <><span className="line-through decoration-[var(--muted)]/60" dir="auto">{valueText(ch.field, ch.old, users)}</span><span className="mx-1.5 text-muted">→</span></>
                    )}
                    <span className="font-medium text-ink" dir="auto">{valueText(ch.field, ch.new, users)}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {e.reason && <p className="mt-3 border-s-2 border-accent ps-3 text-[13.5px] leading-relaxed text-ink-2" dir="auto">“{e.reason}”</p>}
        <div className="mt-3 font-mono text-[11px] text-muted" title={`Entry hash ${e.entry_hash}`}>{e.entry_id} · {e.entry_hash.slice(0, 16)}</div>
      </div>
    </div>
  );
}
