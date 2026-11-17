import clsx from "clsx";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Camera, ChevronLeft, ChevronRight, CircleCheck, CloudUpload, Copy, Download, ExternalLink, FileImage, FileSpreadsheet,
  FileText, Fingerprint, Landmark, Lock, Mail, MapPin, Pencil, Receipt, Scale, ShieldAlert, ShieldCheck, Undo2, X,
} from "lucide-react";
import { api, recordsChanged, uploadEvidence } from "../../api";
import { fmtBytes, fmtDate, fmtDateTime } from "../../lib/format";
import { useApi } from "../../lib/hooks";
import { useToast } from "../../lib/toast";
import { useSession } from "../../session";
import type { CaseDetail, EvidenceDetails, EvidenceItem } from "../../types";
import { Dialog } from "../Dialog";
import { Field, FormError, SelectInput, TextArea, TextInput } from "../forms";
import { Button, Card, Chip, EmptyState, SectionTitle, StatusPill } from "../ui";

const IMAGE_EXT = /\.(jpe?g|png|webp|gif)$/i;

function categoryIcon(e: Pick<EvidenceItem, "category" | "content_type">) {
  switch (e.category) {
    case "Invoice": return Receipt;
    case "Correspondence with authorities": return Landmark;
    case "External counsel document": return Scale;
    case "Cease-and-desist letter": return Mail;
    case "Product photo": case "Screenshot": return FileImage;
    default: return e.content_type.includes("sheet") || e.content_type.includes("csv") ? FileSpreadsheet : FileText;
  }
}

