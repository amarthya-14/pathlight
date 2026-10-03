"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { needsOnboarding, useAuth } from "@/lib/auth-context";
import { BrandMark } from "./Brand";
import { CommandPalette, useCommandPalette } from "./CommandPalette";
import { MobileNav, Sidebar } from "./Sidebar";
import { buttonClasses } from "./ui";

// Public pages render full-bleed with their own layout. "/" (the landing page) stays
// public even when signed in — it shows "Open dashboard" instead of sign-up CTAs.
const PUBLIC_ROUTES = new Set(["/", "/login", "/register", "/forgot-password", "/reset-password", "/auth/callback", "/privacy", "/terms"]);
// Signed-in but full-bleed: the welcome flow has its own focused layout.
const FOCUSED_ROUTES = new Set(["/welcome"]);

function Unreachable({ onRetry }: { onRetry: () => void }) {
  const [retrying, setRetrying] = useState(false);
  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-6 text-center">
      <span className="brand-loading">
        <BrandMark size={36} />
      </span>
      <h1 className="mt-6 text-lg font-semibold text-fg">Pathlight is waking up</h1>
      <p className="mt-2 max-w-sm text-sm leading-relaxed text-muted">
        The server sleeps when nobody&apos;s using it and takes up to a minute to start. You&apos;re still signed in.
      </p>
      <button
        onClick={async () => {
          setRetrying(true);
          await onRetry();
          setRetrying(false);
        }}
        disabled={retrying}
        className={buttonClasses("secondary", "md", "mt-6")}
      >
        {retrying ? "Trying…" : "Try again"}
      </button>
    </div>
  );
}

export function FullScreenLoader() {
  return (
    <div className="flex min-h-screen items-center justify-center" aria-busy="true" aria-label="Loading">
      <span className="brand-loading">
        <BrandMark size={36} />
      </span>
    </div>
  );
}

/** Applies the sidebar + app chrome only once a user is signed in AND the route isn't
 * public — otherwise a still-valid session would render dashboard chrome behind the
 * login form. Also routes people who haven't told Pathlight who they are to /welcome. */
export function Shell({ children }: { children: React.ReactNode }) {
  const { user, profile, loading, unreachable, refresh } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const palette = useCommandPalette();

  const isPublic = PUBLIC_ROUTES.has(pathname);
  const onboarding = !isPublic && !FOCUSED_ROUTES.has(pathname) && needsOnboarding(user, profile);

  useEffect(() => {
    if (!loading && onboarding) router.replace("/welcome");
  }, [loading, onboarding, router]);

  if (isPublic) return <>{children}</>;

  // Avoids a sidebar-then-no-sidebar layout flash while the initial /me check resolves.
  if (loading || onboarding) return <FullScreenLoader />;
  if (unreachable && !user) return <Unreachable onRetry={refresh} />;

  if (!user || FOCUSED_ROUTES.has(pathname)) return <>{children}</>;

  return (
    <div className="flex min-h-screen">
      <Sidebar onSearch={() => palette.setOpen(true)} />
      <div className="min-w-0 flex-1">
        <MobileNav onSearch={() => palette.setOpen(true)} />
        <main className="px-4 pb-28 pt-6 sm:px-8 lg:px-12 lg:pb-16 lg:pt-10">
          {/* Keyed by route so every page enters with the same short settle. */}
          <div key={pathname} className="page-enter mx-auto max-w-[1080px]">
            {children}
          </div>
        </main>
      </div>
      <CommandPalette open={palette.open} onClose={() => palette.setOpen(false)} />
    </div>
  );
}
