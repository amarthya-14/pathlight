import { createContext, useContext, useId } from "react";
import type {
  ButtonHTMLAttributes,
  CSSProperties,
  HTMLAttributes,
  LabelHTMLAttributes,
} from "react";
import type { LucideIcon } from "lucide-react";
import { AlertTriangle, CheckCircle2, Info, Loader2, XCircle } from "lucide-react";

// Pathlight UI primitives. Quiet by default: hairline borders, ink-black primary
// actions, color reserved for meaning (status), never decoration. All colors come from
// semantic tokens in globals.css, so light/dark both work without per-page branches.

export function cx(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}

export type Tone = "neutral" | "accent" | "ok" | "warn" | "bad" | "info";

const TONE_TEXT: Record<Tone, string> = {
  neutral: "text-fg",
  accent: "text-accent-fg",
  ok: "text-ok",
  warn: "text-warn",
  bad: "text-bad",
  info: "text-info",
};
const TONE_SOFT: Record<Tone, string> = {
  neutral: "bg-surface-2 text-muted",
  accent: "bg-accent-soft text-accent-fg",
  ok: "bg-ok-soft text-ok",
  warn: "bg-warn-soft text-warn",
  bad: "bg-bad-soft text-bad",
  info: "bg-info-soft text-info",
};
const TONE_DOT: Record<Tone, string> = {
  neutral: "bg-subtle",
  accent: "bg-accent",
  ok: "bg-ok",
  warn: "bg-warn",
  bad: "bg-bad",
  info: "bg-info",
};

// ── Layout ──────────────────────────────────────────────────────────────────

export function PageHeader({
  title,
  subtitle,
  eyebrow,
  actions,
}: {
  title: string;
  subtitle?: string;
  eyebrow?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {eyebrow && <div className="mb-2 text-[13px] font-medium text-subtle">{eyebrow}</div>}
        <h1 className="text-[1.65rem] font-semibold leading-tight tracking-[-0.025em] text-fg sm:text-[1.85rem]">{title}</h1>
        {subtitle && <p className="mt-2 max-w-2xl text-[0.94rem] leading-relaxed text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function SectionLabel({ children, action }: { children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="mb-3 flex items-center justify-between gap-3">
      <h2 className="text-[13px] font-medium text-subtle">{children}</h2>
      {action}
    </div>
  );
}

export function Card({
  className,
  interactive,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement> & { interactive?: boolean; glow?: boolean }) {
  // `glow` is accepted (and ignored) for call-site compatibility; the design has no glows.
  const { glow: _glow, ...rest } = props as typeof props & { glow?: boolean };
  void _glow;
  return (
    <div
      {...rest}
      className={cx(
        "card rounded-xl",
        interactive && "transition-[border-color,box-shadow,transform] duration-200 hover:border-line-strong hover:shadow-card-lg",
        className
      )}
    >
      {children}
    </div>
  );
}

// ── Forms ───────────────────────────────────────────────────────────────────

// Links a Field's <label> to the TextInput/TextArea inside it (htmlFor/id), so screen
// readers announce the label and clicking it focuses the input.
const FieldContext = createContext<string | undefined>(undefined);

/** The id of the enclosing Field's input — for custom inputs built outside ui.tsx. */
export function useFieldId(): string | undefined {
  return useContext(FieldContext);
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-[13px] font-medium text-fg">
        {label}
      </label>
      <FieldContext.Provider value={id}>{children}</FieldContext.Provider>
      {hint && <p className="mt-1.5 text-xs leading-relaxed text-subtle">{hint}</p>}
    </div>
  );
}

export const fieldClasses =
  "w-full rounded-lg border border-line-strong bg-surface px-3 py-2 text-sm text-fg shadow-xs placeholder:text-subtle transition-[border-color,box-shadow] focus:border-accent focus:outline-none focus:ring-[3px] focus:ring-accent/15 disabled:opacity-60";

export function TextInput(props: React.ComponentProps<"input">) {
  const fieldId = useContext(FieldContext);
  return <input id={fieldId} {...props} className={cx(fieldClasses, "h-9", props.className)} />;
}

// React 19: `ref` is a plain prop, so ComponentProps<"textarea"> lets callers pass one.
export function TextArea(props: React.ComponentProps<"textarea">) {
  const fieldId = useContext(FieldContext);
  return <textarea id={fieldId} {...props} className={cx(fieldClasses, "resize-y leading-relaxed", props.className)} />;
}

export function Label(props: LabelHTMLAttributes<HTMLLabelElement>) {
  return <label {...props} className={cx("text-[13px] font-medium text-fg", props.className)} />;
}

// ── Buttons ─────────────────────────────────────────────────────────────────

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "accent";
type ButtonSize = "sm" | "md" | "lg";

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary: "bg-ink text-ink-fg shadow-xs hover:bg-ink-hover",
  accent: "bg-accent text-white shadow-xs hover:brightness-110",
  secondary: "border border-line-strong bg-surface text-fg shadow-xs hover:bg-surface-hover",
  ghost: "text-muted hover:bg-surface-hover hover:text-fg",
  danger: "border border-line-strong bg-surface text-bad shadow-xs hover:bg-bad-soft",
};
const BUTTON_SIZES: Record<ButtonSize, string> = {
  sm: "h-7 gap-1.5 rounded-md px-2.5 text-xs",
  md: "h-9 gap-2 rounded-lg px-3.5 text-[13px]",
  lg: "h-10 gap-2 rounded-lg px-4.5 text-sm",
};