export function EvidencePanel({ c, onChanged }: { c: CaseDetail; onChanged: () => void }) {
  const { user, meta } = useSession();
  const o = meta!.case_options;
  const { data, error, reload } = useApi<EvidenceItem[] | null>(
    () => (user && c.permissions.evidence ? api.evidence(c.case_id) : Promise.resolve(null)),
    [user?.user_id, c.case_id, c.permissions.evidence]);
  const [filter, setFilter] = useState("all");
  const [showWithdrawn, setShowWithdrawn] = useState(false);
  const [pending, setPending] = useState<File[] | null>(null);
  const [viewing, setViewing] = useState<string | null>(null);
  const [drag, setDrag] = useState(false);
  const browse = useRef<HTMLInputElement>(null);
  const camera = useRef<HTMLInputElement>(null);

  const items = useMemo(() => data ?? [], [data]);
  const active = items.filter((e) => e.status === "Active");
  const withdrawn = items.length - active.length;
  const counts = useMemo(() => {
    const m = new Map<string, number>();
    for (const e of active) m.set(e.category, (m.get(e.category) ?? 0) + 1);
    return m;
  }, [active]);
  const shown = (showWithdrawn ? items : active).filter((e) => filter === "all" || e.category === filter);
  const photos = shown.filter((e) => e.image);
  const files = shown.filter((e) => !e.image);
  const changed = useCallback(() => { reload(); onChanged(); recordsChanged(); }, [reload, onChanged]);

  if (!c.permissions.evidence) {
    return (
      <Card className="p-6">
        <p className="flex items-center gap-2 text-[13.5px] text-ink-2"><Lock size={15} /> Evidence and documents are not available for your role.</p>
      </Card>
    );
  }

  const choose = (list: FileList | null) => { if (list?.length) setPending(Array.from(list)); };

  return (
    <div className="flex flex-col gap-4">
      {c.permissions.add_evidence && (
        <div
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setDrag(false); }}
          onDrop={(e) => { e.preventDefault(); setDrag(false); choose(e.dataTransfer.files); }}
          className={clsx("relative flex flex-col items-center gap-3 rounded-2xl border-2 border-dashed px-6 py-7 text-center transition",
            drag ? "border-accent bg-accent-soft/60" : "border-line-strong bg-surface")}>
          <span className="grid size-12 place-items-center rounded-2xl bg-accent-soft text-accent-ink"><CloudUpload size={22} strokeWidth={1.7} /></span>
          <div>
            <div className="text-[15px] font-semibold text-ink">Add evidence to {c.case_id}</div>
            <p className="mx-auto mt-1 max-w-xl text-[13px] leading-relaxed text-ink-2">
              Drop photos of infringing products, cease-and-desist letters, correspondence with authorities, invoices,
              screenshots or external counsel documents here.
            </p>
          </div>
          <div className="flex flex-wrap justify-center gap-2">
            <Button variant="primary" icon={CloudUpload} onClick={() => browse.current?.click()}>Choose files</Button>
            <Button icon={Camera} onClick={() => camera.current?.click()}>Take a photo</Button>
          </div>
          <p className="text-[11.5px] text-muted">
            {o.accepted_types.charAt(0).toUpperCase() + o.accepted_types.slice(1)} · up to {o.evidence_max_mb} MB each ·
            every file is kept exactly as uploaded, with a SHA-256 fingerprint
          </p>
          <input ref={browse} type="file" multiple accept={o.accept} className="hidden" onChange={(e) => { choose(e.target.files); e.target.value = ""; }} />
          <input ref={camera} type="file" accept="image/*" capture="environment" className="hidden" onChange={(e) => { choose(e.target.files); e.target.value = ""; }} />
        </div>
      )}

      <Card className="p-5">
        <SectionTitle aside={<span className="text-[12px] text-muted">
          {active.length} item{active.length === 1 ? "" : "s"}{withdrawn ? ` · ${withdrawn} withdrawn` : ""}</span>}>
          Evidence &amp; documents
        </SectionTitle>
        {error && <p className="text-[13px] text-critical">The evidence list couldn't be loaded. Please try again.</p>}
        {items.length > 0 && (
          <div className="mb-4 flex flex-wrap items-center gap-1.5">
            {[["all", `All · ${active.length}`] as const, ...[...counts.entries()].map(([k, n]) => [k, `${k} · ${n}`] as const)].map(([k, label]) => (
              <button key={k} type="button" onClick={() => setFilter(k)} aria-pressed={filter === k}
                className={clsx("rounded-full border px-3 py-1 text-[12.5px] font-medium transition",
                  filter === k ? "border-primary bg-primary text-primary-ink" : "border-line bg-surface-2 text-ink-2 hover:text-ink")}>
                {label}
              </button>
            ))}
            {withdrawn > 0 && (
              <label className="ms-auto flex cursor-pointer items-center gap-2 text-[12.5px] text-ink-2">
                <input type="checkbox" checked={showWithdrawn} onChange={(e) => setShowWithdrawn(e.target.checked)} className="accent-[var(--accent)]" />
                Show withdrawn
              </label>
            )}
          </div>
        )}
        {data && items.length === 0 && (
          <EmptyState icon={FileImage} title="No evidence on file yet">
            Photos of the infringing products, letters, correspondence, invoices and screenshots added here stay with the case,
            each with who added it and when.
          </EmptyState>
        )}
        {!data && !error && <p className="py-8 text-center text-[13px] text-muted">Loading evidence…</p>}

        {photos.length > 0 && (
          <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
            {photos.map((e) => (
              <button key={e.evidence_id} type="button" onClick={() => setViewing(e.evidence_id)}
                className={clsx("group relative aspect-[4/3] overflow-hidden rounded-xl border border-line bg-surface-2 text-start",
                  e.status === "Withdrawn" && "opacity-55 grayscale")}>
                <img src={api.evidenceFileUrl(e.evidence_id)} alt={e.title} loading="lazy" decoding="async"
                  className="size-full object-cover transition duration-300 group-hover:scale-[1.03]" />
                <span className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/75 via-black/35 to-transparent px-3 pb-2.5 pt-8">
                  <span className="block truncate text-[12.5px] font-medium text-white">{e.title}</span>
                  <span className="block truncate text-[11px] text-white/75">
                    {[e.captured_on && fmtDate(e.captured_on), e.location].filter(Boolean).join(" · ") || e.category}
                  </span>
                </span>
                <span className="absolute start-2 top-2 rounded-md bg-black/55 px-1.5 py-0.5 text-[10.5px] font-medium text-white backdrop-blur">
                  {e.status === "Withdrawn" ? "Withdrawn" : e.evidence_id}
                </span>
              </button>
            ))}
          </div>
        )}

        {files.length > 0 && (
          <ul className="divide-y divide-line">
            {files.map((e) => {
              const Icon = categoryIcon(e);
              return (
                <li key={e.evidence_id}>
                  <button type="button" onClick={() => setViewing(e.evidence_id)}
                    className={clsx("flex w-full items-center gap-3 py-2.5 text-start transition hover:bg-surface-2/60", e.status === "Withdrawn" && "opacity-60")}>
                    <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-surface-2 text-ink-2"><Icon size={16} strokeWidth={1.7} /></span>
                    <span className="min-w-0 flex-1">
                      <span className="flex flex-wrap items-center gap-x-2 text-[13.5px]">
                        <span className="font-medium text-ink" dir="auto">{e.title}</span>
                        <span className="text-[12px] text-muted">{e.category}</span>
                      </span>
                      <span className="block truncate text-[12px] text-muted" dir="auto">
                        {e.file_name} · {e.file_label} · {fmtBytes(e.size_bytes)} · added by {e.uploaded_by}, {fmtDate(e.uploaded_at.slice(0, 10))}
                      </span>
                    </span>
                    {e.status === "Withdrawn" ? <StatusPill kind="neutral">Withdrawn</StatusPill>
                      : e.captured_on && <span className="hidden text-[12px] text-muted sm:block">{fmtDate(e.captured_on)}</span>}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </Card>

      {pending && <UploadDialog c={c} files={pending} onClose={() => setPending(null)} onUploaded={changed} />}
      {viewing && (
        <EvidenceViewer items={[...photos, ...files]} id={viewing} onNavigate={setViewing} onClose={() => setViewing(null)}
          canEdit={c.permissions.add_evidence} onChanged={changed} />
      )}
    </div>
  );
}

type Status = { state: "waiting" | "uploading" | "done" | "failed" | "invalid"; progress: number; message?: string };

function UploadDialog({ c, files, onClose, onUploaded }: { c: CaseDetail; files: File[]; onClose: () => void; onUploaded: () => void }) {
  const { user, meta } = useSession();
  const toast = useToast();
  const o = meta!.case_options;
  const allowed = useMemo(() => new Set(o.accept.split(",")), [o.accept]);
  const [list, setList] = useState(files);
  const allImages = list.every((f) => IMAGE_EXT.test(f.name) || /\.hei[cf]$/i.test(f.name));
  const [category, setCategory] = useState(allImages ? o.photo_categories[0] : "Other evidence");
  const [title, setTitle] = useState(files.length === 1 ? files[0].name.replace(/\.[^.]+$/, "") : "");
  const [capturedOn, setCapturedOn] = useState(meta!.demo_today);
  const [location, setLocation] = useState("");
  const [notes, setNotes] = useState("");
  const [status, setStatus] = useState<Record<number, Status>>({});
  const [busy, setBusy] = useState(false);
  const [finished, setFinished] = useState(false);
  const previews = useMemo(() => list.map((f) => (IMAGE_EXT.test(f.name) ? URL.createObjectURL(f) : null)), [list]);
  useEffect(() => () => previews.forEach((u) => u && URL.revokeObjectURL(u)), [previews]);

  const problem = (f: File) => {
    const ext = f.name.includes(".") ? `.${f.name.split(".").pop()!.toLowerCase()}` : "";
    if (!allowed.has(ext)) return `${ext || "This file type"} can't be added`;
    if (f.size > o.evidence_max_mb * 1024 * 1024) return `Larger than ${o.evidence_max_mb} MB`;
    if (f.size === 0) return "Empty file";
    return null;
  };
  const valid = list.filter((f) => !problem(f));

  const upload = async () => {
    if (!user || !valid.length) return;
    setBusy(true);
    let ok = 0;
    for (let i = 0; i < list.length; i++) {
      const f = list[i];
      if (problem(f) || status[i]?.state === "done") continue;
      setStatus((s) => ({ ...s, [i]: { state: "uploading", progress: 0 } }));
      const details: EvidenceDetails = {
        category, title: list.length === 1 ? title : undefined, captured_on: capturedOn || undefined,
        location: location || undefined, notes: notes || undefined,
      };
      try {
        await uploadEvidence(c.case_id, f, details, (p) => setStatus((s) => ({ ...s, [i]: { state: "uploading", progress: p } })));
        setStatus((s) => ({ ...s, [i]: { state: "done", progress: 1 } }));
        ok++;
      } catch (e) {
        setStatus((s) => ({ ...s, [i]: { state: "failed", progress: 0, message: (e as Error).message } }));
      }
    }
    setBusy(false);
    if (ok) onUploaded();
    const failed = valid.length - ok;
    if (!failed) {
      toast("success", `${ok} file${ok === 1 ? "" : "s"} added to ${c.case_id} and recorded in the audit trail.`);
      onClose();
    } else {
      setFinished(true);
      if (ok) toast("info", `${ok} of ${valid.length} files added. See the reasons for the others.`);
    }
  };

  return (
    <Dialog open onClose={onClose} busy={busy} wide icon={<CloudUpload size={18} />}
      title={`Add ${list.length === 1 ? "a file" : `${list.length} files`} to ${c.case_id}`}
      subtitle="The details apply to every file in this upload."
      footer={<>
        <Button variant="ghost" onClick={onClose} disabled={busy}>{finished ? "Close" : "Cancel"}</Button>
        {!finished && <Button variant="primary" icon={CloudUpload} onClick={upload} disabled={busy || !valid.length}>
          {busy ? "Uploading…" : `Upload ${valid.length} file${valid.length === 1 ? "" : "s"}`}</Button>}
      </>}>
      <div className="grid gap-6 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <ul className="flex max-h-[52vh] flex-col gap-2 overflow-y-auto pe-1">
          {list.map((f, i) => {
            const bad = problem(f);
            const s = status[i];
            return (
              <li key={`${f.name}-${i}`} className="flex items-center gap-3 rounded-xl border border-line bg-surface-2/60 p-2">
                {previews[i]
                  ? <img src={previews[i]!} alt="" className="size-12 shrink-0 rounded-lg object-cover" />
                  : <span className="grid size-12 shrink-0 place-items-center rounded-lg bg-surface text-ink-2"><FileText size={18} /></span>}
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[13px] font-medium text-ink" dir="auto" title={f.name}>{f.name}</span>
                  <span className={clsx("block text-[12px]", bad || s?.state === "failed" ? "text-critical" : "text-muted")}>
                    {bad ?? (s?.state === "failed" ? s.message : s?.state === "done" ? "Added" : fmtBytes(f.size))}
                  </span>
                  {s?.state === "uploading" && (
                    <span className="mt-1.5 block h-1.5 overflow-hidden rounded-full bg-line">
                      <span className="block h-full rounded-full bg-accent transition-[width]" style={{ width: `${Math.round(s.progress * 100)}%` }} />
                    </span>
                  )}
                </span>
                {s?.state === "done" ? <CircleCheck size={17} className="shrink-0 text-good" />
                  : !busy && !finished && (
                    <button type="button" aria-label={`Remove ${f.name}`} onClick={() => setList((l) => l.filter((_, j) => j !== i))}
                      className="grid size-7 shrink-0 place-items-center rounded-lg text-muted hover:bg-surface hover:text-ink"><X size={14} /></button>
                  )}
              </li>
            );
          })}
        </ul>
        <div className="grid content-start gap-4">
          <Field label="Category">
            <SelectInput value={category} onChange={(e) => setCategory(e.target.value)} options={o.evidence_categories} disabled={busy} />
          </Field>
          {list.length === 1 && (
            <Field label="Title">
              <TextInput value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} disabled={busy} />
            </Field>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={o.photo_categories.includes(category) ? "Taken on" : "Dated"} optional>
              <TextInput type="date" value={capturedOn} max={meta!.demo_today} onChange={(e) => setCapturedOn(e.target.value)} disabled={busy} />
            </Field>
            <Field label="Where found" optional>
              <TextInput value={location} onChange={(e) => setLocation(e.target.value)} maxLength={300} disabled={busy}
                placeholder="Store, address or web address" />
            </Field>
          </div>
          <Field label="Notes" optional>
            <TextArea value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={2000} rows={3} disabled={busy}
              placeholder="e.g. 40 jars of lookalike VELORA on the confectionery aisle, shelf 3" />
          </Field>
        </div>
      </div>
    </Dialog>
  );
}

function EvidenceViewer({ items, id, onNavigate, onClose, canEdit, onChanged }: {
  items: EvidenceItem[]; id: string; onNavigate: (id: string) => void; onClose: () => void; canEdit: boolean; onChanged: () => void;
}) {
  const { user, users, meta } = useSession();
  const toast = useToast();
  const o = meta!.case_options;
  const index = items.findIndex((e) => e.evidence_id === id);
  const [item, setItem] = useState<EvidenceItem | null>(items[index] ?? null);
  const [mode, setMode] = useState<"view" | "edit" | "withdraw">("view");
  const [check, setCheck] = useState<{ ok: boolean; checked_at: string } | null>(null);
  const [form, setForm] = useState<Required<EvidenceDetails>>({ category: "", title: "", captured_on: "", location: "", notes: "" });
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const fromList = items[index];
  useEffect(() => { setMode("view"); setCheck(null); setError(null); setReason(""); }, [id]);
  useEffect(() => { if (fromList) setItem(fromList); }, [fromList]);  // keeps a just-withdrawn item on screen
  const go = useCallback((step: number) => {
    const next = items[index + step];
    if (next) onNavigate(next.evidence_id);
  }, [items, index, onNavigate]);
  useEffect(() => {
    if (mode !== "view") return;
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.closest("input, textarea, select")) return;
      if (e.key === "ArrowRight") go(1);
      if (e.key === "ArrowLeft") go(-1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go, mode]);
  if (!item || !user) return null;

  const url = api.evidenceFileUrl(item.evidence_id);
  const active = item.status === "Active";
  const verify = async () => {
    try { setCheck(await api.verifyEvidence(item.evidence_id)); }
    catch (e) { toast("error", (e as Error).message); }
  };
  const startEdit = () => {
    setForm({ category: item.category, title: item.title, captured_on: item.captured_on ?? "", location: item.location ?? "", notes: item.notes ?? "" });
    setReason(""); setError(null); setMode("edit");
  };
  const saveEdit = async () => {
    const changes = Object.fromEntries(Object.entries(form).filter(([k, v]) =>
      (item[k as keyof EvidenceItem] ?? "") !== v)) as Partial<EvidenceDetails>;
    if (!Object.keys(changes).length) { setMode("view"); return; }
    setBusy(true); setError(null);
    try {
      setItem(await api.updateEvidence(item.evidence_id, changes, reason));
      setMode("view"); onChanged(); toast("success", "Evidence details updated.");
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  const withdraw = async () => {
    setBusy(true); setError(null);
    try {
      setItem(await api.withdrawEvidence(item.evidence_id, reason));
      setMode("view"); onChanged(); toast("success", `${item.evidence_id} withdrawn. The file and its history are kept.`);
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  const copy = () => navigator.clipboard?.writeText(item.sha256).then(() => toast("info", "Fingerprint copied."), () => {});
  const Icon = categoryIcon(item);

  return (
    <Dialog open onClose={onClose} busy={busy} wide title={<span dir="auto">{item.title}</span>}
      subtitle={`${item.evidence_id} · ${item.category}${items.length > 1 ? ` · ${index + 1} of ${items.length}` : ""}`}
      footer={mode === "view" ? <>
        {items.length > 1 && <>
          <Button variant="ghost" icon={ChevronLeft} onClick={() => go(-1)} disabled={index <= 0} aria-label="Previous item">Previous</Button>
          <Button variant="ghost" onClick={() => go(1)} disabled={index >= items.length - 1} aria-label="Next item" className="me-auto">
            Next <ChevronRight size={16} />
          </Button>
        </>}
        {canEdit && active && <Button variant="ghost" icon={Undo2} onClick={() => { setReason(""); setError(null); setMode("withdraw"); }}>Withdraw</Button>}
        {canEdit && active && <Button icon={Pencil} onClick={startEdit}>Edit details</Button>}
        <a href={api.evidenceFileUrl(item.evidence_id, true)}
          className="inline-flex items-center gap-2 rounded-xl bg-primary px-3.5 py-2 text-[13.5px] font-medium text-primary-ink hover:opacity-90">
          <Download size={16} /> Download original
        </a>
      </> : <>
        <Button variant="ghost" onClick={() => setMode("view")} disabled={busy}>Back</Button>
        {mode === "edit"
          ? <Button variant="primary" onClick={saveEdit} disabled={busy}>{busy ? "Saving…" : "Save details"}</Button>
          : <Button variant="primary" icon={Undo2} onClick={withdraw} disabled={busy || reason.trim().length < 3}>{busy ? "Withdrawing…" : "Withdraw evidence"}</Button>}
      </>}>
      <div className="grid gap-6 md:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <div className="min-w-0">
          {item.image ? (
            <a href={url} target="_blank" rel="noreferrer" className="block overflow-hidden rounded-xl border border-line bg-[#0f0f10]">
              <img src={url} alt={item.title} className="mx-auto max-h-[58vh] w-full object-contain" />
            </a>
          ) : item.content_type === "application/pdf" ? (
            <iframe src={url} title={item.title} className="h-[58vh] w-full rounded-xl border border-line bg-surface-2" />
          ) : (
            <div className="flex h-full min-h-[240px] flex-col items-center justify-center gap-3 rounded-xl border border-line bg-surface-2 p-8 text-center">
              <span className="grid size-14 place-items-center rounded-2xl bg-surface text-ink-2"><Icon size={24} strokeWidth={1.6} /></span>
              <div className="text-[13.5px] font-medium text-ink" dir="auto">{item.file_name}</div>
              <div className="text-[12.5px] text-muted">{item.file_label} · {fmtBytes(item.size_bytes)}</div>
              <a href={url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-[13px] font-medium text-accent-ink hover:underline">
                <ExternalLink size={14} /> Open the file
              </a>
            </div>
          )}
          {item.status === "Withdrawn" && (
            <div className="mt-3 rounded-xl border border-line bg-surface-2 p-3 text-[12.5px] text-ink-2">
              <span className="font-medium text-ink">Withdrawn</span> by {item.withdrawn_by} on {fmtDateTime(item.withdrawn_at)}: “{item.withdrawn_reason}”
            </div>
          )}
        </div>

        <div className="min-w-0">
          <FormError>{error}</FormError>
          {mode === "edit" ? (
            <div className="grid gap-4">
              <Field label="Category"><SelectInput value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} options={o.evidence_categories} /></Field>
              <Field label="Title"><TextInput value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} maxLength={200} /></Field>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Taken or dated" optional><TextInput type="date" value={form.captured_on} max={meta!.demo_today} onChange={(e) => setForm({ ...form, captured_on: e.target.value })} /></Field>
                <Field label="Where found" optional><TextInput value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} maxLength={300} /></Field>
              </div>
              <Field label="Notes" optional><TextArea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} rows={3} maxLength={2000} /></Field>
              <Field label="Reason for the change" optional><TextInput value={reason} onChange={(e) => setReason(e.target.value)} maxLength={2000} /></Field>
            </div>
          ) : mode === "withdraw" ? (
            <div className="grid gap-3">
              <p className="text-[13px] leading-relaxed text-ink-2">
                Withdrawing takes this item out of the case's evidence. Nothing is deleted: the file, its fingerprint and its
                history stay on record, with your name, the time and the reason.
              </p>
              <Field label="Reason for withdrawing it">
                <TextArea value={reason} onChange={(e) => setReason(e.target.value)} rows={3} maxLength={2000} data-autofocus
                  placeholder="e.g. Uploaded to the wrong case; belongs to TM-2026-427" />
              </Field>
            </div>
          ) : (
            <dl className="grid gap-3.5 text-[13px]">
              <Row label="Category"><Chip>{item.category}</Chip></Row>
              {item.captured_on && <Row label={item.image ? "Taken on" : "Dated"}>{fmtDate(item.captured_on)}</Row>}
              {item.location && <Row label="Where found"><span className="inline-flex items-start gap-1.5" dir="auto"><MapPin size={13} className="mt-0.5 shrink-0 text-muted" />{item.location}</span></Row>}
              {item.notes && <Row label="Notes"><span className="whitespace-pre-line leading-relaxed" dir="auto">{item.notes}</span></Row>}
              <Row label="File"><span dir="auto">{item.file_name}</span><span className="block text-[12px] text-muted">{item.file_label} · {fmtBytes(item.size_bytes)}</span></Row>
              <Row label="Added">{users.find((u) => u.user_id === item.uploaded_by_id)?.full_name ?? item.uploaded_by}<span className="block text-[12px] text-muted">{fmtDateTime(item.uploaded_at)}</span></Row>
              <Row label="SHA-256 fingerprint">
                <span className="flex items-start gap-2">
                  <span className="min-w-0 break-all font-mono text-[11.5px] leading-relaxed text-ink-2">{item.sha256}</span>
                  <button type="button" onClick={copy} aria-label="Copy fingerprint" className="shrink-0 text-muted hover:text-ink"><Copy size={14} /></button>
                </span>
              </Row>
              <div className="rounded-xl border border-line bg-surface-2 p-3">
                {check == null ? (
                  <button type="button" onClick={verify} className="inline-flex items-center gap-2 text-[13px] font-medium text-accent-ink hover:underline">
                    <Fingerprint size={15} /> Check the file is unchanged since it was added
                  </button>
                ) : (
                  <div className="flex items-start gap-2.5 text-[13px]" role="status">
                    {check.ok ? <ShieldCheck size={17} className="mt-px shrink-0 text-good" /> : <ShieldAlert size={17} className="mt-px shrink-0 text-critical" />}
                    <div>
                      <div className="font-medium text-ink">{check.ok ? "Unchanged since it was added" : "The stored file no longer matches its fingerprint"}</div>
                      <div className="text-[12px] text-muted">Checked {fmtDateTime(check.checked_at)} against the fingerprint recorded at upload</div>
                    </div>
                  </div>
                )}
              </div>
            </dl>
          )}
        </div>
      </div>
    </Dialog>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-3">
      <dt className="text-[12px] text-muted">{label}</dt>
      <dd className="min-w-0 text-ink">{children}</dd>
    </div>
  );
}
