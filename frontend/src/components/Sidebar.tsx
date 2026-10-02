"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Briefcase, ClipboardList, LayoutDashboard, LogOut, Mail, UserRound } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { Brand } from "./Brand";
import { ThemeToggle } from "./ThemeToggle";

export const NAV_LINKS = [
  { href: "/dashboard", label: "Dashboard", short: "Home", icon: LayoutDashboard },
  { href: "/opportunities", label: "Opportunities", short: "Discover", icon: Briefcase },
  { href: "/applications", label: "Applications", short: "Apply", icon: ClipboardList },
  { href: "/integrations", label: "Integrations", short: "Gmail", icon: Mail },
  { href: "/profile", label: "Profile", short: "Profile", icon: UserRound },
];

export function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

function initials(email: string): string {
  return email.slice(0, 2).toUpperCase();
}

export function Sidebar() {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  if (!user) return null;

  return (
    <aside className="sticky top-0 z-20 hidden h-screen w-[264px] shrink-0 flex-col border-r border-line bg-surface backdrop-blur-xl lg:flex">
      <div className="px-6 pb-6 pt-7">
        <Brand href="/dashboard" />
      </div>

      <nav className="flex-1 space-y-1 px-3" aria-label="Main">
        {NAV_LINKS.map((link) => {
          const active = isActive(pathname, link.href);
          const Icon = link.icon;
          return (
            <Link
              key={link.href}
              href={link.href}
              aria-current={active ? "page" : undefined}
              className={`group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all ${
                active ? "bg-accent-soft text-fg" : "text-muted hover:bg-surface-2 hover:text-fg"
              }`}
            >
              {active && (
                <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-brand-gradient shadow-[0_0_12px_rgb(139_92_246/0.8)]" />
              )}
              <Icon
                size={18}
                strokeWidth={2}
                className={active ? "text-accent-fg" : "text-subtle transition-colors group-hover:text-muted"}
              />
              {link.label}
            </Link>
          );
        })}
      </nav>

      <div className="mx-3 mb-3 rounded-2xl border border-line bg-surface-2 p-3">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-gradient text-xs font-semibold text-white">
            {initials(user.email)}
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium text-fg">{user.email.split("@")[0]}</div>
            <div className="truncate text-xs text-subtle">{user.email}</div>
          </div>
        </div>
        <div className="mt-3 flex items-center gap-2">
          <ThemeToggle />
          <button
            onClick={() => {
              logout();
              router.push("/login");
            }}
            className="flex h-9 flex-1 items-center justify-center gap-2 rounded-xl border border-line bg-surface-2 text-xs font-medium text-muted transition-all hover:border-line-strong hover:text-fg"
          >
            <LogOut size={14} /> Log out
          </button>
        </div>
      </div>
    </aside>
  );
}

// Phones: compact top bar + app-style bottom tab bar (the sidebar is hidden < lg).
export function MobileNav() {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  if (!user) return null;

  return (
    <>
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-line bg-bg-elevated/80 px-4 py-3 backdrop-blur-xl lg:hidden">
        <Brand href="/dashboard" size={26} />
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <button
            onClick={() => {
              logout();
              router.push("/login");
            }}
            aria-label="Log out"
            className="flex h-9 w-9 items-center justify-center rounded-xl border border-line bg-surface-2 text-muted"
          >
            <LogOut size={15} />
          </button>
        </div>
      </header>

      <nav
        aria-label="Main"
        className="fixed inset-x-3 bottom-3 z-30 flex items-center justify-around rounded-2xl border border-line-strong bg-bg-elevated/90 px-1 py-1.5 shadow-card-lg backdrop-blur-xl lg:hidden"
        style={{ paddingBottom: "max(0.375rem, env(safe-area-inset-bottom))" }}
      >
        {NAV_LINKS.map((link) => {
          const active = isActive(pathname, link.href);
          const Icon = link.icon;
          return (
            <Link
              key={link.href}
              href={link.href}
              aria-current={active ? "page" : undefined}
              className={`flex min-w-0 flex-1 flex-col items-center gap-0.5 rounded-xl py-1.5 text-[10px] font-medium transition-colors ${
                active ? "text-accent-fg" : "text-subtle"
              }`}
            >
              <span className={`flex h-7 w-10 items-center justify-center rounded-full transition-all ${active ? "bg-accent-soft" : ""}`}>
                <Icon size={18} strokeWidth={active ? 2.3 : 2} />
              </span>
              {link.short}
            </Link>
          );
        })}
      </nav>
    </>
  );
}
