import clsx from "clsx";
import { useId } from "react";

/** The Ferrero mark: a white serif "F" in a ringed blue seal. Original artwork, not the confectioner's logo. */
export function Monogram({ size = 36, className }: { size?: number; className?: string }) {
  // One gradient id per logo: when ids repeat, browsers use the first, which may sit in a hidden element (no fill).
  const gradient = `ferrero-mark-${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  return (
    <svg viewBox="0 0 64 64" width={size} height={size} className={clsx("shrink-0", className)} aria-hidden>
      <defs>
        <linearGradient id={gradient} x1="0.1" y1="0" x2="0.9" y2="1">
          <stop offset="0" stopColor="#3b7bf2" />
          <stop offset="1" stopColor="#1b46c4" />
        </linearGradient>
      </defs>
      <circle cx="32" cy="32" r="32" fill={`url(#${gradient})`} />
      <circle cx="32" cy="32" r="27.2" fill="none" stroke="#ffffff" strokeWidth="1.1" opacity="0.4" />
      <path fill="#ffffff"
        d="M20 18H44V26.5H42.6L41.2 20.8H31.5V30.6H38.2L39.4 27.4H40.6V36.4H39.4L38.2 33.2H31.5V43.6H36V46H21V43.6H25.5V20.8H20Z" />
    </svg>
  );
}

/** The mark with the product name beside it. `onDark`: on the navigation and the brand panels. */
export function Brand({ onDark = false, size = "md", className }: { onDark?: boolean; size?: "sm" | "md" | "lg"; className?: string }) {
  const mark = size === "lg" ? 44 : size === "sm" ? 32 : 38;
  return (
    <span className={clsx("inline-flex items-center gap-3", className)}>
      <Monogram size={mark} />
      <span className="leading-none">
        <span className={clsx("font-display block font-[600]", size === "lg" ? "text-[23px]" : size === "sm" ? "text-[18px]" : "text-[20px]",
          onDark ? "text-on-brand" : "text-ink")}>Ferrero</span>
        <span className={clsx("mt-1.5 block whitespace-nowrap font-medium uppercase tracking-[0.18em]", size === "lg" ? "text-[10.5px]" : "text-[9.5px]",
          onDark ? "text-brand-accent/85" : "text-accent-ink")}>Case Intelligence</span>
      </span>
    </span>
  );
}
