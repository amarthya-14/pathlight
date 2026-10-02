"use client";

import { useState } from "react";
import { BadgeCheck, Eye, EyeOff, Inbox, MousePointerClick, ScanSearch, Wand2 } from "lucide-react";
import { Brand } from "./Brand";
import { ThemeToggle } from "./ThemeToggle";

const STEPS = [
  { icon: Inbox, label: "New alert: SDE Intern at Acme", tone: "text-info bg-info-soft" },
  { icon: BadgeCheck, label: "Eligible — CGPA 8.5 ≥ 7.0", tone: "text-ok bg-ok-soft" },
  { icon: ScanSearch, label: "Skill gap: 4 matched, 1 missing", tone: "text-warn bg-warn-soft" },
  { icon: Wand2, label: "Resume tailored for this role", tone: "text-accent-fg bg-accent-soft" },
  { icon: MousePointerClick, label: "Waiting for your approval", tone: "text-fg bg-surface-2" },
];

// Split-screen auth layout: a living product preview on the left (desktop), the form
// on the right in a glass card.
export function AuthLayout({ title, subtitle, children, footer }: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  footer: React.ReactNode;
}) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <aside className="relative hidden flex-col justify-between overflow-hidden border-r border-line p-12 lg:flex">
        <div className="absolute -left-32 top-1/4 h-96 w-96 rounded-full bg-violet-600/25 blur-3xl" />
        <div className="absolute -bottom-20 right-0 h-80 w-80 rounded-full bg-cyan-500/15 blur-3xl" />
        <Brand />
        <div className="relative">
          <h2 className="max-w-md text-4xl font-semibold leading-tight tracking-tight text-fg">
            Every opportunity, <span className="text-gradient">handled.</span>
          </h2>
          <p className="mt-4 max-w-md leading-relaxed text-muted">
            While you prepare, Pathlight discovers roles, checks fit and gets your application ready — you just approve.
          </p>
          <ul className="stagger mt-10 max-w-sm space-y-2.5">
            {STEPS.map(({ icon: Icon, label, tone }) => (
              <li key={label} className="glass flex items-center gap-3 rounded-2xl px-4 py-3 text-sm text-fg">
                <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${tone}`}>
                  <Icon size={15} />
                </span>
                {label}
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-xs text-subtle">Never invents skills · You approve every application</p>
      </aside>

      <main className="flex min-h-screen flex-col px-5 py-6 sm:px-10">
        <div className="flex items-center justify-between lg:justify-end">
          <span className="lg:hidden">
            <Brand />
          </span>
          <ThemeToggle />
        </div>
        <div className="flex flex-1 items-center justify-center py-10">
          <div className="animate-fade-up w-full max-w-[400px]">
            <h1 className="text-3xl font-semibold tracking-tight text-fg">{title}</h1>
            <p className="mt-2 text-sm text-muted">{subtitle}</p>
            <div className="glass mt-8 rounded-3xl p-6 shadow-card-lg sm:p-7">{children}</div>
            <div className="mt-6 text-center text-sm text-muted">{footer}</div>
          </div>
        </div>
      </main>
    </div>
  );
}

export function PasswordInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <input
        {...props}
        type={visible ? "text" : "password"}
        className="w-full rounded-xl border border-line bg-surface-2 py-2.5 pl-3.5 pr-11 text-sm text-fg placeholder:text-subtle transition-all focus:border-accent focus:bg-surface-solid focus:outline-none focus:ring-4 focus:ring-accent/15"
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? "Hide password" : "Show password"}
        className="absolute right-1.5 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-lg text-subtle transition-colors hover:text-fg"
      >
        {visible ? <EyeOff size={16} /> : <Eye size={16} />}
      </button>
    </div>
  );
}
