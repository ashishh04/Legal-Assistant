import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronDown, ClipboardPlus } from "lucide-react";
import { api, recordsChanged } from "../../api";
import { addDays } from "../../lib/format";
import { useToast } from "../../lib/toast";
import { useSession } from "../../session";
import type { NewCase, RegisterOptions } from "../../types";
import { Dialog } from "../Dialog";
import { Field, FormError, FormSection, Segmented, SelectInput, TextArea, TextInput } from "../forms";
import { Button } from "../ui";
import { useOwners } from "./shared";

type Form = {
  mark_id: string; case_type: string; country: string; source_channel: string; opened_date: string;
  infringer_mode: "known" | "new"; infringer_id: string; infringer_name: string; infringer_type: string; infringer_city: string;
  lead_counsel_id: string; priority: string; next_action: string; next_action_due: string;
  court_id: string; claim: string; business_priority: string; relationship: string; consultation: "" | "yes" | "no"; details: string;
};

const blank = (today: string, o: RegisterOptions | null, userId: string): Form => ({
  mark_id: "", case_type: "", country: o?.countries.length === 1 ? o.countries[0].country : "", source_channel: "",
  opened_date: today, infringer_mode: "known", infringer_id: "", infringer_name: "", infringer_type: "", infringer_city: "",
  lead_counsel_id: userId, priority: "Medium", next_action: o?.default_next_action ?? "",
  next_action_due: addDays(today, o?.default_next_action_days ?? 7), court_id: "", claim: "", business_priority: "",
  relationship: "", consultation: "", details: "",
});

