import { Link } from "react-router-dom";
import {
  ArrowRight, BellRing, CalendarClock, CircleCheck, CircleCheckBig, ClipboardPlus, Gavel, Handshake, History, Languages,
  Moon, Quote, ShieldCheck, Sun, UserRoundCheck,
} from "lucide-react";
import { Monogram } from "../components/Brand";
import { useSession } from "../session";

const STEPS = [
  { icon: ClipboardPlus, title: "Register", text: "Record the infringement and its evidence." },
  { icon: UserRoundCheck, title: "Assign", text: "Give every case an owner." },
  { icon: CalendarClock, title: "Follow up", text: "Deadlines with automatic alerts." },
  { icon: CircleCheckBig, title: "Close", text: "Record the outcome and close." },
];

export default function Landing() {
  const { publicInfo, theme, toggleTheme } = useSession();
  const org = publicInfo?.org_name;
  return (
    <div className="flex h-full flex-col overflow-y-auto bg-page">
      <header className="border-b border-line">
        <div className="mx-auto flex h-16 w-full max-w-[1200px] items-center gap-3 px-5 sm:px-8">
          <Monogram size={34} />
          <div className="leading-tight">
            <div className="text-[15px] font-semibold tracking-[-0.01em] text-ink">Ferrero</div>
            <div className="text-[11.5px] text-muted">Case intelligence</div>
          </div>
          <nav className="ms-auto flex items-center gap-1 sm:gap-2" aria-label="Page">
            <button type="button" onClick={toggleTheme} aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
              className="grid size-9 place-items-center rounded-xl text-ink-2 hover:bg-surface-2 hover:text-ink">
              {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
            </button>
            <Link to="/login" className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-[13.5px] font-medium text-primary-ink hover:opacity-90">
              Sign in
            </Link>
          </nav>
        </div>
      </header>

      <main className="flex-1">
        <section className="relative overflow-hidden">
          <div aria-hidden className="pointer-events-none absolute -end-40 -top-40 size-[640px] rounded-full bg-[radial-gradient(circle,var(--accent-soft),transparent_65%)]" />
          <div className="relative mx-auto grid max-w-[1200px] items-center gap-12 px-5 pb-14 pt-14 sm:px-8 lg:grid-cols-[1.05fr_1fr] lg:pt-20">
            <div className="animate-fade-up">
              <div className="mb-4 text-[11.5px] font-semibold uppercase tracking-[0.16em] text-accent-ink">
                Legal &amp; Brand Protection{org ? ` · ${org}` : ""}
              </div>
              <h1 className="text-balance text-[40px] font-semibold leading-[1.08] tracking-[-0.035em] text-ink sm:text-[52px]">
                Every case, from report to closure.
              </h1>
              <p className="mt-5 max-w-lg text-[16px] leading-relaxed text-ink-2">
                Register, assign, follow up and close infringement cases, with every step on record.
              </p>
              <Link to="/login" className="mt-8 inline-flex items-center gap-2 rounded-xl bg-primary px-5 py-3 text-[14.5px] font-medium text-primary-ink shadow-card hover:opacity-90">
                Sign in <ArrowRight size={16} />
              </Link>
              <ul className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-[13px] text-ink-2">
                {[[ShieldCheck, "Access by role"], [Languages, "English and Arabic"], [History, "Every change on record"]].map(([Icon, text]) => {
                  const I = Icon as typeof ShieldCheck;
                  return <li key={text as string} className="flex items-center gap-2"><I size={15} className="text-accent-ink" />{text as string}</li>;
                })}
              </ul>
            </div>
            <ProductSketch />
          </div>
        </section>

        <section className="mx-auto max-w-[1200px] px-5 pb-16 sm:px-8" aria-label="How it works">
          <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map(({ icon: Icon, title, text }, i) => (
              <li key={title} className="flex items-center gap-4 rounded-2xl border border-line bg-surface p-5">
                <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent-ink"><Icon size={20} strokeWidth={1.7} /></span>
                <span>
                  <span className="block text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">Step {i + 1}</span>
                  <span className="block text-[15px] font-semibold text-ink">{title}</span>
                  <span className="block text-[13px] text-ink-2">{text}</span>
                </span>
              </li>
            ))}
          </ol>
        </section>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-3 px-5 py-6 text-[12.5px] text-muted sm:px-8">
          <span>{org ? `${org} · ` : ""}Legal &amp; Brand Protection</span>
          <span>Ferrero Case Intelligence</span>
        </div>
      </footer>
    </div>
  );
}

