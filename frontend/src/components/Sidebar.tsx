"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Briefcase, ClipboardList, Compass, LogOut, UserRound } from "lucide-react";
import { useAuth } from "@/lib/auth-context";

const LINKS = [
  { href: "/", label: "Home", icon: Compass },
  { href: "/opportunities", label: "Opportunities", icon: Briefcase },
  { href: "/applications", label: "Applications", icon: ClipboardList },
  { href: "/profile", label: "Profile", icon: UserRound },
];

function initials(email: string): string {
  return email.slice(0, 2).toUpperCase();
}

export function Sidebar() {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  if (!user) return null;

  return (
    <aside className="sticky top-0 flex h-screen w-64 shrink-0 flex-col border-r border-slate-200/80 bg-white/80 backdrop-blur-xl">
      <div className="flex items-center gap-2 px-6 py-6">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 text-sm font-bold text-white shadow-sm">
          P
        </div>
        <span className="text-lg font-semibold tracking-tight text-slate-900">Pathlight</span>
      </div>

      <nav className="flex-1 space-y-1 px-3">
        {LINKS.map((link) => {
          const active = pathname === link.href;
          const Icon = link.icon;
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all ${
                active
                  ? "bg-gradient-to-r from-indigo-50 to-violet-50 text-indigo-700 shadow-[inset_0_0_0_1px_rgba(99,102,241,0.15)]"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              }`}
            >
              <Icon
                size={18}
                strokeWidth={2}
                className={active ? "text-indigo-600" : "text-slate-400 group-hover:text-slate-600"}
              />
              {link.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-slate-200/80 p-3">
        <div className="flex items-center gap-3 rounded-lg px-2 py-2">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-900 text-xs font-semibold text-white">
            {initials(user.email)}
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium text-slate-800">{user.email}</div>
          </div>
          <button
            onClick={() => {
              logout();
              router.push("/login");
            }}
            title="Log out"
            className="rounded-md p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
          >
            <LogOut size={16} />
          </button>
        </div>
      </div>
    </aside>
  );
}
