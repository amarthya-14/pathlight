"use client";

import { useState } from "react";
import { BadgeCheck, Eye, EyeOff, Inbox, MousePointerClick, ScanSearch, Wand2 } from "lucide-react";
import { Brand } from "./Brand";
import { ThemeToggle } from "./ThemeToggle";
import { fieldClasses } from "./ui";

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
  return (
    <div className="relative">
      <input {...props} type={visible ? "text" : "password"} className={`${fieldClasses} h-9 pr-10`} />
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
