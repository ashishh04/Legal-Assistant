import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { CircleCheck, LogIn } from "lucide-react";
import { Monogram } from "../components/Brand";
import { useSession } from "../session";

/** Signs out (if still signed in) and confirms it. */
export default function Logout() {
  const { status, signOut, publicInfo } = useSession();
  const [done, setDone] = useState(status === "signed-out");
  const started = useRef(false);

  useEffect(() => {
    if (status === "signed-in" && !started.current) {
      started.current = true;
      signOut().finally(() => setDone(true));
    } else if (status === "signed-out") {
      setDone(true);
    }
  }, [status, signOut]);

  return (
    <div className="grid h-full place-items-center overflow-y-auto bg-page px-5 py-10">
      <div aria-hidden className="pointer-events-none fixed inset-x-0 top-0 h-[420px] bg-[radial-gradient(60%_100%_at_50%_0%,var(--accent-soft),transparent_70%)]" />
      <main className="relative w-full max-w-[440px] animate-fade-up">
        <Link to="/" className="mb-8 flex items-center justify-center gap-2.5">
          <Monogram size={34} />
          <span className="text-[16px] font-semibold text-ink">Ferrero</span>
        </Link>
        <div className="rounded-3xl border border-line bg-surface p-8 text-center shadow-card" role="status" aria-live="polite">
          {done ? (
            <>
              <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-good/10 text-good"><CircleCheck size={26} /></span>
              <h1 className="mt-5 text-[22px] font-semibold tracking-[-0.02em] text-ink">You have been signed out</h1>
              <p className="mx-auto mt-2 max-w-sm text-[14px] leading-relaxed text-ink-2">
                Your session on this device has ended. If you are using a shared computer, please also close the browser.
              </p>
              <div className="mt-7 grid gap-2.5">
                <Link to="/login" className="inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-[14.5px] font-semibold text-primary-ink hover:opacity-90">
                  <LogIn size={16} /> Sign in again
                </Link>
                <Link to="/" className="inline-flex items-center justify-center rounded-xl border border-line-strong px-4 py-3 text-[14px] font-medium text-ink hover:bg-surface-2">
                  Return to the home page
                </Link>
              </div>
            </>
          ) : (
            <p className="py-6 text-[14px] text-muted">Signing you out…</p>
          )}
        </div>
        {publicInfo?.org_name && <p className="mt-6 text-center text-[12px] text-muted">{publicInfo.org_name} · Legal &amp; Brand Protection</p>}
      </main>
    </div>
  );
}
