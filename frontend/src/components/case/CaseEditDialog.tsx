import { useEffect, useMemo, useState } from "react";
import { Pencil } from "lucide-react";
import { ApiError, api, recordsChanged } from "../../api";
import { useToast } from "../../lib/toast";
import { useSession } from "../../session";
import type { CaseChanges, CaseDetail } from "../../types";
import { Dialog } from "../Dialog";
import { Field, FormError, FormSection, Segmented, SelectInput, TextArea, TextInput } from "../forms";
import { Button } from "../ui";
import { GateNotice, useOwners } from "./shared";

type Form = {
  status: string; stage: string; outcome: string; closed_date: string; next_action: string; next_action_due: string;
  next_hearing_date: string; lead_counsel_id: string; external_firm: string; priority: string; risk_rating: string;
};

const fromCase = (c: CaseDetail): Form => ({
  status: c.status, stage: c.stage, outcome: c.outcome, closed_date: c.closed_date ?? "", next_action: c.next_action ?? "",
  next_action_due: c.next_action_due ?? "", next_hearing_date: c.next_hearing_date ?? "", lead_counsel_id: c.lead_counsel_id,
  external_firm: c.external_firm ?? "", priority: c.priority, risk_rating: c.risk_rating ?? "",
});

/** Status, stage, next steps and ownership. Only what changed is sent; the server keeps the case consistent. */
export function CaseEditDialog({ c, open, onClose, onSaved }:
  { c: CaseDetail; open: boolean; onClose: () => void; onSaved: (c: CaseDetail) => void }) {
  const { user, meta } = useSession();
  const toast = useToast();
  const o = meta!.case_options;
  const today = meta!.demo_today;
  const owners = useOwners(c.access_group);
  const [form, setForm] = useState<Form>(() => fromCase(c));
  const [reason, setReason] = useState("");
  const [gate, setGate] = useState<string | null>(null);
  const [override, setOverride] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setForm(fromCase(c));
    setReason(""); setGate(null); setOverride(""); setError(null);
  }, [open, c]);

  const set = (patch: Partial<Form>) => setForm((f) => ({ ...f, ...patch }));
  const closed = form.status === "Closed";
  const setStatus = (status: string) => {
    if (status === form.status) return;
    if (status === "Closed") set({ status, stage: "Closed", outcome: c.status === "Closed" ? c.outcome : "", closed_date: c.closed_date ?? today });
    else set({ status, stage: c.status === "Open" ? c.stage : "", outcome: "Pending", closed_date: "" });
  };
  const ownerOptions = useMemo(() => {
    const list = owners.map((u) => ({ value: u.user_id, label: `${u.full_name} · ${u.job_title}` }));
    if (!owners.some((u) => u.user_id === c.lead_counsel_id)) list.unshift({ value: c.lead_counsel_id, label: c.lead_counsel });
    return list;
  }, [owners, c.lead_counsel_id, c.lead_counsel]);

  const changes = useMemo(() => {
    const base = fromCase(c);
    const out: Record<string, string | null> = {};
    for (const k of Object.keys(form) as (keyof Form)[]) {
      if (form[k] !== base[k]) out[k] = form[k].trim() === "" ? null : form[k].trim();
    }
    if (closed) { delete out.next_action; delete out.next_action_due; delete out.next_hearing_date; }
    return out as CaseChanges;
  }, [form, c, closed]);

  const save = async () => {
    if (!user) return;
    if (!Object.keys(changes).length) { onClose(); return; }
    if (gate && !override.trim()) { setError("Give the reason for going ahead, or cancel."); return; }
    setBusy(true);
    setError(null);
    try {
      const res = await api.updateCase(c.case_id, changes, reason, gate ? override : undefined);
      onSaved(res.case);
      recordsChanged();
      toast("success", `${c.case_id} updated: ${res.changes.length} change${res.changes.length === 1 ? "" : "s"} recorded in the audit trail.`);
      onClose();
    } catch (e) {
      if (e instanceof ApiError && e.code === "consultation_required") setGate(e.message);
      else setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const n = Object.keys(changes).length;
  return (
    <Dialog open={open} onClose={onClose} busy={busy} icon={<Pencil size={17} />} title={`Update ${c.case_id}`} subtitle={c.title}
      footer={<>
        <span className="me-auto text-[12px] text-muted">{n ? `${n} change${n === 1 ? "" : "s"}` : "No changes yet"}</span>
        <Button variant="ghost" onClick={onClose} disabled={busy}>Cancel</Button>
        <Button variant="primary" onClick={save} disabled={busy || !n}>{busy ? "Saving…" : gate ? "Go ahead and save" : "Save changes"}</Button>
      </>}>
      {gate && <GateNotice message={gate} reason={override} setReason={setOverride} />}
      <FormError>{error}</FormError>
      <FormSection title="Status">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Status" className="sm:col-span-2" group>
            <Segmented label="Status" value={form.status} onChange={setStatus}
              options={[{ value: "Open", label: "Open" }, { value: "Closed", label: "Closed" }]} />
          </Field>
          <Field label="Stage">
            <SelectInput value={form.stage} onChange={(e) => set({ stage: e.target.value })}
              options={closed ? o.stages_closed : o.stages_open} placeholder={form.stage ? undefined : "Choose the stage"} />
          </Field>
          {closed ? (
            <>
              <Field label="Outcome">
                <SelectInput value={form.outcome === "Pending" ? "" : form.outcome} onChange={(e) => set({ outcome: e.target.value })}
                  options={o.outcomes} placeholder="Choose the outcome" />
              </Field>
              <Field label="Closed on">
                <TextInput type="date" value={form.closed_date} max={today} min={c.opened_date} onChange={(e) => set({ closed_date: e.target.value })} />
              </Field>
            </>
          ) : (
            <Field label="Next hearing" optional>
              <TextInput type="date" value={form.next_hearing_date} onChange={(e) => set({ next_hearing_date: e.target.value })} />
            </Field>
          )}
        </div>
        {!closed && o.enforcement_stages.includes(form.stage) && !o.enforcement_stages.includes(c.stage) && (
          <p className="mt-3 text-[12.5px] text-ink-2">Moving to <strong className="font-medium text-ink">{form.stage}</strong> starts enforcement.
            {c.consultation_required ? " This case needs business consultation first." : ""}</p>
        )}
      </FormSection>
      {!closed && (
        <FormSection title="Next step">
          <div className="grid gap-4 sm:grid-cols-[1fr_180px]">
            <Field label="Next action" optional>
              <TextInput value={form.next_action} onChange={(e) => set({ next_action: e.target.value })} maxLength={200}
                placeholder="e.g. Follow up on cease-and-desist response" />
            </Field>
            <Field label="Due" optional hint="The owner is reminded before and on this date.">
              <TextInput type="date" value={form.next_action_due} onChange={(e) => set({ next_action_due: e.target.value })} />
            </Field>
          </div>
        </FormSection>
      )}
      <FormSection title="Ownership and priority">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Case owner (lead counsel)">
            <SelectInput value={form.lead_counsel_id} onChange={(e) => set({ lead_counsel_id: e.target.value })} options={ownerOptions} />
          </Field>
          <Field label="External firm" optional>
            <TextInput value={form.external_firm} onChange={(e) => set({ external_firm: e.target.value })} maxLength={200} />
          </Field>
          <Field label="Legal priority" group>
            <Segmented label="Legal priority" value={form.priority} onChange={(v) => set({ priority: v })} size="sm"
              options={o.levels.map((l) => ({ value: l, label: l }))} />
          </Field>
          <Field label="Risk rating" group>
            <Segmented label="Risk rating" value={form.risk_rating} onChange={(v) => set({ risk_rating: v })} size="sm"
              options={[...o.levels.map((l) => ({ value: l, label: l })), { value: "", label: "Not rated" }]} />
          </Field>
        </div>
      </FormSection>
      <FormSection title="Audit trail">
        <Field label="Reason for the change" optional hint="Saved with your name, the time and every value changed, before and after.">
          <TextArea value={reason} onChange={(e) => setReason(e.target.value)} rows={2} maxLength={2000} />
        </Field>
      </FormSection>
    </Dialog>
  );
}
