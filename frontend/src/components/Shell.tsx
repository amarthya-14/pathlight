"use client";

import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { AuroraBackground } from "./AuroraBackground";
import { BrandMark } from "./Brand";
import { MobileNav, Sidebar } from "./Sidebar";

// Public pages render full-bleed with their own layout. Note "/" (the landing page)
// stays public even when signed in — it shows "Open dashboard" instead of sign-up CTAs.
const PUBLIC_ROUTES = new Set(["/", "/login", "/register"]);

/** Applies the sidebar + padded app shell only once a user is signed in AND the route
 * isn't public — otherwise a still-valid session would render the dashboard chrome
 * behind the login form. */
export function Shell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const pathname = usePathname();

  if (PUBLIC_ROUTES.has(pathname)) {
    return (
      <>
        <AuroraBackground />
        <div className="relative z-10">{children}</div>
      </>
    );
  }

  // Avoids a sidebar-then-no-sidebar layout flash while the initial /me check resolves.
  if (loading) {
    return (
      <>
        <AuroraBackground />
        <div className="relative z-10 flex min-h-screen items-center justify-center">
          <div className="animate-pulse-ring rounded-[10px]">
            <BrandMark size={44} />
          </div>
        </div>
      </>
    );
  }

  if (!user) {
    return (
      <>
        <AuroraBackground />
        <div className="relative z-10">{children}</div>
      </>
    );
  }

  return (
    <>
      <AuroraBackground />
      <div className="relative z-10 flex min-h-screen">
        <Sidebar />
        <div className="min-w-0 flex-1">
          <MobileNav />
          <main className="px-4 pb-28 pt-6 sm:px-8 lg:px-12 lg:pb-16 lg:pt-10">
            <div className="mx-auto max-w-6xl">{children}</div>
          </main>
        </div>
      </div>
    </>
  );
}
