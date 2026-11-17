import clsx from "clsx";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, Eye, EyeOff, Info, KeyRound, LockKeyhole, ShieldCheck, Sparkles, TriangleAlert, UsersRound } from "lucide-react";
import { ApiError } from "../api";
import { Monogram } from "../components/Brand";
import { inputCls } from "../components/forms";
import { initials } from "../lib/format";
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

  return (
    <div className="grid h-full overflow-y-auto bg-page lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
      <BrandPanel org={publicInfo?.org_name} />
      <main className="flex min-h-full flex-col px-5 py-8 sm:px-10">
        <div className="flex items-center justify-between">
          <Link to="/" className="inline-flex items-center gap-1.5 text-[13px] text-ink-2 hover:text-ink"><ArrowLeft size={15} /> Home</Link>
          <span className="flex items-center gap-2 lg:hidden"><Monogram size={28} /><span className="text-[14px] font-semibold text-ink">Ferrero</span></span>
        </div>
        <div className="mx-auto my-auto w-full max-w-[420px] py-10">
          <h1 className="text-[28px] font-semibold tracking-[-0.025em] text-ink">Sign in</h1>
          <p className="mt-1.5 text-[14px] text-ink-2">Use your work e-mail address and your Ferrero password.</p>

          {expired && (
            <Notice icon={Info}>Your session has ended. Sign in again to carry on where you left off.</Notice>
          )}
          {publicInfo && !publicInfo.sign_in_configured && (
            <Notice icon={TriangleAlert} tone="warning">
              Sign-in is not available yet. Please contact your administrator.
            </Notice>
          )}

          <form onSubmit={submit} className="mt-6 grid gap-4" noValidate>
            <label className="block">
              <span className="mb-1.5 block text-[12.5px] font-medium text-ink-2">E-mail address</span>
              <input ref={loginRef} type="email" inputMode="email" autoComplete="username" value={login}
                onChange={(e) => setLogin(e.target.value)} placeholder="name@company.com" className={clsx(inputCls, "py-2.5")}
                aria-invalid={Boolean(error)} aria-describedby={error ? "sign-in-error" : undefined} />
            </label>
            <div>
              <div className="mb-1.5 flex items-baseline justify-between">
                <label htmlFor="password" className="text-[12.5px] font-medium text-ink-2">Password</label>
                <button type="button" onClick={() => setHelp((h) => !h)} aria-expanded={help}
                  className="text-[12.5px] font-medium text-accent-ink hover:underline">Forgot your password?</button>
              </div>
              <div className="relative">
                <input id="password" ref={passwordRef} type={show ? "text" : "password"} autoComplete="current-password"
                  value={password} onChange={(e) => setPassword(e.target.value)} className={clsx(inputCls, "py-2.5 pe-11")}
                  aria-invalid={Boolean(error)} aria-describedby={error ? "sign-in-error" : undefined} />
                <button type="button" onClick={() => setShow((s) => !s)} aria-label={show ? "Hide password" : "Show password"}
                  aria-pressed={show} className="absolute inset-y-0 end-0 grid w-11 place-items-center text-muted hover:text-ink">
                  {show ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </div>
              {help && (
                <p className="mt-2 rounded-xl border border-line bg-surface-2 p-3 text-[12.5px] leading-relaxed text-ink-2">
                  Passwords are managed by Legal Operations. Contact them to have yours reset; you will then sign in
                  with a temporary password and set a new one from your account menu.
                </p>
              )}
            </div>
            <label className="flex cursor-pointer items-center gap-2.5 text-[13px] text-ink-2">
              <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} className="size-4 accent-[var(--accent)]" />
              Keep me signed in on this device
            </label>
            {error && (
              <p id="sign-in-error" role="alert" className="flex items-start gap-2 rounded-xl border border-critical/30 bg-critical/5 px-3.5 py-2.5 text-[13px] text-ink">
                <TriangleAlert size={16} className="mt-0.5 shrink-0 text-critical" />{error}
              </p>
            )}
            <button type="submit" disabled={busy}
              className="mt-1 inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-[14.5px] font-semibold text-primary-ink transition hover:opacity-90 disabled:opacity-60">
              <LockKeyhole size={16} /> {busy ? "Signing in…" : "Sign in"}
            </button>
          </form>

          {publicInfo?.accounts && publicInfo.accounts.length > 0 && (
            <details className="group mt-8 rounded-2xl border border-line bg-surface">
              <summary className="flex cursor-pointer list-none items-center gap-2.5 px-4 py-3 text-[13.5px] font-medium text-ink">
                <UsersRound size={16} className="text-accent-ink" /> Test accounts
                <span className="ms-auto text-[12px] font-normal text-muted group-open:hidden">Show</span>
                <span className="ms-auto hidden text-[12px] font-normal text-muted group-open:inline">Hide</span>
              </summary>
              <div className="border-t border-line px-2 pb-2 pt-1">
                <p className="px-2 py-2 text-[12px] leading-relaxed text-muted">
                  Select an account to fill in its e-mail address. Each account sees only what its role permits.
                </p>
                <ul className="grid gap-0.5">
                  {publicInfo.accounts.map((a) => (
                    <li key={a.user_id}>
                      <button type="button" onClick={() => pick(a.email)}
                        className={clsx("flex w-full items-center gap-3 rounded-xl px-2 py-2 text-start transition hover:bg-surface-2",
                          login === a.email && "bg-accent-soft/60")}>
                        <span className="grid size-8 shrink-0 place-items-center rounded-full bg-gradient-to-br from-[#e8cf9a] to-[#9c7a3f] text-[11px] font-semibold text-[#141519]">
                          {initials(a.full_name)}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-[13px] font-medium text-ink">{a.full_name}</span>
                          <span className="block truncate text-[11.5px] text-muted">{a.job_title}</span>
                        </span>
                        <span className="shrink-0 rounded-full border border-line px-2 py-0.5 text-[10.5px] text-ink-2">{a.entra_group}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            </details>
          )}
        </div>
        <p className="text-center text-[12px] text-muted">For your security, sessions end after a period of inactivity.</p>
      </main>
    </div>
  );
}

function Notice({ icon: Icon, tone = "info", children }: { icon: typeof Info; tone?: "info" | "warning"; children: React.ReactNode }) {
  return (
    <div role="status" className={clsx("mt-5 flex items-start gap-2.5 rounded-xl border p-3.5 text-[13px] leading-relaxed text-ink",
      tone === "warning" ? "border-warning/60 bg-warning/10" : "border-line bg-surface-2")}>
      <Icon size={16} className={clsx("mt-0.5 shrink-0", tone === "warning" ? "text-[var(--warning)]" : "text-accent-ink")} />
      <span>{children}</span>
    </div>
  );
}

/** The left half of the sign-in page on wide screens. */
export function BrandPanel({ org }: { org?: string }) {
  return (
    <aside className="relative hidden overflow-hidden bg-sidebar lg:flex lg:flex-col lg:justify-between lg:p-12">
      <div aria-hidden className="pointer-events-none absolute inset-0 bg-[radial-gradient(90%_70%_at_0%_0%,rgba(201,164,101,0.28),transparent_60%)]" />
      <div aria-hidden className="pointer-events-none absolute -bottom-40 -end-40 size-[520px] rounded-full border border-white/5" />
      <div aria-hidden className="pointer-events-none absolute -bottom-24 -end-24 size-[360px] rounded-full border border-white/5" />
      <Link to="/" className="relative flex items-center gap-3">
        <Monogram size={40} />
        <span>
          <span className="block text-[17px] font-semibold text-white">Ferrero</span>
          <span className="block text-[12px] text-sidebar-muted">Case intelligence</span>
        </span>
      </Link>
      <div className="relative max-w-md">
        <h2 className="text-[34px] font-semibold leading-[1.12] tracking-[-0.03em] text-white">
          Your cases, documents and deadlines, in one place.
        </h2>
        <ul className="mt-8 grid gap-4 text-[14px] text-sidebar-ink">
          {[[Sparkles, "Answers from the case files, with sources"], [KeyRound, "Each person sees only what their role allows"],
            [ShieldCheck, "Every change recorded, with who and when"]].map(([Icon, text]) => {
            const I = Icon as typeof Sparkles;
            return (
              <li key={text as string} className="flex items-center gap-3">
                <span className="grid size-8 place-items-center rounded-lg bg-white/5 text-accent"><I size={15} /></span>{text as string}
              </li>
            );
          })}
        </ul>
      </div>
      <div className="relative text-[12px] text-sidebar-muted">{org ? `${org} · ` : ""}Legal &amp; Brand Protection</div>
    </aside>
  );
}
