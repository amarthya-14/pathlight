"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { LucideIcon } from "lucide-react";
import { ArrowRight, Briefcase, ClipboardList, Compass, LayoutDashboard, Mail, Moon, Plus, Search, Sun, UserRound } from "lucide-react";
import { api } from "@/lib/api";
import { useTheme } from "@/lib/theme";
import type { ApplicationOut } from "@/lib/types";
import { STAGE_META, currentStage } from "@/lib/stages";
import { CompanyAvatar } from "./ui";

type Item = {
  id: string;
  group: string;
  label: string;
  hint?: string;
  icon?: LucideIcon;
  company?: string;
  run: () => void;
};

// ⌘K / Ctrl+K: jump to any page or application, or run an action, from the keyboard.
export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const router = useRouter();
  const { resolved, toggle } = useTheme();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [applications, setApplications] = useState<ApplicationOut[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setActive(0);
    api.listApplications().then(setApplications).catch(() => {});
    const t = setTimeout(() => inputRef.current?.focus(), 10);
    return () => clearTimeout(t);
  }, [open]);

  const go = useCallback(
    (href: string) => {
      onClose();
      router.push(href);
    },
    [onClose, router]
  );

  const items: Item[] = useMemo(() => {
    const nav: Item[] = [
      { id: "nav-dash", group: "Go to", label: "Dashboard", icon: LayoutDashboard, run: () => go("/dashboard") },
      { id: "nav-jobs", group: "Go to", label: "Jobs for you", icon: Compass, run: () => go("/jobs") },
      { id: "nav-opp", group: "Go to", label: "Add a job", icon: Briefcase, run: () => go("/opportunities") },
      { id: "nav-apps", group: "Go to", label: "Applications", icon: ClipboardList, run: () => go("/applications") },
      { id: "nav-int", group: "Go to", label: "Gmail alerts", icon: Mail, run: () => go("/integrations") },
      { id: "nav-prof", group: "Go to", label: "Profile", icon: UserRound, run: () => go("/profile") },
    ];
    const actions: Item[] = [
      { id: "act-add", group: "Actions", label: "Add an opportunity", icon: Plus, run: () => go("/opportunities") },
      {
        id: "act-theme",
        group: "Actions",
        label: resolved === "dark" ? "Switch to light theme" : "Switch to dark theme",
        icon: resolved === "dark" ? Sun : Moon,
        run: () => {
          toggle();
          onClose();
        },
      },
    ];
    const apps: Item[] = applications.map((a) => {
      const s = currentStage(a);
      return {
        id: `app-${a.id}`,
        group: "Applications",
        label: a.role,
        hint: `${a.company_name}${s ? ` · ${STAGE_META[s].label}` : ""}`,
        company: a.company_name,
        run: () => go(`/applications/${a.id}`),
      };
    });
    const q = query.trim().toLowerCase();
    const all = [...actions, ...nav, ...apps];
    if (!q) return [...actions, ...nav, ...apps.slice(0, 5)];
    return all.filter((i) => `${i.label} ${i.hint ?? ""}`.toLowerCase().includes(q));
  }, [applications, query, go, resolved, toggle, onClose]);

  useEffect(() => setActive(0), [query]);

  useEffect(() => {
    (listRef.current?.querySelector(`[data-index="${active}"]`) as HTMLElement | null)?.scrollIntoView?.({ block: "nearest" });
  }, [active]);

  if (!open) return null;

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(i + 1, items.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      items[active]?.run();
    } else if (e.key === "Escape") {
      onClose();
    }
  };

  let lastGroup = "";
  return (
    <div className="fixed inset-0 z-[70] flex items-start justify-center px-4 pt-[12vh]" role="dialog" aria-modal="true" aria-label="Command menu">
      <div className="animate-overlay-in absolute inset-0 bg-black/30 backdrop-blur-[2px]" onClick={onClose} />
      <div className="card animate-scale-in relative w-full max-w-xl overflow-hidden rounded-xl shadow-card-lg" onKeyDown={onKeyDown}>
        <div className="flex items-center gap-3 border-b border-line px-4">
          <Search size={16} className="shrink-0 text-subtle" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search applications, pages, actions…"
            className="h-12 w-full bg-transparent text-[15px] text-fg placeholder:text-subtle focus:outline-none focus-visible:outline-none"
          />
          <kbd className="kbd">esc</kbd>
        </div>
        <div ref={listRef} className="max-h-[360px] overflow-y-auto p-1.5">
          {items.length === 0 && <div className="px-3 py-8 text-center text-sm text-subtle">No results for “{query}”</div>}
          {items.map((item, index) => {
            const showGroup = item.group !== lastGroup;
            lastGroup = item.group;
            const Icon = item.icon;
            return (
              <div key={item.id}>
                {showGroup && <div className="px-2.5 pb-1 pt-2.5 text-[11px] font-medium text-subtle">{item.group}</div>}
                <button
                  data-index={index}
                  onMouseMove={() => setActive(index)}
                  onClick={item.run}
                  className={`flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left text-sm transition-colors ${
                    index === active ? "bg-surface-hover text-fg" : "text-muted"
                  }`}
                >
                  {item.company ? (
                    <CompanyAvatar name={item.company} size="sm" />
                  ) : Icon ? (
                    <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-line bg-surface-2">
                      <Icon size={15} />
                    </span>
                  ) : null}
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium text-fg">{item.label}</span>
                    {item.hint && <span className="block truncate text-xs text-subtle">{item.hint}</span>}
                  </span>
                  {index === active && <ArrowRight size={14} className="shrink-0 text-subtle" />}
                </button>
              </div>
            );
          })}
        </div>
        <div className="flex items-center gap-4 border-t border-line bg-surface-2 px-4 py-2 text-[11px] text-subtle">
          <span className="flex items-center gap-1.5"><kbd className="kbd">↑</kbd><kbd className="kbd">↓</kbd> navigate</span>
          <span className="flex items-center gap-1.5"><kbd className="kbd">↵</kbd> open</span>
        </div>
      </div>
    </div>
  );
}

/** Global ⌘K / Ctrl+K listener + palette state. */
export function useCommandPalette() {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  return { open, setOpen };
}
