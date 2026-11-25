import { Link } from "react-router-dom";
import { ArrowRight, Check, History, Languages, Moon, Quote, ShieldCheck, Sun } from "lucide-react";
import { Brand, Monogram } from "../components/Brand";
import { buttonCls } from "../components/ui";
import { useSession } from "../session";

const STEPS = [
  { title: "Register", text: "Record the infringement and its evidence." },
  { title: "Assign", text: "Give every case an owner." },
  { title: "Follow up", text: "Deadlines with automatic alerts." },
  { title: "Close", text: "Record the outcome and close." },
];

const ASSURANCES = [
  { icon: ShieldCheck, text: "Access by role" },
  { icon: Languages, text: "English and Arabic" },
  { icon: History, text: "Every change on record" },
];

export default function Landing() {
  const { publicInfo, theme, toggleTheme } = useSession();
  const org = publicInfo?.org_name;
  return (
    <div className="flex h-full flex-col overflow-y-auto bg-page">
      <section className="brand-surface relative flex flex-[1_0_auto] flex-col overflow-hidden text-on-brand">
        {/* the seal's rings, large and faint, behind the product */}
        <div aria-hidden className="pointer-events-none absolute -end-[220px] top-1/2 hidden size-[900px] -translate-y-1/2 rounded-full border border-brand-accent/[0.13] lg:block" />
        <div aria-hidden className="pointer-events-none absolute -end-[120px] top-1/2 hidden size-[700px] -translate-y-1/2 rounded-full border border-brand-accent/[0.09] lg:block" />

        <header className="relative mx-auto flex h-[76px] w-full max-w-[1240px] shrink-0 items-center px-6 sm:px-10">
          <Link to="/" aria-label="Ferrero Case Intelligence"><Brand onDark /></Link>
          <nav className="ms-auto flex items-center gap-2" aria-label="Page">
            <button type="button" onClick={toggleTheme} aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
              className="grid size-9 place-items-center rounded-lg text-on-brand/70 transition-colors hover:bg-white/10 hover:text-on-brand">
              {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
            </button>
            <Link to="/login" className={buttonCls("inverse", "md", "px-4")}>Sign in</Link>
          </nav>
        </header>

        <div className="relative mx-auto grid w-full max-w-[1240px] flex-1 grid-cols-1 items-center gap-x-16 gap-y-14 px-6 pb-20 pt-10 sm:px-10 lg:grid-cols-[minmax(0,1.02fr)_minmax(0,1fr)] lg:pb-24 lg:pt-12">
          <div className="min-w-0 animate-fade-up">
            <div className="mb-6 flex items-center gap-3 text-[11.5px] font-semibold uppercase tracking-[0.2em] text-brand-accent">
              <span aria-hidden className="h-px w-8 bg-brand-accent/60" />
              Legal &amp; Brand Protection
            </div>
            <h1 className="font-display text-balance text-[44px] font-[460] leading-[1.04] text-on-brand sm:text-[60px]">
              Every case, from report to <em className="font-[440] italic text-brand-accent">closure</em>.
            </h1>
            <p className="mt-6 max-w-[30rem] text-[17px] leading-relaxed text-on-brand/75">
              Register, assign, follow up and close infringement cases, with every step on record.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-x-6 gap-y-4">
              <Link to="/login" className={buttonCls("inverse", "lg", "px-6")}>
                Sign in <ArrowRight size={17} />
              </Link>
              {org && <span className="text-[13px] text-on-brand/55">For the legal team of {org}</span>}
            </div>
            <ul className="mt-12 flex flex-wrap gap-x-7 gap-y-3 border-t border-white/10 pt-6 text-[13.5px] text-on-brand/80">
              {ASSURANCES.map(({ icon: Icon, text }) => (
                <li key={text} className="flex items-center gap-2"><Icon size={16} className="text-brand-accent" strokeWidth={1.7} />{text}</li>
              ))}
            </ul>
          </div>
          <ProductSketch />
        </div>
      </section>

      <section className="mx-auto w-full max-w-[1240px] shrink-0 px-6 py-12 sm:px-10" aria-label="How it works">
        <ol className="grid gap-x-0 gap-y-8 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map(({ title, text }, i) => (
            <li key={title} className="min-w-0">
              <div className="flex items-center">
                <span className="grid size-9 shrink-0 place-items-center rounded-full border border-accent-line bg-accent-soft text-[14px] font-semibold text-accent-ink">{i + 1}</span>
                {i < STEPS.length - 1 && <span aria-hidden className="mx-4 hidden h-px flex-1 bg-line-strong lg:block" />}
              </div>
              <h2 className="mt-4 text-[16px] font-semibold text-ink"><span className="sr-only">Step {i + 1}: </span>{title}</h2>
              <p className="mt-1 max-w-[15rem] text-[14px] leading-relaxed text-ink-2">{text}</p>
            </li>
          ))}
        </ol>
      </section>

      <footer className="shrink-0 border-t border-line">
        <div className="mx-auto flex max-w-[1240px] flex-wrap items-center justify-between gap-3 px-6 py-5 text-[12.5px] text-muted sm:px-10">
          <span>{org ? `${org} · ` : ""}Legal &amp; Brand Protection</span>
          <span>Ferrero Case Intelligence</span>
        </div>
      </footer>
    </div>
  );
}

