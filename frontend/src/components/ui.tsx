import type {
  ButtonHTMLAttributes,
  HTMLAttributes,
  InputHTMLAttributes,
  LabelHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";
import type { LucideIcon } from "lucide-react";
import { AlertTriangle, CheckCircle2, Info, Loader2, XCircle } from "lucide-react";

// Pathlight UI primitives (Aurora design system). Every page composes these; colors come
// from semantic tokens in globals.css, so light/dark both work without per-page branches.

function cx(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}

export type Tone = "neutral" | "accent" | "ok" | "warn" | "bad" | "info";

const TONE_TEXT: Record<Tone, string> = {
  neutral: "text-muted",
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
        {eyebrow && <div className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-accent-fg">{eyebrow}</div>}
        <h1 className="text-[1.75rem] font-semibold leading-tight tracking-tight text-fg sm:text-3xl">{title}</h1>
        {subtitle && <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted sm:text-[0.95rem]">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function SectionLabel({ children, action }: { children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="mb-3 flex items-center justify-between gap-3">
      <h2 className="text-xs font-semibold uppercase tracking-[0.16em] text-subtle">{children}</h2>
      {action}
    </div>
  );
}

export function Card({
  className,
  interactive,
  glow,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement> & { interactive?: boolean; glow?: boolean }) {
  return (
    <div
      {...props}
      className={cx(
        "glass rounded-2xl",
        interactive && "transition-all duration-200 hover:-translate-y-0.5 hover:border-line-strong hover:bg-surface-hover",
        glow && "glow-border",
        className
      )}
    >
      {children}
    </div>
  );
}

// ── Forms ───────────────────────────────────────────────────────────────────

export function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1.5 block text-sm font-medium text-fg">{label}</label>
      {children}
      {hint && <p className="mt-1.5 text-xs leading-relaxed text-subtle">{hint}</p>}
    </div>
  );
}

const fieldClasses =
  "w-full rounded-xl border border-line bg-surface-2 px-3.5 py-2.5 text-sm text-fg placeholder:text-subtle transition-all focus:border-accent focus:bg-surface-solid focus:outline-none focus:ring-4 focus:ring-accent/15";

export function TextInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cx(fieldClasses, props.className)} />;
}

export function TextArea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={cx(fieldClasses, "resize-y leading-relaxed", props.className)} />;
}

export function Label(props: LabelHTMLAttributes<HTMLLabelElement>) {
  return <label {...props} className={cx("text-sm font-medium text-fg", props.className)} />;
}

// ── Buttons ─────────────────────────────────────────────────────────────────

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md" | "lg";

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary:
    "btn-sheen bg-brand-gradient text-white shadow-[0_8px_24px_-8px_rgb(124_58_237/0.6)] hover:shadow-[0_10px_32px_-6px_rgb(124_58_237/0.75)] hover:brightness-110",
  secondary: "border border-line bg-surface-2 text-fg hover:border-line-strong hover:bg-surface-hover",
  ghost: "text-muted hover:bg-surface-2 hover:text-fg",
  danger: "border border-bad/30 bg-bad-soft text-bad hover:bg-bad/15",
};
const BUTTON_SIZES: Record<ButtonSize, string> = {
  sm: "h-8 gap-1.5 rounded-lg px-3 text-xs",
  md: "h-10 gap-2 rounded-xl px-4 text-sm",
  lg: "h-12 gap-2 rounded-xl px-6 text-[0.95rem]",
};

export function buttonClasses(variant: ButtonVariant = "primary", size: ButtonSize = "md", className?: string) {
  return cx(
    "inline-flex items-center justify-center whitespace-nowrap font-semibold transition-all duration-200 active:scale-[0.97] disabled:pointer-events-none disabled:opacity-50",
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
      {loading && <Loader2 size={size === "sm" ? 13 : 16} className="animate-spin" />}
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
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-medium",
        TONE_SOFT[tone],
        className
      )}
    >
      {dot && <span className={cx("h-1.5 w-1.5 rounded-full", TONE_DOT[tone])} />}
      {Icon && <Icon size={12} strokeWidth={2.4} />}
      {children}
    </span>
  );
}