export function buttonClasses(variant: ButtonVariant = "primary", size: ButtonSize = "md", className?: string) {
  return cx(
    "inline-flex items-center justify-center whitespace-nowrap font-medium transition-[background-color,color,box-shadow,filter,transform] duration-150 active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50",
    BUTTON_VARIANTS[variant],
    BUTTON_SIZES[size],
    className
  );
}

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  className,
  children,
  disabled,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: ButtonSize; loading?: boolean }) {
  return (
    <button {...props} disabled={disabled || loading} className={buttonClasses(variant, size, className)}>
      {loading && <Loader2 size={size === "sm" ? 12 : 14} className="animate-spin" />}
      {children}
    </button>
  );
}

// ── Data display ────────────────────────────────────────────────────────────

export function Badge({
  tone = "neutral",
  dot,
  icon: Icon,
  className,
  children,
}: {
  tone?: Tone;
  dot?: boolean;
  icon?: LucideIcon;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cx(
        "inline-flex h-[22px] items-center gap-1.5 whitespace-nowrap rounded-md px-2 text-xs font-medium",
        TONE_SOFT[tone],
        className
      )}
    >
      {dot && <span className={cx("h-1.5 w-1.5 rounded-full", TONE_DOT[tone])} />}
      {Icon && <Icon size={12} strokeWidth={2.2} />}
      {children}
    </span>
  );
}

export function IconTile({ icon: Icon, tone = "neutral", size = "md" }: { icon: LucideIcon; tone?: Tone; size?: "sm" | "md" | "lg" }) {
  const dims = { sm: "h-7 w-7 rounded-md", md: "h-9 w-9 rounded-lg", lg: "h-11 w-11 rounded-xl" }[size];
  const icon = { sm: 14, md: 17, lg: 20 }[size];
  return (
    <div
      className={cx(
        "flex shrink-0 items-center justify-center",
        dims,
        tone === "neutral" ? "border border-line bg-surface-2 text-muted" : TONE_SOFT[tone]
      )}
    >
      <Icon size={icon} strokeWidth={1.9} />
    </div>
  );
}

