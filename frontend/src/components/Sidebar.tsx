"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { BarChart3, Briefcase, ClipboardList, Compass, LayoutDashboard, LogOut, Mail, Search, UserRound } from "lucide-react";
import { initials, useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import { currentStage } from "@/lib/stages";
import { Brand } from "./Brand";
import { ThemeToggle } from "./ThemeToggle";

export const NAV_LINKS = [
  { href: "/dashboard", label: "Dashboard", short: "Home", icon: LayoutDashboard, mobile: true },
  { href: "/jobs", label: "Jobs for you", short: "Jobs", icon: Compass, mobile: true },
  { href: "/opportunities", label: "Add a job", short: "Add", icon: Briefcase, mobile: false },
  { href: "/applications", label: "Applications", short: "Apply", icon: ClipboardList, mobile: true },
  { href: "/integrations", label: "Job alerts", short: "Alerts", icon: Mail, mobile: true },
  { href: "/profile", label: "Profile", short: "Profile", icon: UserRound, mobile: true },
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

const JOBS_SEEN_KEY = "pathlight_jobs_seen_at";
let newJobsCache: { at: number; count: number } | null = null;

/** Matches posted since the student last opened Jobs — fetched at most every 10 min. */
function useNewJobsCount(pathname: string): number {
  const [count, setCount] = useState(newJobsCache?.count ?? 0);
  useEffect(() => {
    let seen = 0;
    try {
      if (pathname === "/jobs") window.localStorage.setItem(JOBS_SEEN_KEY, String(Date.now()));
      seen = Number(window.localStorage.getItem(JOBS_SEEN_KEY) ?? 0);
    } catch {
      seen = 0;
    }
    if (pathname === "/jobs") {
      newJobsCache = { at: Date.now(), count: 0 };
      setCount(0);
      return;
    }
    if (newJobsCache && Date.now() - newJobsCache.at < 10 * 60_000) {
      setCount(newJobsCache.count);
      return;
    }
    api
      .jobFeed()
      .then((feed) => {
        const n = seen ? feed.items.filter((j) => j.posted_at && new Date(j.posted_at).getTime() > seen && !j.tracked_application_id).length : 0;
        newJobsCache = { at: Date.now(), count: n };
        setCount(n);
      })
      .catch(() => {});
  }, [pathname]);
  return count;
}

export function Sidebar({ onSearch }: { onSearch: () => void }) {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const reviewCount = useReviewCount(pathname);
  const newJobs = useNewJobsCount(pathname);
  const links = user?.is_admin ? [...NAV_LINKS, { href: "/admin", label: "Admin", short: "Admin", icon: BarChart3, mobile: false }] : NAV_LINKS;

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
        {links.map((link) => {
          const active = isActive(pathname, link.href);
          const Icon = link.icon;
          const badge =
            link.href === "/applications" && reviewCount > 0
              ? reviewCount
              : link.href === "/jobs" && newJobs > 0
                ? newJobs
                : null;
          return (
            <Link
              key={link.href}
              href={link.href}
              aria-current={active ? "page" : undefined}
              className={`flex h-8 items-center gap-2.5 rounded-lg px-2.5 text-[13px] font-medium transition-[background-color,color,box-shadow] duration-200 ${
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
          <Link href="/profile" className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-ink text-[10px] font-semibold text-ink-fg">
            {initials(user)}
          </Link>
          <div className="min-w-0 flex-1">
            <div className="truncate text-[13px] font-medium text-fg">{user.full_name || user.email.split("@")[0]}</div>
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
        {NAV_LINKS.filter((link) => link.mobile).map((link) => {
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
