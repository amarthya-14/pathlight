"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, clearToken, getToken } from "./api";
import type { ProfileOut, UserOut } from "./types";

type AuthState = {
  user: UserOut | null;
  /** The student's profile — null until loaded, or if it couldn't be. */
  profile: ProfileOut | null;
  loading: boolean;
  /** The server couldn't be reached (e.g. a free host waking up) — NOT the same as
   * being logged out, so nobody gets bounced to /login by a slow cold start. */
  unreachable: boolean;
  refresh: () => Promise<void>;
  setUser: (user: UserOut) => void;
  setProfile: (profile: ProfileOut) => void;
  logout: () => void;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [profile, setProfile] = useState<ProfileOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [unreachable, setUnreachable] = useState(false);

  const refresh = async () => {
    if (!getToken()) {
      setUser(null);
      setProfile(null);
      setLoading(false);
      return;
    }
    try {
      const me = await meWithRetry();
      setUnreachable(false);
      setUser(me);
      // Best-effort: the app works without it, it just can't personalise yet. Its own
      // try, so a profile hiccup never signs the user out.
      try {
        setProfile(await api.getProfile());
      } catch {
        setProfile(null);
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 0) {
        // Network-level failure: keep the session, say the server is unreachable.
        setUnreachable(true);
      } else {
        clearToken();
        setUser(null);
        setProfile(null);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const logout = () => {
    clearToken();
    setUser(null);
    setProfile(null);
  };

  return (
    <AuthContext.Provider value={{ user, profile, loading, unreachable, refresh, setUser, setProfile, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

// Free hosts take up to a minute to wake; retry network failures (not 401s) with backoff.
const RETRY_DELAYS_MS = [1500, 4000, 8000, 15000];

async function meWithRetry(): Promise<UserOut> {
  for (let attempt = 0; ; attempt++) {
    try {
      return await api.me();
    } catch (err) {
      const network = err instanceof ApiError && err.status === 0;
      if (!network || attempt >= RETRY_DELAYS_MS.length) throw err;
      await new Promise((r) => setTimeout(r, RETRY_DELAYS_MS[attempt]));
    }
  }
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

/** Redirects to /login if not authenticated once the initial auth check settles. */
export function useRequireAuth(): AuthState {
  const auth = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!auth.loading && !auth.user && !auth.unreachable) {
      router.replace("/login");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.loading, auth.user]);

  return auth;
}

const SKIP_KEY = "pathlight_onboarding_skipped";

export function markOnboardingSeen(): void {
  try {
    window.localStorage.setItem(SKIP_KEY, "1");
  } catch {
    // storage unavailable — they'll just see the welcome flow again next time
  }
}

/** Whether to send this user through /welcome: no name yet, no profile yet, or nothing
 * about what they're looking for (unless they chose to skip those optional steps). */
export function needsOnboarding(user: UserOut | null, profile: ProfileOut | null): boolean {
  if (!user) return false;
  if (!user.full_name?.trim()) return true;
  if (profile === null) return false; // couldn't load — don't trap them in a redirect
  if (!profile.id) return true;
  let skipped = false;
  try {
    skipped = window.localStorage.getItem(SKIP_KEY) === "1";
  } catch {
    skipped = false;
  }
  return !skipped && profile.target_roles.length === 0 && profile.graduation_year === null;
}

/** First name for greetings: "Asha Rao" -> "Asha"; falls back to the email's name part. */
export function firstName(user: UserOut | null): string {
  if (!user) return "";
  const fromName = user.full_name?.trim().split(/\s+/)[0];
  if (fromName) return fromName;
  const local = user.email.split("@")[0].replace(/[._-]+/g, " ").replace(/\d+/g, "").trim().split(" ")[0];
  return local ? local[0].toUpperCase() + local.slice(1) : "there";
}

export function initials(user: UserOut | null): string {
  if (!user) return "";
  const parts = (user.full_name ?? "").trim().split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return user.email.slice(0, 2).toUpperCase();
}
