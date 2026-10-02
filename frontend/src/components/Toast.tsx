"use client";

import { createContext, useCallback, useContext, useRef, useState } from "react";
import { CheckCircle2, Info, X, XCircle } from "lucide-react";

type ToastTone = "ok" | "bad" | "info";
type ToastItem = { id: number; title: string; description?: string; tone: ToastTone };
type ToastFn = (title: string, opts?: { description?: string; tone?: ToastTone }) => void;

const ToastContext = createContext<ToastFn | null>(null);

const ICON = { ok: CheckCircle2, bad: XCircle, info: Info };
const ICON_COLOR = { ok: "text-ok", bad: "text-bad", info: "text-info" };

// Lightweight toasts for confirming actions ("Saved", "Application sent") without
// shifting the page layout. Bottom-right on desktop, top on phones (clear of the tab bar).
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), []);

  const toast = useCallback<ToastFn>(
    (title, opts) => {
      const id = nextId.current++;
      setToasts((t) => [...t.slice(-2), { id, title, description: opts?.description, tone: opts?.tone ?? "ok" }]);
      setTimeout(() => dismiss(id), 4200);
    },
    [dismiss]
  );

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed inset-x-3 top-3 z-[60] flex flex-col items-center gap-2 sm:inset-x-auto sm:bottom-5 sm:right-5 sm:top-auto sm:items-end"
      >
        {toasts.map((t) => {
          const Icon = ICON[t.tone];
          return (
            <div
              key={t.id}
              className="card animate-scale-in pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-xl px-4 py-3 shadow-card-lg"
            >
              <Icon size={17} className={`mt-[1px] shrink-0 ${ICON_COLOR[t.tone]}`} />
              <div className="min-w-0 flex-1">
                <div className="text-[13px] font-medium text-fg">{t.title}</div>
                {t.description && <div className="mt-0.5 text-xs leading-relaxed text-muted">{t.description}</div>}
              </div>
              <button onClick={() => dismiss(t.id)} aria-label="Dismiss" className="text-subtle transition-colors hover:text-fg">
                <X size={14} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastFn {
  // Outside the provider (isolated unit tests) toasts are a no-op.
  return useContext(ToastContext) ?? (() => {});
}
