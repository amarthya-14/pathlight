"use client";

import { useState } from "react";
import { BadgeCheck, Eye, EyeOff, Inbox, MousePointerClick, ScanSearch, Wand2 } from "lucide-react";
import { Brand } from "./Brand";
import { ThemeToggle } from "./ThemeToggle";
import { api, ApiError } from "@/lib/api";
import { fieldClasses, useFieldId } from "./ui";

const STEPS = [
  { icon: Inbox, label: "New alert — SDE Intern at Acme" },
  { icon: BadgeCheck, label: "Eligible — CGPA 8.5 ≥ 7.0, freshers welcome" },
  { icon: ScanSearch, label: "Skill gap — 4 matched, 1 missing" },
  { icon: Wand2, label: "Resume tailored for this role" },
  { icon: MousePointerClick, label: "Waiting for your approval" },
];

// Split-screen auth: an editorial panel on the left (desktop), the form on the right.
export function AuthLayout({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  footer: React.ReactNode;
}) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
      <aside className="relative hidden flex-col justify-between border-r border-line bg-bg-subtle p-12 lg:flex">
        <Brand />
        <div className="max-w-md">
          <h2 className="text-[2.6rem] font-semibold leading-[1.08] tracking-[-0.04em] text-fg">
            Every opportunity,
            <br />
            <span className="font-display font-normal italic">handled.</span>
          </h2>
          <p className="mt-4 leading-relaxed text-muted">
            While you prepare, Pathlight discovers roles, checks fit and gets each application ready. You just approve.
          </p>
          <ol className="mt-10 space-y-0 overflow-hidden rounded-xl border border-line bg-surface shadow-card">
            {STEPS.map(({ icon: Icon, label }, i) => (
              <li
                key={label}
                className={`flex items-center gap-3 px-4 py-3 text-[13px] ${i > 0 ? "border-t border-line" : ""} ${
                  i === STEPS.length - 1 ? "font-medium text-fg" : "text-muted"
                }`}
              >
                <Icon size={15} className={i === STEPS.length - 1 ? "text-accent" : "text-subtle"} strokeWidth={1.9} />
                {label}
              </li>
            ))}
          </ol>
        </div>
        <p className="text-xs text-subtle">Never invents skills · You approve every application</p>
      </aside>

      <main className="flex min-h-screen flex-col px-5 py-5 sm:px-10">
        <div className="flex items-center justify-between lg:justify-end">
          <span className="lg:hidden">
            <Brand />
          </span>
          <ThemeToggle />
        </div>
        <div className="flex flex-1 items-center justify-center py-10">
          <div className="animate-fade-up w-full max-w-[380px]">
            <h1 className="text-[1.8rem] font-semibold tracking-[-0.03em] text-fg">{title}</h1>
            <p className="mt-1.5 text-sm text-muted">{subtitle}</p>
            <div className="mt-8">{children}</div>
            <div className="mt-8 border-t border-line pt-6 text-center text-[13px] text-muted">{footer}</div>
          </div>
        </div>
      </main>
    </div>
  );
}

export function PasswordInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  const [visible, setVisible] = useState(false);
  const fieldId = useFieldId();
  return (
    <div className="relative">
      <input id={fieldId} {...props} type={visible ? "text" : "password"} className={`${fieldClasses} h-9 pr-10`} />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? "Hide password" : "Show password"}
        className="absolute right-1 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md text-subtle transition-colors hover:text-fg"
      >
        {visible ? <EyeOff size={15} /> : <Eye size={15} />}
      </button>
    </div>
  );
}

/** "Continue with Google" + an "or" divider. Google sign-in means no password to forget. */
export function GoogleButton({ label = "Continue with Google" }: { label?: string }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <div>
      <button
        type="button"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          setError(null);
          try {
            const { auth_url } = await api.googleLoginUrl();
            window.location.assign(auth_url);
          } catch (err) {
            setError(err instanceof ApiError ? err.detail : "Google sign-in is unavailable right now.");
            setBusy(false);
          }
        }}
        className="flex h-10 w-full items-center justify-center gap-2.5 rounded-lg border border-line-strong bg-surface text-sm font-medium text-fg shadow-xs transition-[background-color,transform] duration-150 hover:bg-surface-hover active:scale-[0.99] disabled:opacity-60"
      >
        <svg width="17" height="17" viewBox="0 0 48 48" aria-hidden>
          <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z" />
          <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
          <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z" />
          <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z" />
        </svg>
        {busy ? "Opening Google…" : label}
      </button>
      {error && <p className="mt-2 text-center text-xs text-bad">{error}</p>}
      <div className="my-5 flex items-center gap-3 text-xs text-subtle">
        <span className="h-px flex-1 bg-line" /> or use email <span className="h-px flex-1 bg-line" />
      </div>
    </div>
  );
}
