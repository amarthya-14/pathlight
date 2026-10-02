"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

// Theme = what the user picked; "system" follows the OS. The *resolved* theme lives on
// <html data-theme>, set before first paint by THEME_INIT_SCRIPT (see layout.tsx), so
// there's never a flash of the wrong theme. This provider only handles changes after load.

export type ThemeChoice = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

const STORAGE_KEY = "pathlight_theme";

export const THEME_INIT_SCRIPT = `(function(){try{var c=localStorage.getItem("${STORAGE_KEY}");var t=c==="light"||c==="dark"?c:(window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light");document.documentElement.setAttribute("data-theme",t)}catch(e){}})()`;

type ThemeState = {
  choice: ThemeChoice;
  resolved: ResolvedTheme;
  setChoice: (choice: ThemeChoice) => void;
  toggle: () => void;
};

const ThemeContext = createContext<ThemeState | null>(null);

function systemTheme(): ResolvedTheme {
  if (typeof window === "undefined" || !window.matchMedia) return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function readChoice(): ThemeChoice {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return stored === "light" || stored === "dark" ? stored : "system";
  } catch {
    return "system";
  }
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [choice, setChoiceState] = useState<ThemeChoice>("system");
  const [resolved, setResolved] = useState<ResolvedTheme>("light");

  const apply = useCallback((next: ThemeChoice) => {
    const theme = next === "system" ? systemTheme() : next;
    document.documentElement.setAttribute("data-theme", theme);
    setResolved(theme);
  }, []);

  useEffect(() => {
    const initial = readChoice();
    setChoiceState(initial);
    apply(initial);

    const media = window.matchMedia?.("(prefers-color-scheme: dark)");
    const onSystemChange = () => {
      if (readChoice() === "system") apply("system");
    };
    media?.addEventListener?.("change", onSystemChange);
    return () => media?.removeEventListener?.("change", onSystemChange);
  }, [apply]);

  const setChoice = useCallback(
    (next: ThemeChoice) => {
      try {
        if (next === "system") window.localStorage.removeItem(STORAGE_KEY);
        else window.localStorage.setItem(STORAGE_KEY, next);
      } catch {
        // storage unavailable (private mode) — still switch for this session
      }
      setChoiceState(next);
      apply(next);
    },
    [apply]
  );

  const toggle = useCallback(() => setChoice(resolved === "dark" ? "light" : "dark"), [resolved, setChoice]);

  return <ThemeContext.Provider value={{ choice, resolved, setChoice, toggle }}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeState {
  const ctx = useContext(ThemeContext);
  // Components rendered outside the provider (e.g. isolated unit tests) get a no-op theme.
  return ctx ?? { choice: "system", resolved: "light", setChoice: () => {}, toggle: () => {} };
}
