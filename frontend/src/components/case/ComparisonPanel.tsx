import clsx from "clsx";
import { useEffect, useState, type ReactNode } from "react";
import { Camera, ExternalLink, History, ImageOff, Info, Scale } from "lucide-react";
import { api, recordsChanged } from "../../api";
import { fmtDate, fmtDateTime } from "../../lib/format";
import { useApi } from "../../lib/hooks";
import { useToast } from "../../lib/toast";
import { useSession } from "../../session";
import type { CaseDetail, ComparisonData, ComparisonEntry, EvidenceItem, SimilarityResult } from "../../types";
import { Dialog } from "../Dialog";
import { Field, FormError, FormSection, Segmented, TextArea, TextInput } from "../forms";
import { Button, Card, EmptyState, SectionTitle, StatusPill } from "../ui";
import { Level } from "./shared";

const pctText = (v: number | null | undefined) => (v == null ? "–" : `${Math.round(v * 100)}%`);

/** The registered mark beside the product as found, the assessment of how alike they are, and its history. */
export function ComparisonPanel({ c, onChanged, onAddPhoto }: { c: CaseDetail; onChanged: () => void; onAddPhoto: () => void }) {
  const { user } = useSession();
  const { data, error, reload } = useApi<ComparisonData | null>(
    () => (user ? api.comparison(c.case_id) : Promise.resolve(null)), [user?.user_id, c.case_id, c.counts.audit, c.counts.evidence]);
  const [recording, setRecording] = useState(false);
  const [shown, setShown] = useState<string | null>(null);

  if (error) return <Card className="p-6 text-[13.5px] text-critical">The comparison couldn't be loaded. Please try again.</Card>;
  if (!data) return <div className="py-16 text-center text-[13.5px] text-muted">Loading the comparison…</div>;

  const { mark, current, photos } = data;
  const photo = photos?.find((p) => p.evidence_id === (shown ?? current?.evidence_id)) ?? photos?.[0] ?? null;
  const changed = () => { reload(); onChanged(); recordsChanged(); };

  return (
    <div className="grid gap-4">
      <Card className="p-5">
        <SectionTitle aside={data.can_record && mark && (
          <Button variant="primary" icon={Scale} onClick={() => setRecording(true)}>{current ? "Update the assessment" : "Record the comparison"}</Button>
        )}>Visual trademark comparison</SectionTitle>
        <p className="-mt-1 mb-4 text-[12.5px] text-muted">The mark as registered, beside the product as found.</p>
        <div className="grid gap-4 md:grid-cols-2">
          <Frame label="Registered mark" caption={mark ? `${mark.mark_name} · ${mark.registration_no}` : "No registered mark on this case"}>
            {mark?.specimen
              ? <img src={api.markSpecimenUrl(mark.mark_id)} alt={`${mark.mark_name}, as registered`} className="size-full object-contain" />
              : <Placeholder icon={ImageOff} text="No specimen on file" />}
          </Frame>
          <Frame label="Infringing product" caption={photo ? `${photo.title}${photo.captured_on ? ` · ${fmtDate(photo.captured_on)}` : ""}` : current ? `Sign: ${current.infringing_sign}` : " "}
            link={photo ? api.evidenceFileUrl(photo.evidence_id) : undefined}>
            {photos === null ? <Placeholder icon={ImageOff} text="Photos are not available for your role" />
              : photo ? <img src={api.evidenceFileUrl(photo.evidence_id)} alt={photo.title} className="size-full object-contain" />
              : (
                <div className="grid size-full place-items-center p-6 text-center">
                  <div>
                    <Camera size={22} className="mx-auto text-muted" />
                    <p className="mt-2 text-[13px] text-ink-2">No photo of the product yet.</p>
                    {c.permissions.add_evidence && <Button className="mt-3" icon={Camera} onClick={onAddPhoto}>Add a photo</Button>}
                  </div>
                </div>
              )}
          </Frame>
        </div>
        {photos && photos.length > 1 && (
          <div className="mt-3 flex flex-wrap items-center gap-2" role="group" aria-label="Photo shown">
            <span className="text-[12px] text-muted">Photo shown:</span>
            {photos.map((p) => (
              <button key={p.evidence_id} type="button" onClick={() => setShown(p.evidence_id)} aria-pressed={photo?.evidence_id === p.evidence_id}
                title={p.title}
                className={clsx("size-12 overflow-hidden rounded-lg border-2 transition", photo?.evidence_id === p.evidence_id ? "border-accent" : "border-line hover:border-line-strong")}>
                <img src={api.evidenceFileUrl(p.evidence_id)} alt="" className="size-full object-cover" />
              </button>
            ))}
          </div>
        )}
        {mark && (
          <dl className="mt-4 grid gap-x-8 gap-y-3 border-t border-line pt-4 text-[13px] sm:grid-cols-4">
            <Fact label="Mark" value={<>{mark.mark_name} <span dir="rtl" className="text-ink-2">{mark.mark_name_ar}</span></>} />
            <Fact label="Registration" value={mark.registration_no} />
            <Fact label="Nice classes" value={mark.nice_classes} sub={mark.product_category} />
            <Fact label="Registered in" value={`${mark.registered_in.length} countries`} sub={mark.registered_in.join(", ")} />
          </dl>
        )}
      </Card>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="p-5 lg:col-span-2">
          <SectionTitle aside={current && <span className="text-[12px] text-muted">{current.comparison_id}</span>}>Assessment</SectionTitle>
          {current ? <Assessment entry={current} /> : (
            <EmptyState icon={Scale} title="Not assessed yet"
              action={data.can_record && mark ? <Button variant="primary" icon={Scale} onClick={() => setRecording(true)}>Record the comparison</Button> : undefined}>
              Record how alike the sign on the product and the registered mark look, sound and mean, and the likelihood of confusion.
            </EmptyState>
          )}
        </Card>
        <Card className="p-5">
          <SectionTitle>Indicators</SectionTitle>
          {data.indicators && current ? <Indicators sign={current.infringing_sign} result={data.indicators} />
            : <p className="text-[13px] text-muted">Shown once the sign on the product is recorded.</p>}
          {data.history.length > 1 && (
            <div className="mt-5 border-t border-line pt-4">
              <div className="mb-2 flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-[0.1em] text-muted"><History size={13} /> Earlier assessments</div>
              <ul className="space-y-2">
                {data.history.filter((h) => h.status === "Superseded").map((h) => (
                  <li key={h.comparison_id} className="text-[12.5px] text-ink-2">
                    <span className="font-medium text-ink">{h.comparison_id}</span> · {fmtDate(h.assessed_at.slice(0, 10))} · {h.assessed_by} ·
                    likelihood {h.overall.toLowerCase()}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      </div>

      {recording && data.mark && (
        <ComparisonDialog c={c} data={data} onClose={() => setRecording(false)} onSaved={() => { setRecording(false); changed(); }} />
      )}
    </div>
  );
}

function Frame({ label, caption, children, link }: { label: string; caption: string; children: ReactNode; link?: string }) {
  return (
    <figure className="min-w-0">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">{label}</span>
        {link && <a href={link} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[12px] font-medium text-accent-ink hover:underline">
          Open full size <ExternalLink size={12} /></a>}
      </div>
      <div className="aspect-[3/2] overflow-hidden rounded-xl border border-line bg-white">{children}</div>
      <figcaption className="mt-2 truncate text-[12.5px] text-ink-2" title={caption}>{caption}</figcaption>
    </figure>
  );
}

function Placeholder({ icon: Icon, text }: { icon: typeof ImageOff; text: string }) {
  return <div className="grid size-full place-items-center text-[13px] text-muted"><span className="flex items-center gap-2"><Icon size={16} /> {text}</span></div>;
}

function Fact({ label, value, sub }: { label: string; value: ReactNode; sub?: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-[12px] text-muted">{label}</dt>
      <dd className="mt-0.5 truncate font-medium text-ink">{value}</dd>
      {sub && <dd className="truncate text-[12px] text-ink-2" title={sub}>{sub}</dd>}
    </div>
  );
}

function SimilarityLevel({ value }: { value: string }) {
  return value === "None" ? <span className="text-[13px] font-medium text-ink">Not similar</span> : <Level value={value} />;
}

function Assessment({ entry }: { entry: ComparisonEntry }) {
  return (
    <>
      <div className="mb-4 flex flex-wrap items-center gap-4 rounded-xl border border-line bg-surface-2 p-4">
        <div>
          <div className="text-[12px] text-muted">Sign on the product</div>
          <div className="text-[20px] font-semibold tracking-[-0.01em] text-ink" dir="auto">{entry.infringing_sign}</div>
        </div>
        <div className="ms-auto text-end">
          <div className="text-[12px] text-muted">Likelihood of confusion</div>
          <div className="mt-1"><Level value={entry.overall} /></div>
        </div>
      </div>
      <dl className="grid gap-x-8 gap-y-3 text-[13px] sm:grid-cols-2">
        {([["Visual similarity", entry.visual], ["Phonetic similarity", entry.phonetic], ["Conceptual similarity", entry.conceptual]] as const).map(([label, v]) => (
          <div key={label} className="flex items-center justify-between gap-3 border-b border-line pb-2">
            <dt className="text-ink-2">{label}</dt><dd><SimilarityLevel value={v} /></dd>
          </div>
        ))}
        <div className="flex items-center justify-between gap-3 border-b border-line pb-2">
          <dt className="text-ink-2">Goods</dt><dd className="font-medium text-ink">{entry.goods}</dd>
        </div>
      </dl>
      {entry.notes && <p className="mt-4 whitespace-pre-line rounded-xl border-s-2 border-accent bg-accent-soft/40 px-3.5 py-2.5 text-[13px] leading-relaxed text-ink">{entry.notes}</p>}
      <p className="mt-3 text-[12px] text-muted">Assessed by {entry.assessed_by} · {fmtDateTime(entry.assessed_at)} · recorded in the audit trail</p>
    </>
  );
}

function Indicators({ sign, result }: { sign: string; result: SimilarityResult }) {
  return (
    <>
      <dl className="space-y-2 text-[13px]">
        <Row label="Compared" value={<span dir="auto">{sign} · {result.compared_with}</span>} />
        <Row label="Word similarity" value={pctText(result.word_similarity)} />
        <Row label="Letters different" value={result.letters_different ?? "–"} />
        <Row label="Sounds alike" value={result.sounds_alike ? "Yes" : "No"} />
        <Row label="Contains the mark" value={result.contains_mark ? "Yes" : "No"} />
      </dl>
      {result.indication && (
        <div className="mt-3 flex items-center gap-2">
          <span className="text-[12.5px] text-ink-2">Indication</span>
          <StatusPill kind={result.indication === "High" ? "warning" : result.indication === "Medium" ? "pending" : "neutral"}>{result.indication}</StatusPill>
        </div>
      )}
      <p className="mt-3 flex gap-1.5 text-[11.5px] leading-relaxed text-muted"><Info size={13} className="mt-0.5 shrink-0" />
        Indicative only, from the spelling and sound of the words; the assessment is the legal view.</p>
    </>
  );
}

function Row({ label, value }: { label: string; value: ReactNode }) {
  return <div className="flex items-center justify-between gap-3"><dt className="text-ink-2">{label}</dt><dd className="truncate font-medium text-ink">{value}</dd></div>;
}

function ComparisonDialog({ c, data, onClose, onSaved }: { c: CaseDetail; data: ComparisonData; onClose: () => void; onSaved: () => void }) {
  const { meta } = useSession();
  const toast = useToast();
  const choices = meta!.case_options.comparison;
  const cur = data.current;
  const [sign, setSign] = useState(cur?.infringing_sign ?? "");
  const [photo, setPhoto] = useState<string>(cur?.evidence_id ?? data.photos?.[0]?.evidence_id ?? "");
  const [visual, setVisual] = useState(cur?.visual ?? "");
  const [phonetic, setPhonetic] = useState(cur?.phonetic ?? "");
  const [conceptual, setConceptual] = useState(cur?.conceptual ?? "");
  const [goods, setGoods] = useState(cur?.goods ?? "");
  const [overall, setOverall] = useState(cur?.overall ?? "");
  const [notes, setNotes] = useState(cur?.notes ?? "");
  const [live, setLive] = useState<SimilarityResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {  // indicative similarity as the sign is typed
    if (!sign.trim()) { setLive(null); return; }
    const t = window.setTimeout(() => { api.similarity(data.mark!.mark_id, sign).then(setLive).catch(() => setLive(null)); }, 250);
    return () => window.clearTimeout(t);
  }, [sign, data.mark]);

  const save = async () => {
    const missing = [!sign.trim() && "the sign on the product", !visual && "visual similarity", !phonetic && "phonetic similarity",
      !conceptual && "conceptual similarity", !goods && "the goods", !overall && "the likelihood of confusion"].filter(Boolean);
    if (missing.length) { setError(`Choose ${missing.join(", ")}.`); return; }
    setBusy(true); setError(null);
    try {
      await api.recordComparison(c.case_id, { infringing_sign: sign.trim(), evidence_id: photo || null, visual, phonetic, conceptual, goods, overall,
        notes: notes.trim() || null });
      toast("success", `Trademark comparison recorded on ${c.case_id}.`);
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const seg = (label: string, value: string, set: (v: string) => void, options: string[], render?: (o: string) => string) => (
    <Field label={label} group>
      <Segmented label={label} value={value} size="sm" onChange={set} options={options.map((o) => ({ value: o, label: render ? render(o) : o }))} />
    </Field>
  );

  return (
    <Dialog open onClose={onClose} busy={busy} wide icon={<Scale size={17} />} title="Trademark comparison"
      subtitle={`${data.mark!.mark_name} (${data.mark!.registration_no}) against the sign on the product · ${c.case_id}`}
      footer={<>
        <span className="me-auto text-[12px] text-muted">Saved in the audit trail; an earlier assessment is kept as history.</span>
        <Button variant="ghost" onClick={onClose} disabled={busy}>Cancel</Button>
        <Button variant="primary" onClick={save} disabled={busy}>{busy ? "Saving…" : "Save the assessment"}</Button>
      </>}>
      <FormError>{error}</FormError>
      <FormSection title="What was found">
        <div className="grid gap-4 sm:grid-cols-[1fr_220px]">
          <Field label="Sign on the product" hint="The name or sign exactly as it appears on the product or listing.">
            <TextInput value={sign} onChange={(e) => setSign(e.target.value)} maxLength={120} dir="auto" data-autofocus placeholder="e.g. VELLORA" />
          </Field>
          <div className="rounded-xl border border-line bg-surface-2 p-3 text-[12.5px]">
            <div className="font-medium text-ink-2">Indicative similarity</div>
            {live?.indication ? (
              <div className="mt-1 text-ink">
                <span className="font-semibold">{live.indication}</span> · {pctText(live.word_similarity)} alike
                {live.sounds_alike ? " · sounds alike" : ""}
              </div>
            ) : <div className="mt-1 text-muted">Type the sign to see it</div>}
          </div>
        </div>
        {data.photos && data.photos.length > 0 && (
          <div className="mt-4">
            <div className="mb-1.5 text-[12.5px] font-medium text-ink-2">Photo compared</div>
            <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Photo compared">
              {data.photos.map((p: EvidenceItem) => (
                <button key={p.evidence_id} type="button" role="radio" aria-checked={photo === p.evidence_id} onClick={() => setPhoto(p.evidence_id)}
                  title={p.title} className={clsx("size-16 overflow-hidden rounded-lg border-2 transition", photo === p.evidence_id ? "border-accent" : "border-line hover:border-line-strong")}>
                  <img src={api.evidenceFileUrl(p.evidence_id)} alt={p.title} className="size-full object-cover" />
                </button>
              ))}
              <button type="button" role="radio" aria-checked={!photo} onClick={() => setPhoto("")}
                className={clsx("h-16 rounded-lg border-2 px-3 text-[12px] text-ink-2 transition", !photo ? "border-accent" : "border-line hover:border-line-strong")}>
                No photo
              </button>
            </div>
          </div>
        )}
      </FormSection>
      <FormSection title="Assessment">
        <div className="grid gap-4 sm:grid-cols-2">
          {seg("Visual similarity", visual, setVisual, choices.similarity, (o) => (o === "None" ? "Not similar" : o))}
          {seg("Phonetic similarity", phonetic, setPhonetic, choices.similarity, (o) => (o === "None" ? "Not similar" : o))}
          {seg("Conceptual similarity", conceptual, setConceptual, choices.similarity, (o) => (o === "None" ? "Not similar" : o))}
          {seg("Goods", goods, setGoods, choices.goods)}
          {seg("Likelihood of confusion", overall, setOverall, choices.overall)}
        </div>
        <Field label="Notes" optional className="mt-4">
          <TextArea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} maxLength={2000}
            placeholder="e.g. Same oval cream label, gold border and red lettering; one extra L in the name" />
        </Field>
      </FormSection>
    </Dialog>
  );
}