/** An illustration of the product, made from the app's own pieces (no real case data: this page is public). */
function ProductSketch() {
  return (
    <div className="relative mx-auto w-full max-w-[520px] animate-fade-up lg:mx-0" aria-hidden>
      <div className="rounded-3xl border border-line bg-surface p-5 shadow-card">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">Today</div>
            <div className="text-[16px] font-semibold text-ink">Needs attention</div>
          </div>
          <span className="rounded-full border border-line bg-surface-2 px-2.5 py-1 text-[11.5px] font-medium text-ink-2">3 items</span>
        </div>
        <ul className="flex flex-col gap-2.5">
          {[
            { icon: BellRing, title: "Store to remove infringing products", meta: "Deadline reached · decision due today", tone: "warn" },
            { icon: Gavel, title: "Hearing, Commercial Court", meta: "In 6 days · hearing bundle prepared", tone: "calm" },
            { icon: Handshake, title: "Business consultation", meta: "Customer · cleared to proceed", tone: "good" },
          ].map(({ icon: Icon, title, meta, tone }) => (
            <li key={title} className="flex items-center gap-3 rounded-2xl border border-line bg-page p-3">
              <span className={`grid size-9 shrink-0 place-items-center rounded-xl ${tone === "warn" ? "bg-critical/10 text-critical" : tone === "good" ? "bg-good/10 text-good-ink" : "bg-accent-soft text-accent-ink"}`}>
                <Icon size={16} />
              </span>
              <span className="min-w-0">
                <span className="block truncate text-[13.5px] font-medium text-ink">{title}</span>
                <span className="block truncate text-[12px] text-muted">{meta}</span>
              </span>
            </li>
          ))}
        </ul>
      </div>

      <div className="relative -mt-6 ms-auto w-[88%] rounded-3xl border border-line bg-surface p-4 shadow-card sm:-mt-8">
        <div className="flex items-center gap-2.5">
          <Monogram size={28} />
          <span className="text-[13px] font-semibold text-ink">Ferrero</span>
          <span className="ms-auto rounded-full bg-surface-2 px-2 py-0.5 text-[11px] text-muted">EN · AR</span>
        </div>
        <p className="mt-3 rounded-2xl rounded-tl-md bg-surface-2 px-3.5 py-2.5 text-[13px] text-ink-2">What did the court award?</p>
        <p className="mt-2 text-[13px] leading-relaxed text-ink">
          The court awarded compensation and ordered the infringing goods destroyed
          <span className="ms-1 inline-grid size-[18px] place-items-center rounded-md bg-accent-soft align-[1px] text-[10.5px] font-semibold text-accent-ink">1</span>
        </p>
        <span className="mt-2.5 inline-flex items-center gap-1.5 rounded-lg border border-line px-2 py-1 text-[11.5px] text-muted">
          <Quote size={12} /> Judgment · Operative part
        </span>
      </div>

      <div className="absolute -end-3 -top-5 hidden items-center gap-2 rounded-2xl border border-line bg-surface px-3.5 py-2.5 shadow-card sm:flex">
        <CircleCheck size={16} className="text-good" />
        <span className="text-[12.5px] font-medium text-ink">Tamper check passed</span>
      </div>
    </div>
  );
}