/** Register a new case: what was infringed, by whom, where, who owns it and the first step. It starts at Intake. */
export function RegisterCaseDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { user, meta } = useSession();
  const navigate = useNavigate();
  const toast = useToast();
  const today = meta!.demo_today;
  const [o, setO] = useState<RegisterOptions | null>(null);
  const [form, setForm] = useState<Form>(() => blank(today, null, user?.user_id ?? ""));
  const [more, setMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (patch: Partial<Form>) => setForm((f) => ({ ...f, ...patch }));

  useEffect(() => {
    if (!open) return;
    setError(null); setMore(false);
    api.registerOptions().then((opts) => { setO(opts); setForm(blank(today, opts, user?.user_id ?? "")); })
      .catch((e) => setError((e as Error).message));
  }, [open, today, user?.user_id]);

  const country = o?.countries.find((c) => c.country === form.country);
  const owners = useOwners(country?.access_group ?? "");
  const infringers = useMemo(() => (o?.infringers ?? []).filter((i) => i.country === form.country), [o, form.country]);
  const courts = useMemo(() => (o?.courts ?? []).filter((c) => c.country === form.country), [o, form.country]);
  const mode = infringers.length ? form.infringer_mode : "new";

  // keep the owner valid for the chosen country: the registrant when they cover it, otherwise the first counsel
  useEffect(() => {
    if (!country || !owners.length) return;
    if (!owners.some((u) => u.user_id === form.lead_counsel_id)) {
      set({ lead_counsel_id: owners.some((u) => u.user_id === user?.user_id) ? user!.user_id : owners[0].user_id });
    }
  }, [country, owners, form.lead_counsel_id, user]);

  const submit = async () => {
    if (!o) return;
    const missing = [!form.mark_id && "the mark", !form.country && "the country", !form.case_type && "the case type",
      !form.source_channel && "how it was reported",
      mode === "known" ? !form.infringer_id && "the infringer" : !form.infringer_name.trim() && "the infringer's name",
      mode === "new" && !form.infringer_type && "the infringer type"].filter(Boolean);
    if (missing.length) { setError(`Choose ${missing.join(", ")}.`); return; }
    const data: NewCase = {
      mark_id: form.mark_id, case_type: form.case_type, country: form.country, source_channel: form.source_channel,
      opened_date: form.opened_date || null, priority: form.priority, lead_counsel_id: form.lead_counsel_id || null,
      next_action: form.next_action.trim() || null, next_action_due: form.next_action.trim() ? form.next_action_due || null : null,
      court_id: form.court_id || null, claim_amount_local: form.claim ? Number(form.claim) : null,
      business_priority: form.business_priority || null, commercial_relationship: form.relationship || null,
      consultation_required: form.consultation === "" ? null : form.consultation === "yes", details: form.details.trim() || null,
      ...(mode === "known" ? { infringer_id: form.infringer_id }
        : { infringer_name: form.infringer_name.trim(), infringer_type: form.infringer_type, infringer_city: form.infringer_city.trim() || null }),
    };
    setBusy(true); setError(null);
    try {
      const res = await api.registerCase(data);
      recordsChanged();
      toast("success", `${res.case_id} registered and assigned to ${res.case.lead_counsel}.`);
      onClose();
      navigate(`/cases/${res.case_id}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} busy={busy} wide icon={<ClipboardPlus size={17} />} title="Register a case"
      subtitle="Record a new infringement. It starts at Intake with an owner, and every step after is in its audit trail."
      footer={<>
        <span className="me-auto text-[12.5px] text-muted">The owner is notified and reminded of the first step.</span>
        <Button variant="ghost" onClick={onClose} disabled={busy}>Cancel</Button>
        <Button variant="primary" onClick={submit} disabled={busy || !o}>{busy ? "Registering…" : "Register case"}</Button>
      </>}>
      <FormError>{error}</FormError>
      {!o && !error && <p className="py-12 text-center text-[13.5px] text-muted">Loading…</p>}
      {o && <>
        <FormSection title="The infringement">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Mark infringed">
              <SelectInput value={form.mark_id} onChange={(e) => set({ mark_id: e.target.value })} placeholder="Choose the mark" data-autofocus
                options={o.marks.map((m) => ({ value: m.mark_id, label: `${m.mark_name} · ${m.product_category}` }))} />
            </Field>
            <Field label="Case type">
              <SelectInput value={form.case_type} onChange={(e) => set({ case_type: e.target.value })} options={o.case_types} placeholder="Choose the type" />
            </Field>
            <Field label="Country">
              <SelectInput value={form.country} onChange={(e) => set({ country: e.target.value, infringer_id: "", court_id: "" })}
                options={o.countries.map((c) => c.country)} placeholder="Choose the country" />
            </Field>
            <Field label="Reported through">
              <SelectInput value={form.source_channel} onChange={(e) => set({ source_channel: e.target.value })} options={o.sources} placeholder="Choose the source" />
            </Field>
          </div>
        </FormSection>

        <FormSection title="Infringer">
          {infringers.length > 0 && (
            <Segmented label="Infringer" value={mode} size="sm" onChange={(v) => set({ infringer_mode: v })}
              options={[{ value: "known", label: "Already on record" }, { value: "new", label: "New infringer" }]} />
          )}
          <div className="mt-3 grid gap-4 sm:grid-cols-[2fr_1fr_1fr]">
            {mode === "known" ? (
              <Field label="Infringer" className="sm:col-span-3" hint={form.country ? undefined : "Choose the country first."}>
                <SelectInput value={form.infringer_id} onChange={(e) => set({ infringer_id: e.target.value })} disabled={!form.country}
                  options={infringers.map((i) => ({ value: i.infringer_id, label: `${i.name} · ${i.type}` }))} placeholder="Choose the infringer" />
              </Field>
            ) : <>
              <Field label="Name">
                <TextInput value={form.infringer_name} onChange={(e) => set({ infringer_name: e.target.value })} maxLength={200}
                  placeholder="Company, store, seller or website" />
              </Field>
              <Field label="Type">
                <SelectInput value={form.infringer_type} onChange={(e) => set({ infringer_type: e.target.value })} options={o.infringer_types} placeholder="Choose" />
              </Field>
              <Field label="City" optional>
                <TextInput value={form.infringer_city} onChange={(e) => set({ infringer_city: e.target.value })} maxLength={100} />
              </Field>
            </>}
          </div>
        </FormSection>

        <FormSection title="Owner and first step">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Case owner" hint={form.country ? `Counsel who cover ${form.country}.` : "Choose the country first."}>
              <SelectInput value={form.lead_counsel_id} onChange={(e) => set({ lead_counsel_id: e.target.value })} disabled={!form.country}
                options={owners.map((u) => ({ value: u.user_id, label: `${u.full_name} · ${u.job_title}` }))} />
            </Field>
            <Field label="Legal priority" group>
              <Segmented label="Legal priority" value={form.priority} size="sm" onChange={(v) => set({ priority: v })}
                options={o.levels.map((l) => ({ value: l, label: l }))} />
            </Field>
            <Field label="First action" optional>
              <TextInput value={form.next_action} onChange={(e) => set({ next_action: e.target.value })} maxLength={200} />
            </Field>
            <Field label="Due" optional hint="The owner is reminded before and on this date.">
              <TextInput type="date" value={form.next_action_due} min={form.opened_date} onChange={(e) => set({ next_action_due: e.target.value })} />
            </Field>
          </div>
        </FormSection>

        <button type="button" onClick={() => setMore((m) => !m)} aria-expanded={more}
          className="mb-6 inline-flex h-8 items-center gap-1.5 rounded-lg bg-surface-3 px-2.5 text-[13px] font-medium text-ink-2 transition-colors hover:text-ink">
          <ChevronDown size={15} className={more ? "rotate-180 transition-transform" : "transition-transform"} /> More details (optional)
        </button>
        {more && <>
          <FormSection title="Details">
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label="Reported on">
                <TextInput type="date" value={form.opened_date} max={today} onChange={(e) => set({ opened_date: e.target.value })} />
              </Field>
              <Field label="Court or authority" optional>
                <SelectInput value={form.court_id} onChange={(e) => set({ court_id: e.target.value })} disabled={!form.country}
                  options={courts.map((c) => ({ value: c.court_id, label: c.court_name }))} placeholder="Not yet" />
              </Field>
              <Field label={`Amount claimed${country ? ` (${country.currency})` : ""}`} optional>
                <TextInput type="number" min={0} step="any" value={form.claim} onChange={(e) => set({ claim: e.target.value })} />
              </Field>
            </div>
          </FormSection>
          <FormSection title="Commercial sensitivity">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Business priority" group>
                <Segmented label="Business priority" value={form.business_priority} size="sm" onChange={(v) => set({ business_priority: v })}
                  options={[...o.levels.map((l) => ({ value: l, label: l })), { value: "", label: "Not assessed" }]} />
              </Field>
              <Field label="Business consultation before enforcement" group>
                <Segmented label="Business consultation before enforcement" value={form.consultation} size="sm"
                  onChange={(v) => set({ consultation: v })}
                  options={[{ value: "yes", label: "Yes" }, { value: "no", label: "No" }, { value: "", label: "Not assessed" }]} />
              </Field>
              <Field label="Commercial relationship with the infringer" optional>
                <SelectInput value={form.relationship} onChange={(e) => set({ relationship: e.target.value })} options={o.relationships} placeholder="Not assessed" />
              </Field>
            </div>
          </FormSection>
        </>}

        <FormSection title="How it was reported">
          <Field label="Details" optional hint="Saved as the first entry in the case's audit trail.">
            <TextArea value={form.details} onChange={(e) => set({ details: e.target.value })} rows={2} maxLength={2000}
              placeholder="e.g. Our distributor saw lookalike jars on sale at two outlets in Amman" />
          </Field>
        </FormSection>
      </>}
    </Dialog>
  );
}
