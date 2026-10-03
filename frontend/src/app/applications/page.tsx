"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ClipboardList, Columns3, Inbox, List, Plus } from "lucide-react";
import { useRequireAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import type { ApplicationOut, ApplicationStage } from "@/lib/types";
import { STAGE_META, currentStage, daysUntil, deadlineLabel, deadlineTone, isAlertSource } from "@/lib/stages";
import { ApplicationRow, RowList } from "@/components/ApplicationRow";
import { Badge, buttonClasses, CompanyAvatar, EmptyState, PageHeader, Skeleton } from "@/components/ui";

type Group = { key: string; label: string; stages: ApplicationStage[] | null; dot: string };

const GROUPS: Group[] = [
  { key: "all", label: "All", stages: null, dot: "" },
  { key: "review", label: "To review", stages: ["READY_TO_APPLY", "MANUAL_APPLY_REQUIRED"], dot: "bg-accent" },
  { key: "progress", label: "In progress", stages: ["DISCOVERED", "ELIGIBILITY_CHECKED", "PREPARING"], dot: "bg-subtle" },
  { key: "applied", label: "Applied", stages: ["APPLIED"], dot: "bg-info" },
  { key: "interviewing", label: "Interviewing", stages: ["OA", "INTERVIEW"], dot: "bg-warn" },
  { key: "offer", label: "Offer", stages: ["OFFER"], dot: "bg-ok" },
  { key: "closed", label: "Closed", stages: ["REJECTED", "SKIPPED_BY_USER"], dot: "bg-bad" },
];

function inGroup(app: ApplicationOut, g: Group): boolean {
  const s = currentStage(app);
  return g.stages === null || (s !== null && g.stages.includes(s));
}

const VIEW_KEY = "pathlight_applications_view";

function BoardCard({ app }: { app: ApplicationOut }) {
  const stage = currentStage(app);
  const days = app.deadline ? daysUntil(app.deadline) : null;
  return (
    <Link
      href={`/applications/${app.id}`}
      className="card block rounded-lg p-3 transition-[border-color,box-shadow] hover:border-line-strong hover:shadow-card-lg"
    >
      <div className="flex items-start gap-2.5">
        <CompanyAvatar name={app.company_name} size="sm" />
        <div className="min-w-0">
          <div className="line-clamp-2 text-[13px] font-medium leading-snug text-fg">{app.role}</div>
          <div className="mt-0.5 truncate text-xs text-muted">{app.company_name}</div>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        {stage && <span className="text-[11px] text-subtle">{STAGE_META[stage].label}</span>}
        {isAlertSource(app.source) && <Inbox size={11} className="text-subtle" />}
        {days !== null && days >= 0 && days <= 30 && (
          <Badge tone={deadlineTone(days)} className="ml-auto">
            {deadlineLabel(days)}
          </Badge>
        )}
      </div>
    </Link>
  );
}

export default function ApplicationsPage() {
  const { user, loading: authLoading } = useRequireAuth();
  const [applications, setApplications] = useState<ApplicationOut[] | null>(null);
  const [group, setGroup] = useState("all");
  const [view, setView] = useState<"list" | "board">("list");

  useEffect(() => {
    try {
      if (window.localStorage.getItem(VIEW_KEY) === "board") setView("board");
    } catch {
      // storage unavailable — default view
    }
  }, []);

  useEffect(() => {
    if (user) api.listApplications().then(setApplications).catch(() => setApplications([]));
  }, [user]);

  const counts = useMemo(() => {
    const out: Record<string, number> = {};
    for (const g of GROUPS) out[g.key] = (applications ?? []).filter((a) => inGroup(a, g)).length;
    return out;
  }, [applications]);

  const switchView = (v: "list" | "board") => {
    setView(v);
    try {
      window.localStorage.setItem(VIEW_KEY, v);
    } catch {
      // ignore
    }
  };

  if (authLoading || !user) return null;

  const active = GROUPS.find((g) => g.key === group)!;
  const visible = (applications ?? []).filter((a) => inGroup(a, active));

  return (
    <div className="space-y-6">
      <div className="animate-fade-in">
        <PageHeader
          title="Applications"
          subtitle="Every opportunity in your pipeline, from discovered to offer."
          actions={
            <>
              <div className="inline-flex rounded-lg border border-line bg-surface-2 p-0.5" role="tablist" aria-label="View">
                {(
                  [
                    ["list", List, "List"],
                    ["board", Columns3, "Board"],
                  ] as const
                ).map(([key, Icon, label]) => (
                  <button
                    key={key}
                    role="tab"
                    aria-selected={view === key}
                    onClick={() => switchView(key)}
                    className={`flex h-7 items-center gap-1.5 rounded-md px-2.5 text-[13px] font-medium transition-all ${
                      view === key ? "bg-surface text-fg shadow-xs ring-1 ring-line" : "text-muted hover:text-fg"
                    }`}
                  >
                    <Icon size={13} /> {label}
                  </button>
                ))}
              </div>
              <Link href="/opportunities" className={buttonClasses("primary", "md")}>
                <Plus size={15} /> Add
              </Link>
            </>
          }
        />
      </div>

      {applications === null ? (
        <Skeleton className="h-64" />
      ) : applications.length === 0 ? (
        <EmptyState
          icon={ClipboardList}
          title="No applications yet"
          description="Analyse an opportunity or connect Gmail to start your pipeline."
          action={
            <Link href="/opportunities" className={buttonClasses("primary", "md")}>
              <Plus size={15} /> Add an opportunity
            </Link>
          }
        />
      ) : view === "board" ? (
        <div className="-mx-4 overflow-x-auto px-4 pb-2 sm:mx-0 sm:px-0">
          <div className="flex w-max gap-3">
            {GROUPS.filter((g) => g.stages !== null).map((g) => {
              const items = applications.filter((a) => inGroup(a, g));
              return (
                <div key={g.key} className="w-[248px] shrink-0 rounded-xl border border-line bg-bg-subtle p-2">
                  <div className="flex items-center gap-2 px-1.5 pb-2 pt-1 text-[13px] font-medium text-fg">
                    <span className={`h-2 w-2 rounded-full ${g.dot}`} />
                    {g.label}
                    <span className="ml-auto text-xs tabular-nums text-subtle">{items.length}</span>
                  </div>
                  <div className="space-y-2">
                    {items.map((app) => (
                      <BoardCard key={app.id} app={app} />
                    ))}
                    {items.length === 0 && <div className="rounded-lg border border-dashed border-line px-3 py-6 text-center text-xs text-subtle">Empty</div>}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        <>
          <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
            <div className="flex w-max gap-1">
              {GROUPS.map((g) => (
                <button
                  key={g.key}
                  onClick={() => setGroup(g.key)}
                  className={`flex h-8 items-center gap-2 rounded-lg px-3 text-[13px] font-medium transition-colors ${
                    group === g.key ? "bg-ink text-ink-fg" : "text-muted hover:bg-surface-hover hover:text-fg"
                  }`}
                >
                  {g.dot && <span className={`h-1.5 w-1.5 rounded-full ${g.dot}`} />}
                  {g.label}
                  <span className={`text-xs tabular-nums ${group === g.key ? "opacity-70" : "text-subtle"}`}>{counts[g.key] ?? 0}</span>
                </button>
              ))}
            </div>
          </div>
          {visible.length === 0 ? (
            <p className="py-12 text-center text-sm text-muted">Nothing in “{active.label}” right now.</p>
          ) : (
            <RowList>
              {visible.map((app) => (
                <ApplicationRow key={app.id} app={app} />
              ))}
            </RowList>
          )}
        </>
      )}
    </div>
  );
}
