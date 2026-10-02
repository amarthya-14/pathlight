"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Briefcase, ClipboardList, LayoutDashboard, LogOut, Mail, Search, UserRound } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import { currentStage } from "@/lib/stages";
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

function useReviewCount(pathname: string): number {
  const [count, setCount] = useState(0);
  useEffect(() => {
    api
      .listApplications()
      .then((apps) =>
        setCount(apps.filter((a) => ["READY_TO_APPLY", "MANUAL_APPLY_REQUIRED"].includes(currentStage(a) ?? "")).length)
      )
      .catch(() => {});
  }, [pathname]);
  return count;
}

export function Sidebar({ onSearch }: { onSearch: () => void }) {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const reviewCount = useReviewCount(pathname);

  if (!user) return null;

  return (
    <aside className="sticky top-0 z-20 hidden h-screen w-[244px] shrink-0 flex-col border-r border-line bg-bg-subtle lg:flex">
      <div className="flex items-center justify-between px-4 pb-4 pt-5">
        <Brand href="/dashboard" />
        <ThemeToggle />
      </div>

      <div className="px-3">
        <button
          onClick={onSearch}
          className="flex h-8 w-full items-center gap-2 rounded-lg border border-line bg-surface px-2.5 text-[13px] text-subtle shadow-xs transition-colors hover:border-line-strong hover:text-muted"
        >
          <Search size={14} />
          <span className="flex-1 text-left">Search…</span>
          <kbd className="kbd">⌘K</kbd>
        </button>
      </div>

      <nav className="mt-4 flex-1 space-y-0.5 px-3" aria-label="Main">
        {NAV_LINKS.map((link) => {
          const active = isActive(pathname, link.href);
          const Icon = link.icon;
          const badge = link.href === "/applications" && reviewCount > 0 ? reviewCount : null;
          return (
            <Link
              key={link.href}
              href={link.href}
              aria-current={active ? "page" : undefined}
              className={`flex h-8 items-center gap-2.5 rounded-lg px-2.5 text-[13px] font-medium transition-colors ${
                active ? "bg-surface text-fg shadow-xs ring-1 ring-line" : "text-muted hover:bg-surface-hover hover:text-fg"
              }`}
            >
              <Icon size={15} strokeWidth={1.9} className={active ? "text-fg" : "text-subtle"} />
              <span className="flex-1">{link.label}</span>
              {badge !== null && (
                <span className="flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-accent px-1 text-[10px] font-semibold text-white">
                  {badge}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-line p-3">
        <div className="flex items-center gap-2.5 rounded-lg px-1.5 py-1">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-ink text-[10px] font-semibold text-ink-fg">
            {user.email.slice(0, 2).toUpperCase()}
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-[13px] font-medium text-fg">{user.email.split("@")[0]}</div>
            <div className="truncate text-[11px] text-subtle">{user.email}</div>
          </div>
          <button
            onClick={() => {
              logout();
              router.push("/login");
            }}
            title="Log out"
            aria-label="Log out"
            className="flex h-7 w-7 items-center justify-center rounded-md text-subtle transition-colors hover:bg-surface-hover hover:text-fg"
          >
            <LogOut size={14} />
          </button>
        </div>
      </div>
    </aside>
  );
}

// Phones: compact top bar + app-style bottom tab bar (the sidebar is hidden < lg).
export function MobileNav({ onSearch }: { onSearch: () => void }) {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  if (!user) return null;

  return (
    <>
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-line bg-bg/85 px-4 py-2.5 backdrop-blur-xl lg:hidden">
        <Brand href="/dashboard" size={24} />
        <div className="flex items-center gap-0.5">
          <button onClick={onSearch} aria-label="Search" className="flex h-8 w-8 items-center justify-center rounded-lg text-muted hover:bg-surface-hover">
            <Search size={16} />
          </button>
          <ThemeToggle />
          <button
            onClick={() => {
              logout();
              router.push("/login");
            }}
            aria-label="Log out"
            className="flex h-8 w-8 items-center justify-center rounded-lg text-muted hover:bg-surface-hover"
          >
            <LogOut size={15} />
          </button>
        </div>
      </header>

      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 z-30 flex items-center justify-around border-t border-line bg-bg/90 px-2 pt-1.5 backdrop-blur-xl lg:hidden"
        style={{ paddingBottom: "max(0.5rem, env(safe-area-inset-bottom))" }}
      >
        {NAV_LINKS.map((link) => {
          const active = isActive(pathname, link.href);
          const Icon = link.icon;
          return (
            <Link
              key={link.href}
              href={link.href}
              aria-current={active ? "page" : undefined}
              className={`flex min-w-0 flex-1 flex-col items-center gap-1 py-1 text-[10px] font-medium transition-colors ${
                active ? "text-fg" : "text-subtle"
              }`}
            >
              <Icon size={19} strokeWidth={active ? 2.2 : 1.8} />
              {link.short}
            </Link>
          );
        })}
      </nav>
    </>
  );
}
