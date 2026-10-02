"use client";

import { useId } from "react";
import Link from "next/link";

// Pathlight mark: a beam of light along a path — a rounded square with a gradient
// "light ray" stroke and a glowing endpoint.
export function BrandMark({ size = 32 }: { size?: number }) {
  // Unique gradient ids per instance: with duplicate ids, a copy inside a display:none
  // container (e.g. the desktop sidebar on phones) "owns" the gradient and every other
  // instance renders without its background.
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const bg = `pl-bg-${uid}`;
  const dot = `pl-dot-${uid}`;
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden>
      <defs>
        <linearGradient id={bg} x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop stopColor="#8B5CF6" />
          <stop offset="0.55" stopColor="#6366F1" />
          <stop offset="1" stopColor="#06B6D4" />
        </linearGradient>
        <radialGradient id={dot} cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(22.5 9.5) scale(5)">
          <stop stopColor="#fff" />
          <stop offset="1" stopColor="#fff" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill={`url(#${bg})`} />
      <path d="M8.5 23.5c4-1 6-3.5 7.5-7s3.5-6 6.5-7" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" opacity="0.95" />
      <circle cx="22.5" cy="9.5" r="5" fill={`url(#${dot})`} opacity="0.55" />
      <circle cx="22.5" cy="9.5" r="2.1" fill="#fff" />
      <circle cx="8.5" cy="23.5" r="1.6" fill="#fff" opacity="0.7" />
    </svg>
  );
}

export function Brand({ href = "/", size = 30 }: { href?: string; size?: number }) {
  return (
    <Link href={href} className="group flex items-center gap-2.5" aria-label="Pathlight home">
      <span className="transition-transform duration-300 group-hover:rotate-[-6deg] group-hover:scale-105">
        <BrandMark size={size} />
      </span>
      <span className="text-[1.05rem] font-semibold tracking-tight text-fg">Pathlight</span>
    </Link>
  );
}
