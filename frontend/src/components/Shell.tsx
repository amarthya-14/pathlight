"use client";

import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { BrandMark } from "./Brand";
import { CommandPalette, useCommandPalette } from "./CommandPalette";
import { MobileNav, Sidebar } from "./Sidebar";

// Public pages render full-bleed with their own layout. "/" (the landing page) stays
// public even when signed in — it shows "Open dashboard" instead of sign-up CTAs.
const PUBLIC_ROUTES = new Set(["/", "/login", "/register"]);

/** Applies the sidebar + app chrome only once a user is signed in AND the route isn't
 * public — otherwise a still-valid session would render dashboard chrome behind the
 * login form. */
export function Shell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const pathname = usePathname();
  const palette = useCommandPalette();

  if (PUBLIC_ROUTES.has(pathname)) return <>{children}</>;

  // Avoids a sidebar-then-no-sidebar layout flash while the initial /me check resolves.
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="animate-pulse">
          <BrandMark size={36} />
        </div>
      </div>
    );
  }

  if (!user) return <>{children}</>;

  return (
    <div className="flex min-h-screen">
      <Sidebar onSearch={() => palette.setOpen(true)} />
      <div className="min-w-0 flex-1">
        <MobileNav onSearch={() => palette.setOpen(true)} />
        <main className="px-4 pb-28 pt-6 sm:px-8 lg:px-12 lg:pb-16 lg:pt-10">
          <div className="mx-auto max-w-[1080px]">{children}</div>
        </main>
      </div>
      <CommandPalette open={palette.open} onClose={() => palette.setOpen(false)} />
    </div>
  );
}
