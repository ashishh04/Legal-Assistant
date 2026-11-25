import clsx from "clsx";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, Check, ChevronDown, CircleAlert, Eye, EyeOff, Info, TriangleAlert, UsersRound } from "lucide-react";
import { ApiError } from "../api";
import { Brand } from "../components/Brand";
import { inputCls } from "../components/forms";
import { Avatar, Callout, Chip, buttonCls } from "../components/ui";
import { useSession } from "../session";

/** Only paths inside the app: never send someone to another site after signing in. */
export function safeNext(next: string | null): string {
  return next && next.startsWith("/") && !next.startsWith("//") && !next.startsWith("/login") && !next.startsWith("/logout") ? next : "/";
}

export default function Login() {
  const { status, signIn, expired, publicInfo } = useSession();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const next = safeNext(params.get("next"));
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [remember, setRemember] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [help, setHelp] = useState(false);
  const passwordRef = useRef<HTMLInputElement>(null);
  const loginRef = useRef<HTMLInputElement>(null);
  useEffect(() => { loginRef.current?.focus(); }, []);

  if (status === "signed-in") return <Navigate to={next} replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!login.trim() || !password) { setError("Enter your e-mail address and password."); return; }
    setBusy(true);
    setError(null);
    try {
      await signIn(login.trim(), password, remember);
      navigate(next, { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Ferrero couldn't be reached. Check the connection and try again.");
      setPassword("");
      passwordRef.current?.focus();
    } finally {
      setBusy(false);
    }
  };
  const pick = (email: string) => { setLogin(email); setError(null); passwordRef.current?.focus(); };
  const field = clsx(inputCls, "h-11 text-[14.5px]");

  return (
    <div className="grid h-full overflow-y-auto bg-page lg:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)]">
      <BrandPanel org={publicInfo?.org_name} />
      <main className="flex min-h-full flex-col px-6 py-7 sm:px-12">
        <div className="flex h-10 items-center justify-between">
          <Link to="/" className="-ms-2 inline-flex h-9 items-center gap-1.5 rounded-lg px-2 text-[13.5px] font-medium text-ink-2 transition-colors hover:bg-surface-3 hover:text-ink">
            <ArrowLeft size={15} /> Home
          </Link>
          <span className="lg:hidden"><Brand size="sm" /></span>
        </div>
        <div className="mx-auto my-auto w-full max-w-[400px] py-12">
          <h1 className="font-display text-[36px] font-[520] leading-tight text-ink">Sign in</h1>
          <p className="mt-2 text-[14.5px] leading-relaxed text-ink-2">Use your work e-mail address and your Ferrero password.</p>

          {expired && (
            <Callout icon={Info} className="mt-6">Your session has ended. Sign in again to carry on where you left off.</Callout>
          )}
          {publicInfo && !publicInfo.sign_in_configured && (
            <Callout icon={TriangleAlert} tone="warning" className="mt-6">
              Sign-in is not available yet. Please contact your administrator.
            </Callout>
          )}

          <form onSubmit={submit} className="mt-8 grid gap-5" noValidate>
            <label className="block">
              <span className="mb-1.5 block text-[13px] font-medium text-ink">E-mail address</span>
              <input ref={loginRef} type="email" inputMode="email" autoComplete="username" value={login}
                onChange={(e) => setLogin(e.target.value)} placeholder="name@company.com" className={field}
                aria-invalid={Boolean(error)} aria-describedby={error ? "sign-in-error" : undefined} />
            </label>
            <div>
              <div className="mb-1.5 flex items-baseline justify-between">
                <label htmlFor="password" className="text-[13px] font-medium text-ink">Password</label>
                <button type="button" onClick={() => setHelp((h) => !h)} aria-expanded={help}
                  className="text-[13px] font-medium text-accent-ink underline-offset-2 hover:underline">Forgot your password?</button>
              </div>
              <div className="relative">
                <input id="password" ref={passwordRef} type={show ? "text" : "password"} autoComplete="current-password"
                  value={password} onChange={(e) => setPassword(e.target.value)} className={clsx(field, "pe-11")}
                  aria-invalid={Boolean(error)} aria-describedby={error ? "sign-in-error" : undefined} />
                <button type="button" onClick={() => setShow((s) => !s)} aria-label={show ? "Hide password" : "Show password"}
                  aria-pressed={show} className="absolute inset-y-0 end-0 grid w-11 place-items-center rounded-e-lg text-muted transition-colors hover:text-ink">
                  {show ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </div>
              {help && (
                <p className="mt-2.5 rounded-lg border border-line bg-surface-2 p-3 text-[13px] leading-relaxed text-ink-2">
                  Passwords are managed by Legal Operations. Contact them to have yours reset; you will then sign in
                  with a temporary password and set a new one from your account menu.
                </p>
              )}
            </div>
            <label className="flex cursor-pointer items-center gap-2.5 text-[13.5px] text-ink-2">
              <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} className="size-4 rounded accent-[var(--primary)]" />
              Keep me signed in on this device
            </label>
            {error && (
              <p id="sign-in-error" role="alert" className="flex items-start gap-2.5 rounded-lg border border-critical-line bg-critical-soft px-3.5 py-2.5 text-[13.5px] leading-relaxed text-ink">
                <CircleAlert size={16} className="mt-0.5 shrink-0 text-critical" />{error}
              </p>
            )}
            <button type="submit" disabled={busy} className={buttonCls("primary", "lg", "mt-1 w-full font-semibold")}>
              {busy ? "Signing in…" : <>Sign in <ArrowRight size={16} /></>}
            </button>
          </form>

          {publicInfo?.accounts && publicInfo.accounts.length > 0 && (
            <details className="group mt-8 overflow-hidden rounded-xl border border-line bg-surface shadow-card">
              <summary className="flex cursor-pointer list-none items-center gap-2.5 px-4 py-3 text-[13.5px] font-medium text-ink">
                <UsersRound size={16} className="text-accent-ink" /> Test accounts
                <ChevronDown size={15} className="ms-auto text-muted transition-transform group-open:rotate-180" />
              </summary>
              <div className="border-t border-line px-2 pb-2 pt-1">
                <p className="px-2 py-2 text-[12.5px] leading-relaxed text-muted">
                  Select an account to fill in its e-mail address. Each account sees only what its role permits.
                </p>
                <ul className="grid grid-cols-1 gap-0.5">
                  {publicInfo.accounts.map((a) => (
                    <li key={a.user_id}>
                      <button type="button" onClick={() => pick(a.email)}
                        className={clsx("flex w-full items-center gap-3 rounded-lg px-2 py-2 text-start transition-colors hover:bg-surface-3",
                          login === a.email && "bg-accent-soft")}>
                        <Avatar name={a.full_name} size={32} />
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-[13.5px] font-medium text-ink">{a.full_name}</span>
                          <span className="block truncate text-[12px] text-muted">{a.job_title}</span>
                        </span>
                        <Chip tone="outline" className="shrink-0">{a.entra_group}</Chip>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            </details>
          )}
        </div>
        <p className="text-center text-[12.5px] text-muted">For your security, sessions end after a period of inactivity.</p>
      </main>
    </div>
  );
}

const POINTS = [
  "Answers from the case files, with sources",
  "Each person sees only what their role allows",
  "Every change recorded, with who and when",
];

/** The left half of the sign-in page on wide screens. */
export function BrandPanel({ org }: { org?: string }) {
  return (
    <aside className="brand-surface relative hidden overflow-hidden text-on-brand lg:flex lg:flex-col lg:justify-between lg:px-14 lg:py-10">
      <div aria-hidden className="pointer-events-none absolute -bottom-[360px] -end-[300px] size-[820px] rounded-full border border-brand-accent/[0.14]" />
      <div aria-hidden className="pointer-events-none absolute -bottom-[260px] -end-[200px] size-[620px] rounded-full border border-brand-accent/[0.10]" />
      <div aria-hidden className="pointer-events-none absolute -bottom-[160px] -end-[100px] size-[420px] rounded-full border border-brand-accent/[0.07]" />
      <Link to="/" className="relative w-fit" aria-label="Ferrero Case Intelligence"><Brand onDark size="lg" /></Link>
      <div className="relative max-w-[30rem]">
        <div className="mb-6 flex items-center gap-3 text-[11.5px] font-semibold uppercase tracking-[0.2em] text-brand-accent">
          <span aria-hidden className="h-px w-8 bg-brand-accent/60" />
          Legal &amp; Brand Protection
        </div>
        <h2 className="font-display text-balance text-[42px] font-[460] leading-[1.08] text-on-brand">
          Your cases, documents and deadlines, in <em className="font-[440] italic text-brand-accent">one place</em>.
        </h2>
        <ul className="mt-10 grid gap-4 text-[14.5px] text-on-brand/85">
          {POINTS.map((text) => (
            <li key={text} className="flex items-center gap-3.5">
              <span className="grid size-6 shrink-0 place-items-center rounded-full bg-brand-accent/15 text-brand-accent ring-1 ring-brand-accent/35"><Check size={13} strokeWidth={2.6} /></span>
              {text}
            </li>
          ))}
        </ul>
      </div>
      <div className="relative text-[12.5px] text-on-brand/55">{org ? `${org} · ` : ""}Legal &amp; Brand Protection</div>
    </aside>
  );
}
