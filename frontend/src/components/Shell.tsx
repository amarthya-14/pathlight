"use client";

import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Sidebar } from "./Sidebar";

const AUTH_ROUTES = new Set(["/login", "/register"]);

/** Applies the sidebar + padded dashboard shell only once a user is signed in AND the
 * current route isn't login/register — otherwise a still-valid session (localStorage
 * token) would render the dashboard sidebar behind the login form if someone manually
 * navigated to /login while already signed in. Auth pages always render full-bleed. */
export function Shell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const pathname = usePathname();

  if (AUTH_ROUTES.has(pathname)) return <>{children}</>;

  // Avoids a sidebar-then-no-sidebar layout flash while the initial /me check resolves.
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-slate-200 border-t-indigo-500" />
      </div>
    );
  }

  if (!user) return <>{children}</>;

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="min-w-0 flex-1 px-6 py-8 sm:px-10 lg:px-12">
        <div className="mx-auto max-w-5xl">{children}</div>
      </main>
    </div>
  );
}