export function StatCard({
  icon: Icon,
  value,
  label,
  tone = "neutral",
  hint,
}: {
  icon: LucideIcon;
  value: React.ReactNode;
  label: string;
  tone?: "neutral" | "danger" | "warning" | "success" | Tone;
  hint?: React.ReactNode;
}) {
  const mapped: Tone = tone === "danger" ? "bad" : tone === "warning" ? "warn" : tone === "success" ? "ok" : tone;
  return (
    <Card className="p-4 sm:p-5">
      <div className="flex items-center justify-between">
        <div className="text-[13px] text-muted">{label}</div>
        <Icon size={15} className="text-subtle" strokeWidth={1.9} />
      </div>
      <div className={cx("mt-3 text-[1.7rem] font-semibold leading-none tracking-tight tabular-nums", TONE_TEXT[mapped])}>{value}</div>
      {hint && <div className="mt-2 text-xs text-subtle">{hint}</div>}
    </Card>
  );
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: LucideIcon;
  title: string;
  description?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-line-strong px-6 py-14 text-center">
      <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl border border-line bg-surface text-muted shadow-xs">
        <Icon size={20} strokeWidth={1.7} />
      </div>
      <div className="text-[15px] font-semibold text-fg">{title}</div>
      {description && <div className="mt-1.5 max-w-sm text-sm leading-relaxed text-muted">{description}</div>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}

const ALERT_ICON: Record<Tone, LucideIcon> = {
  neutral: Info,
  accent: Info,
  info: Info,
  ok: CheckCircle2,
  warn: AlertTriangle,
  bad: XCircle,
};

export function Alert({
  tone = "info",
  title,
  children,
  action,
  className,
}: {
  tone?: Tone;
  title?: React.ReactNode;
  children?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  const Icon = ALERT_ICON[tone];
  return (
    <div className={cx("flex items-start gap-2.5 rounded-lg px-3.5 py-2.5 text-[13px]", TONE_SOFT[tone], className)} role="status">
      <Icon size={15} className="mt-[1px] shrink-0" strokeWidth={2.1} />
      <div className="min-w-0 flex-1 leading-relaxed">
        {title && <div className="font-semibold">{title}</div>}
        {children && <div className={title ? "mt-0.5 opacity-90" : ""}>{children}</div>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

export function Spinner({ size = 18 }: { size?: number }) {
  return <Loader2 size={size} className="animate-spin text-subtle" />;
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("skeleton", className)} />;
}

export function PageSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading">
      <Skeleton className="h-8 w-60" />
      <Skeleton className="h-4 w-96 max-w-full" />
      <div className="grid gap-4 sm:grid-cols-3">
        <Skeleton className="h-24" />
        <Skeleton className="h-24" />
        <Skeleton className="h-24" />
      </div>
      <Skeleton className="h-48" />
    </div>
  );
}

function hueFor(name: string): number {
  const hash = [...name].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7);
  return hash % 360;
}

// Initials tile tinted by a per-company hue — recognizable at a glance, quiet enough
// to sit in a list of twenty without turning into confetti.
export function CompanyAvatar({ name, size = "md" }: { name: string; size?: "sm" | "md" | "lg" }) {
  const words = name.trim().split(/\s+/).filter(Boolean);
  const initials = (words.length > 1 ? words[0][0] + words[1][0] : name.slice(0, 2)).toUpperCase();
  const dims = { sm: "h-8 w-8 rounded-lg text-[11px]", md: "h-10 w-10 rounded-lg text-xs", lg: "h-14 w-14 rounded-xl text-base" }[size];
  return (
    <div
      className={cx("avatar-tint flex shrink-0 items-center justify-center font-semibold tracking-wide", dims)}
      style={{ "--h": hueFor(name) } as CSSProperties}
      aria-hidden
    >
      {initials}
    </div>
  );
}

export function Divider({ className }: { className?: string }) {
  return <div className={cx("h-px w-full bg-line", className)} />;
}

export function Kbd({ children }: { children: React.ReactNode }) {
  return <kbd className="kbd">{children}</kbd>;
}

/** Thin determinate progress bar. */
export function Progress({ value, tone = "accent", className }: { value: number; tone?: Tone; className?: string }) {
  const color = { neutral: "bg-fg", accent: "bg-accent", ok: "bg-ok", warn: "bg-warn", bad: "bg-bad", info: "bg-info" }[tone];
  return (
    <div className={cx("h-1.5 overflow-hidden rounded-full bg-surface-hover", className)}>
      <div className={cx("h-full rounded-full transition-[width] duration-700 ease-out", color)} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  );
}
