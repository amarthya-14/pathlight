import Link from "next/link";

// Pathlight mark: three ascending steps on an ink tile, each brighter than the last —
// a path upward that lights up as you climb. Geometric, one color (follows the theme's
// ink), reads cleanly at 16px. `animate` lights the steps up one after another.
export function BrandMark({ size = 28, animate = false }: { size?: number; animate?: boolean }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden
      className={`shrink-0 text-ink ${animate ? "brand-animate" : ""}`}
    >
      <rect width="32" height="32" rx="8.5" fill="currentColor" />
      <rect className="brand-step" x="6.5" y="19" width="6.5" height="6.5" rx="1.7" fill="var(--ink-fg)" opacity="0.38" />
      <rect className="brand-step" x="12.75" y="12.75" width="6.5" height="6.5" rx="1.7" fill="var(--ink-fg)" opacity="0.68" />
      <rect className="brand-step" x="19" y="6.5" width="6.5" height="6.5" rx="1.7" fill="var(--ink-fg)" />
    </svg>
  );
}

export function Brand({ href = "/", size = 26 }: { href?: string; size?: number }) {
  return (
    <Link href={href} className="group flex items-center gap-2.5" aria-label="Pathlight home">
      <span className="transition-transform duration-300 ease-out group-hover:-translate-y-px">
        <BrandMark size={size} />
      </span>
      <span className="text-[15px] font-semibold tracking-[-0.02em] text-fg">Pathlight</span>
    </Link>
  );
}
