import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

/** Fetch with stale-while-revalidate: on refetch the previous data stays (dimmed by the caller), no skeleton flash. */
export function useApi<T>(load: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);
  const seq = useRef(0);
  const run = useCallback(() => {
    const id = ++seq.current;
    setLoading(true);
    load()
      .then((d) => { if (id === seq.current) { setData(d); setError(null); } })
      .catch((e: Error) => { if (id === seq.current) setError(e); })
      .finally(() => { if (id === seq.current) setLoading(false); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(run, [run]);
  return { data, error, loading, reload: run };
}

/** Width of an element, kept current with a ResizeObserver (charts lay out to their container). */
export function useWidth<T extends HTMLElement>(): [React.RefObject<T | null>, number] {
  const ref = useRef<T | null>(null);
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    setWidth(el.getBoundingClientRect().width);
    const ro = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width];
}

export function useLocalStorage(key: string, initial: string): [string, (v: string) => void] {
  const [value, setValue] = useState(() => {
    try { return localStorage.getItem(key) ?? initial; } catch { return initial; }
  });
  const set = useCallback((v: string) => {
    setValue(v);
    try { localStorage.setItem(key, v); } catch { /* storage unavailable: keep in memory */ }
  }, [key]);
  return [value, set];
}
