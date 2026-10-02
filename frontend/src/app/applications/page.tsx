"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ClipboardList, Plus } from "lucide-react";
import { useRequireAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import type { ApplicationOut, ApplicationStage } from "@/lib/types";
import { currentStage } from "@/lib/stages";
import { ApplicationRow } from "@/components/ApplicationRow";
import { buttonClasses, EmptyState, PageHeader, Skeleton } from "@/components/ui";

const GROUPS: { key: string; label: string; stages: ApplicationStage[] | null }[] = [
  { key: "all", label: "All", stages: null },
  { key: "review", label: "To review", stages: ["READY_TO_APPLY", "MANUAL_APPLY_REQUIRED"] },
  { key: "progress", label: "In progress", stages: ["DISCOVERED", "ELIGIBILITY_CHECKED", "PREPARING"] },
  { key: "applied", label: "Applied", stages: ["APPLIED", "OA", "INTERVIEW", "OFFER"] },
  { key: "closed", label: "Closed", stages: ["REJECTED", "SKIPPED_BY_USER"] },
];

export default function ApplicationsPage() {
  const { user, loading: authLoading } = useRequireAuth();
  const [applications, setApplications] = useState<ApplicationOut[] | null>(null);
  const [group, setGroup] = useState("all");

  useEffect(() => {
    if (user) api.listApplications().then(setApplications).catch(() => setApplications([]));
  }, [user]);

  const counts = useMemo(() => {
    const out: Record<string, number> = {};
    for (const g of GROUPS) {
      out[g.key] = (applications ?? []).filter((a) => {
        const s = currentStage(a);
        return g.stages === null || (s !== null && g.stages.includes(s));
      }).length;
    }
    return out;
  }, [applications]);

  if (authLoading || !user) return null;

  const active = GROUPS.find((g) => g.key === group)!;
  const visible = (applications ?? []).filter((a) => {
    const s = currentStage(a);
    return active.stages === null || (s !== null && active.stages.includes(s));
  });

  return (
    <div className="space-y-8">
      <div className="animate-fade-in">
        <PageHeader
          eyebrow="Apply"
          title="Applications"
          subtitle="Every opportunity in your pipeline and where it stands — from discovered to applied."
          actions={
            <Link href="/opportunities" className={buttonClasses("secondary", "md")}>
              <Plus size={16} /> Add
            </Link>
          }
        />
      </div>

      <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
        <div className="flex w-max gap-2">
          {GROUPS.map((g) => (
            <button
              key={g.key}
              onClick={() => setGroup(g.key)}
              className={`flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition-all ${
                group === g.key
                  ? "border-transparent bg-brand-gradient text-white shadow-glow"
                  : "border-line bg-surface-2 text-muted hover:border-line-strong hover:text-fg"
              }`}
            >
              {g.label}
              <span
                className={`rounded-full px-1.5 text-xs tabular-nums ${group === g.key ? "bg-white/20" : "bg-surface-hover text-subtle"}`}
              >
                {counts[g.key] ?? 0}
              </span>
            </button>
          ))}
        </div>
      </div>

      {applications === null ? (
        <div className="space-y-2.5">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-[68px]" />
          ))}
        </div>
      ) : applications.length === 0 ? (
        <EmptyState
          icon={ClipboardList}
          title="No applications yet"
          description="Analyse an opportunity or connect Gmail to start your pipeline."
          action={
            <Link href="/opportunities" className={buttonClasses("primary", "md")}>
              <Plus size={16} /> Add an opportunity
            </Link>
          }
        />
      ) : visible.length === 0 ? (
        <p className="py-12 text-center text-sm text-muted">Nothing in “{active.label}” right now.</p>
      ) : (
        <div className="stagger space-y-2.5">
          {visible.map((app) => (
            <ApplicationRow key={app.id} app={app} />
          ))}
        </div>
      )}
    </div>
  );
}