/** An illustration of the product, made from the app's own pieces (no real case data: this page is public). It is
 *  always drawn in the light theme, as a picture on the dark panel. */
function ProductSketch() {
  const rows = [
    { day: "5", title: "Store to remove infringing products", meta: "Compliance deadline · decision due", due: "Due today", leaf: "border-warning-line", band: "bg-warning-soft text-warning-ink", pill: "bg-warning-soft text-warning-ink" },
    { day: "11", title: "Hearing, Commercial Court", meta: "Hearing bundle prepared", due: "In 6 days", leaf: "border-accent-line", band: "bg-accent-soft text-accent-ink", pill: "bg-accent-soft text-accent-ink" },
    { day: "19", title: "Follow-up test purchase", meta: "Next action · assigned to counsel", due: "In 14 days", leaf: "border-line", band: "bg-surface-3 text-muted", pill: "bg-surface-3 text-ink-2" },
  ];
  return (
    <div data-theme="light" className="relative mx-auto w-full min-w-0 max-w-[540px] animate-fade-up lg:mx-0 lg:ms-auto" aria-hidden>
      <div className="rounded-2xl border border-white/10 bg-surface p-5 shadow-overlay">
        <div className="mb-4 flex items-center justify-between">
          <div className="text-[15px] font-semibold text-ink">Needs attention</div>
          <span className="text-[12.5px] text-muted">This week</span>
        </div>
        <ul className="divide-y divide-line">
          {rows.map((r) => (
            <li key={r.title} className="flex items-center gap-3.5 py-3 first:pt-1 last:pb-1">
              <span className={`w-11 shrink-0 overflow-hidden rounded-lg border bg-surface text-center ${r.leaf}`}>
                <span className={`block py-[2px] text-[9.5px] font-semibold uppercase tracking-[0.1em] ${r.band}`}>Nov</span>
                <span className="block py-1 text-[15px] font-semibold leading-none text-ink">{r.day}</span>
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[13.5px] font-medium text-ink">{r.title}</span>
                <span className="block truncate text-[12.5px] text-muted">{r.meta}</span>
              </span>
              <span className={`shrink-0 rounded-full px-2.5 py-[3px] text-[11.5px] font-medium ${r.pill}`}>{r.due}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="relative -mt-5 ms-auto w-[90%] rounded-2xl border border-line bg-surface p-4 shadow-overlay sm:-mt-6 sm:w-[86%] lg:-me-6">
        <div className="flex items-center gap-2.5">
          <Monogram size={28} />
          <span className="text-[13.5px] font-semibold text-ink">Ferrero Assistant</span>
          <span className="ms-auto rounded-md bg-surface-3 px-2 py-0.5 text-[11.5px] font-medium text-ink-2">EN · AR</span>
        </div>
        <p className="ms-auto mt-3.5 w-fit rounded-2xl rounded-ee-md bg-brand-2 px-3.5 py-2 text-[13px] text-on-brand">What did the court award?</p>
        <p className="mt-3 text-[13.5px] leading-relaxed text-ink">
          The court awarded compensation and ordered the infringing goods destroyed
          <span className="ms-1 inline-grid size-[18px] place-items-center rounded bg-accent-soft align-[1px] text-[10.5px] font-semibold text-accent-ink ring-1 ring-accent-line">1</span>
        </p>
        <span className="mt-3 inline-flex items-center gap-1.5 rounded-md border border-line bg-surface-2 px-2 py-1 text-[12px] text-ink-2">
          <Quote size={12} className="text-accent-ink" /> Judgment · Operative part
        </span>
      </div>

      <div className="absolute -top-5 end-6 hidden items-center gap-2 rounded-full border border-good-line bg-good-soft py-1.5 pe-3.5 ps-2.5 shadow-pop sm:flex lg:-end-5">
        <span className="grid size-5 place-items-center rounded-full bg-good text-white"><Check size={12} strokeWidth={3} /></span>
        <span className="text-[12.5px] font-medium text-good-ink">Tamper check passed</span>
      </div>
    </div>
  );
}
