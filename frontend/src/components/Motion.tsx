"use client";

import { useEffect, useRef, useState, type CSSProperties, type ElementType, type ReactNode } from "react";
import { cx } from "./ui";

// Small motion primitives on top of the CSS in globals.css. No animation library:
// IntersectionObserver + CSS transitions are enough, and keep the bundle small.

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

/** Adds .is-visible once the element scrolls into view (once). */
export function useInView<T extends Element>(threshold = 0.15) {
  const ref = useRef<T>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined" || prefersReducedMotion()) {
      setVisible(true);
      return;
    }
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          io.disconnect();
        }
      },
      { threshold, rootMargin: "0px 0px -6% 0px" }
    );
    io.observe(el);
    return () => io.disconnect();
  }, [threshold]);
  return { ref, visible };
}

export function Reveal({
  as: Tag = "div",
  delay = 0,
  sequence = false,
  className,
  children,
  ...rest
}: {
  as?: ElementType;
  delay?: number;
  /** Reveal children one by one instead of the block as a whole. */
  sequence?: boolean;
  className?: string;
  children: ReactNode;
} & Record<string, unknown>) {
  const { ref, visible } = useInView<HTMLElement>();
  return (
    <Tag
      ref={ref}
      {...rest}
      className={cx(sequence ? "reveal-seq" : "reveal", visible && "is-visible", className)}
      style={{ "--delay": `${delay}ms` } as CSSProperties}
    >
      {children}
    </Tag>
  );
}

/** Splits a line into words that rise in one after another. */
export function WordRise({ text, start = 0, className }: { text: string; start?: number; className?: string }) {
  return (
    <span className={className}>
      {text.split(" ").map((word, i) => (
        <span key={i} className="word-rise">
          <span style={{ "--i": i + start } as CSSProperties}>{word}</span>
          {i < text.split(" ").length - 1 ? " " : null}
        </span>
      ))}
    </span>
  );
}

/** Animates a number from 0 to `value` when it first appears. */
export function CountUp({ value, duration = 900 }: { value: number; duration?: number }) {
  const { ref, visible } = useInView<HTMLSpanElement>(0.3);
  const [shown, setShown] = useState(0);
  useEffect(() => {
    if (!visible) return;
    if (prefersReducedMotion() || value === 0) {
      setShown(value);
      return;
    }
    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 4);
      setShown(Math.round(value * eased));
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [visible, value, duration]);
  return <span ref={ref}>{shown}</span>;
}

/** Circular score (0-100) that fills in when it appears. */
export function ScoreRing({
  value,
  max = 100,
  size = 72,
  stroke = 6,
  tone = "accent",
  label,
}: {
  value: number;
  max?: number;
  size?: number;
  stroke?: number;
  tone?: "accent" | "ok" | "warn" | "bad";
  label?: ReactNode;
}) {
  const { ref, visible } = useInView<SVGSVGElement>(0.3);
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(1, value / max));
  const color = { accent: "var(--accent)", ok: "var(--ok)", warn: "var(--warn)", bad: "var(--bad)" }[tone];
  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg ref={ref} width={size} height={size} className="-rotate-90" aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--surface-hover)" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={visible ? c * (1 - pct) : c}
          className="ring-progress"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-lg font-semibold tabular-nums tracking-tight text-fg">
          <CountUp value={value} duration={1300} />
        </span>
        {label && <span className="-mt-0.5 text-[10px] font-medium uppercase tracking-wider text-subtle">{label}</span>}
      </div>
    </div>
  );
}
