import Link from "next/link";

// Pathlight mark: a single ink tile with a path that ends in a point of light. One
// color (follows the theme's ink), no gradients — reads cleanly at 16px.
export function BrandMark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden className="text-ink">
      <rect width="32" height="32" rx="8" fill="currentColor" />
      <path
        d="M8.5 23.5c4-1 6-3.5 7.5-7s3.5-6 6.5-7"
        stroke="var(--ink-fg)"
        strokeWidth="2.3"
        strokeLinecap="round"
        opacity="0.9"
      />
      <circle cx="22.5" cy="9.5" r="2.4" fill="var(--ink-fg)" />
      <circle cx="8.5" cy="23.5" r="1.5" fill="var(--ink-fg)" opacity="0.55" />
    </svg>
  );
}

export function Brand({ href = "/", size = 26 }: { href?: string; size?: number }) {
  return (
    <Link href={href} className="flex items-center gap-2.5" aria-label="Pathlight home">
      <BrandMark size={size} />
      <span className="text-[15px] font-semibold tracking-[-0.02em] text-fg">Pathlight</span>
    </Link>
  );
}
