import clsx from "clsx";
import { useId } from "react";

/** The Ferrero monogram: a champagne "F" on an ink tile. Original artwork, not the confectioner's logo. */
export function Monogram({ size = 36, className }: { size?: number; className?: string }) {
  // One gradient id per logo: when ids repeat, browsers use the first, which may sit in a hidden element (no fill).
  const gradient = `ferrero-gold-${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  return (
    <span className={clsx("relative grid place-items-center overflow-hidden rounded-[30%] bg-[#141519] ring-1 ring-white/10", className)}
      style={{ width: size, height: size }} aria-hidden>
      <span className="absolute inset-0 bg-[radial-gradient(120%_90%_at_20%_0%,rgba(201,164,101,0.35),transparent_60%)]" />
      <svg viewBox="0 0 64 64" width={size * 0.62} height={size * 0.62} className="relative">
        <defs>
          <linearGradient id={gradient} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#e8cf9a" />
            <stop offset="1" stopColor="#b08a4a" />
          </linearGradient>
        </defs>
        <path d="M18 54V10h30v9H28.5v9.5H45v9H28.5V54z" fill={`url(#${gradient})`} />
      </svg>
    </span>
  );
}
