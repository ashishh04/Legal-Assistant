import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Check } from "lucide-react";
import { Brand } from "../components/Brand";
import { buttonCls } from "../components/ui";
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
      <div aria-hidden className="brand-surface pointer-events-none fixed inset-x-0 top-0 h-[42%]" />
      <main className="relative w-full max-w-[440px] animate-fade-up">
        <Link to="/" className="mb-8 flex justify-center" aria-label="Ferrero Case Intelligence"><Brand onDark /></Link>
        <div className="rounded-2xl border border-line bg-surface px-8 py-9 text-center shadow-overlay" role="status" aria-live="polite">
          {done ? (
            <>
              <span className="mx-auto grid size-12 place-items-center rounded-full bg-good-soft text-good-ink ring-1 ring-good-line"><Check size={22} strokeWidth={2.4} /></span>
              <h1 className="font-display mt-5 text-[26px] font-[540] leading-tight text-ink">You have been signed out</h1>
              <p className="mx-auto mt-2.5 max-w-sm text-[14px] leading-relaxed text-ink-2">
                Your session on this device has ended. If you are using a shared computer, please also close the browser.
              </p>
              <div className="mt-7 grid gap-2.5">
                <Link to="/login" className={buttonCls("primary", "lg", "w-full font-semibold")}>Sign in again</Link>
                <Link to="/" className={buttonCls("secondary", "lg", "w-full")}>Return to the home page</Link>
              </div>
            </>
          ) : (
            <p className="py-6 text-[14px] text-muted">Signing you out…</p>
          )}
        </div>
        {publicInfo?.org_name && <p className="mt-6 text-center text-[12.5px] text-muted">{publicInfo.org_name} · Legal &amp; Brand Protection</p>}
      </main>
    </div>
  );
}