export function IconTile({ icon: Icon, tone = "accent", size = "md" }: { icon: LucideIcon; tone?: Tone; size?: "sm" | "md" | "lg" }) {
  const dims = { sm: "h-8 w-8 rounded-lg", md: "h-10 w-10 rounded-xl", lg: "h-12 w-12 rounded-2xl" }[size];
  const icon = { sm: 15, md: 18, lg: 22 }[size];
  return (
    <div className={cx("flex shrink-0 items-center justify-center", dims, TONE_SOFT[tone])}>
      <Icon size={icon} strokeWidth={2.1} />
    </div>
  );
}

export function StatCard({
  icon,
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
    <Card className="p-5">
      <div className="flex items-start justify-between">
        <IconTile icon={icon} tone={mapped === "neutral" ? "accent" : mapped} size="sm" />
      </div>
      <div className={cx("mt-4 text-2xl font-semibold tracking-tight", mapped === "neutral" ? "text-fg" : TONE_TEXT[mapped])}>
        {value}
      </div>
      <div className="mt-0.5 text-xs text-muted">{label}</div>
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
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-line-strong bg-surface px-6 py-14 text-center">
      <div className="relative mb-5">
        <div className="absolute inset-0 rounded-2xl bg-accent/30 blur-xl" />
        <div className="relative flex h-14 w-14 items-center justify-center rounded-2xl border border-line bg-surface-solid text-accent-fg">
          <Icon size={24} strokeWidth={1.75} />
        </div>
      </div>
      <div className="text-base font-semibold text-fg">{title}</div>
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
    <div className={cx("flex items-start gap-3 rounded-xl px-4 py-3 text-sm", TONE_SOFT[tone], className)} role="status">
      <Icon size={17} className="mt-0.5 shrink-0" strokeWidth={2.2} />
      <div className="min-w-0 flex-1 leading-relaxed">
        {title && <div className="font-semibold">{title}</div>}
        {children && <div className={title ? "mt-0.5 opacity-90" : ""}>{children}</div>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

export function Spinner({ size = 20 }: { size?: number }) {
  return <Loader2 size={size} className="animate-spin text-accent" />;
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("skeleton", className)} />;
}

export function PageSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading">
      <Skeleton className="h-9 w-64" />
      <Skeleton className="h-4 w-96 max-w-full" />
      <div className="grid gap-4 sm:grid-cols-3">
        <Skeleton className="h-32" />
        <Skeleton className="h-32" />
        <Skeleton className="h-32" />
      </div>
      <Skeleton className="h-48" />
    </div>
  );
}

// Deterministic per-company gradient avatar with initials — every company gets a
// recognizable color without needing a logo service.
const AVATAR_GRADIENTS = [
  "from-violet-500 to-indigo-500",
  "from-cyan-500 to-blue-500",
  "from-fuchsia-500 to-violet-500",
  "from-emerald-500 to-teal-500",
  "from-amber-500 to-orange-500",
  "from-rose-500 to-pink-500",
  "from-sky-500 to-indigo-500",
  "from-teal-500 to-cyan-500",
];

export function CompanyAvatar({ name, size = "md" }: { name: string; size?: "sm" | "md" | "lg" }) {
  const hash = [...name].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7);
  const words = name.trim().split(/\s+/).filter(Boolean);
  const initials = (words.length > 1 ? words[0][0] + words[1][0] : name.slice(0, 2)).toUpperCase();
  const dims = { sm: "h-9 w-9 rounded-lg text-xs", md: "h-11 w-11 rounded-xl text-sm", lg: "h-16 w-16 rounded-2xl text-xl" }[size];
  return (
    <div
      className={cx(
        "flex shrink-0 items-center justify-center bg-gradient-to-br font-semibold text-white shadow-lg shadow-black/10",
        AVATAR_GRADIENTS[hash % AVATAR_GRADIENTS.length],
        dims
      )}
      aria-hidden
    >
      {initials}
    </div>
  );
}

export function Divider({ className }: { className?: string }) {
  return <div className={cx("h-px w-full bg-line", className)} />;
}
