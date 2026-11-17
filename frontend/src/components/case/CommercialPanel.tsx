import { useEffect, useState } from "react";
import { Handshake, Pencil } from "lucide-react";
import { api, recordsChanged } from "../../api";
import { useToast } from "../../lib/toast";
import { useSession } from "../../session";
import type { CaseChanges, CaseDetail } from "../../types";
import { Dialog } from "../Dialog";
import { Field, FormError, FormSection, Segmented, SelectInput, TextArea, TextInput } from "../forms";
import { Button, Card, SectionTitle } from "../ui";
import { ConsultationBadge, Level } from "./shared";

export function CommercialCard({ c, onEdit }: { c: CaseDetail; onEdit?: () => void }) {
  const assessed = c.business_priority != null || c.consultation_required != null || c.commercial_relationship != null;
  return (
    <Card className="p-5">
      <SectionTitle aside={onEdit && (
        <Button variant="ghost" icon={Pencil} onClick={onEdit} className="-me-2 px-2.5 py-1.5 text-[12.5px]">{assessed ? "Edit" : "Assess"}</Button>
      )}>Commercial sensitivity</SectionTitle>
      {!assessed ? (
        <p className="text-[13px] leading-relaxed text-ink-2">
          Not assessed yet. Record the business priority, and whether the business must be consulted before enforcement,
          for example when the alleged infringer is also a customer or a commercial partner.
        </p>
      ) : (
        <dl className="grid gap-x-6 gap-y-4 text-[13px] sm:grid-cols-2">
          <div>
            <dt className="text-[12px] text-muted">Business priority</dt>
            <dd className="mt-1"><Level value={c.business_priority} /></dd>
          </div>
          <div>
            <dt className="text-[12px] text-muted">Consult the business before enforcement</dt>
            <dd className="mt-1 font-medium text-ink">
              {c.consultation_required == null ? <span className="font-normal text-muted">Not assessed</span> : c.consultation_required ? "Yes" : "No"}
            </dd>
          </div>
          <div>
            <dt className="text-[12px] text-muted">Commercial relationship</dt>
            <dd className="mt-1 font-medium text-ink">{c.commercial_relationship ?? <span className="font-normal text-muted">Not recorded</span>}</dd>
          </div>
          {c.consultation_required && (
            <div>
              <dt className="text-[12px] text-muted">Consultation</dt>
              <dd className="mt-1"><ConsultationBadge required={c.consultation_required} status={c.consultation_status} /></dd>
              {c.consultation_contact && <dd className="mt-1 text-[12px] text-ink-2">With {c.consultation_contact}</dd>}
            </div>
          )}
          {c.consultation_notes && (
            <div className="sm:col-span-2">
              <dt className="text-[12px] text-muted">Business considerations</dt>
              <dd className="mt-1 whitespace-pre-line leading-relaxed text-ink-2">{c.consultation_notes}</dd>
            </div>
          )}
        </dl>
      )}
    </Card>
  );
}

type YesNo = "" | "yes" | "no";

/** Business priority and the business-consultation requirement, changed together and audited. */
export function BusinessDialog({ c, open, onClose, onSaved }:
  { c: CaseDetail; open: boolean; onClose: () => void; onSaved: (c: CaseDetail) => void }) {
  const { user, meta } = useSession();
  const toast = useToast();
  const o = meta!.case_options;
  const [priority, setPriority] = useState("");
  const [required, setRequired] = useState<YesNo>("");
  const [relationship, setRelationship] = useState("");
  const [status, setStatus] = useState("Not started");
  const [contact, setContact] = useState("");
  const [notes, setNotes] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setPriority(c.business_priority ?? "");
    setRequired(c.consultation_required == null ? "" : c.consultation_required ? "yes" : "no");
    setRelationship(c.commercial_relationship ?? "");
    setStatus(c.consultation_status ?? "Not started");
    setContact(c.consultation_contact ?? "");
    setNotes(c.consultation_notes ?? "");
    setReason("");
    setError(null);
  }, [open, c]);

  const save = async () => {
    if (!user) return;
    const want: CaseChanges = {
      business_priority: priority || null,
      consultation_required: required === "" ? null : required === "yes",
      commercial_relationship: relationship || null,
      consultation_contact: contact.trim() || null,
      consultation_notes: notes.trim() || null,
    };
    if (required === "yes") want.consultation_status = status;
    const current: Record<string, unknown> = c as unknown as Record<string, unknown>;
    const changes = Object.fromEntries(Object.entries(want).filter(([k, v]) => (current[k] ?? null) !== v)) as CaseChanges;
    if (!Object.keys(changes).length) { onClose(); return; }
    setBusy(true);
    setError(null);
    try {
      const res = await api.updateCase(c.case_id, changes, reason);
      onSaved(res.case);
      recordsChanged();
      toast("success", "Business assessment saved and recorded in the audit trail.");
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} busy={busy} icon={<Handshake size={18} />} title="Commercial sensitivity"
      subtitle={`${c.case_id} · ${c.infringer_name} (${c.infringer_type})`}
      footer={<>
        <Button variant="ghost" onClick={onClose} disabled={busy}>Cancel</Button>
        <Button variant="primary" onClick={save} disabled={busy}>{busy ? "Saving…" : "Save assessment"}</Button>
      </>}>
      <FormError>{error}</FormError>
      <FormSection title="Business view">
        <div className="grid gap-4">
          <Field label="Business priority" group>
            <Segmented label="Business priority" value={priority} onChange={setPriority}
              options={[...o.levels.map((l) => ({ value: l, label: l })), { value: "", label: "Not assessed" }]} />
          </Field>
          <Field label="Business consultation required before enforcement" group
            hint="Choose Yes when the alleged infringer is also a customer or a commercial partner: no notice, filing or takedown goes ahead until the business has agreed.">
            <Segmented<YesNo> label="Business consultation required" value={required} onChange={setRequired}
              options={[{ value: "yes", label: "Yes" }, { value: "no", label: "No" }, { value: "", label: "Not assessed" }]} />
          </Field>
          <Field label="Commercial relationship with the infringer" optional>
            <SelectInput value={relationship} onChange={(e) => setRelationship(e.target.value)} options={o.relationships} placeholder="Not recorded" />
          </Field>
        </div>
      </FormSection>
      {required === "yes" && (
        <FormSection title="Consultation">
          <div className="grid gap-4">
            <Field label="Status" group>
              <Segmented label="Consultation status" value={status} onChange={setStatus} size="sm"
                options={o.consultation_statuses.map((s) => ({ value: s, label: s }))} />
            </Field>
            <Field label="Business contact" optional hint="Who in the business is consulted, e.g. the key-account or country manager.">
              <TextInput value={contact} onChange={(e) => setContact(e.target.value)} maxLength={200} placeholder="Name and role" />
            </Field>
          </div>
        </FormSection>
      )}
      <FormSection title="Notes">
        <div className="grid gap-4">
          <Field label="Business considerations" optional>
            <TextArea value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={2000} rows={3}
              placeholder="e.g. Top-10 distributor in the UAE; renewal talks in Q1. Agree the approach with the commercial director." />
          </Field>
          <Field label="Reason for the change" optional hint="Recorded in the audit trail with your name and the time.">
            <TextInput value={reason} onChange={(e) => setReason(e.target.value)} maxLength={2000} />
          </Field>
        </div>
      </FormSection>
    </Dialog>
  );
}
