"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ClipboardList } from "lucide-react";
import { useRequireAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import type { ApplicationOut } from "@/lib/types";
import { EmptyState, PageHeader } from "@/components/ui";

const STAGE_STYLE: Record<string, string> = {
  DISCOVERED: "bg-slate-100 text-slate-600",
  ELIGIBILITY_CHECKED: "bg-slate-100 text-slate-600",
  PREPARING: "bg-indigo-50 text-indigo-600",
  READY_TO_APPLY: "bg-violet-50 text-violet-600",
  APPLIED: "bg-blue-50 text-blue-600",
  OA: "bg-amber-50 text-amber-600",
  INTERVIEW: "bg-amber-50 text-amber-600",
  OFFER: "bg-emerald-50 text-emerald-600",
  REJECTED: "bg-rose-50 text-rose-600",
};

function currentStage(app: ApplicationOut): string {
  if (app.status_history.length === 0) return "—";
  return app.status_history[app.status_history.length - 1].stage;
}

export default function ApplicationsPage() {
  const { user, loading: authLoading } = useRequireAuth();
  const [applications, setApplications] = useState<ApplicationOut[] | null>(null);

  useEffect(() => {
    if (user) api.listApplications().then(setApplications).catch(() => setApplications([]));
  }, [user]);

  if (authLoading || !user) return null;

  return (
    <div className="animate-fade-in space-y-6">
      <PageHeader title="Applications" subtitle="Every opportunity you've ingested, with its current stage." />

      {applications === null ? (
        <div className="flex h-40 items-center justify-center">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-slate-200 border-t-indigo-500" />
        </div>
      ) : applications.length === 0 ? (
        <EmptyState icon={ClipboardList} title="No applications yet" description="Ingest an opportunity to start one." />
      ) : (
        <div className="card-shadow overflow-hidden rounded-2xl border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/60 text-xs uppercase tracking-wide text-slate-400">
                <th className="px-5 py-3 font-medium">Company</th>
                <th className="px-5 py-3 font-medium">Role</th>
                <th className="px-5 py-3 font-medium">Stage</th>
                <th className="px-5 py-3 font-medium">Deadline</th>
              </tr>
            </thead>
            <tbody>
              {applications.map((app) => {
                const stage = currentStage(app);
                return (
                  <tr key={app.id} className="border-b border-slate-50 last:border-0 hover:bg-slate-50/60">
                    <td className="px-5 py-3.5">
                      <Link href={`/applications/${app.id}`} className="font-medium text-indigo-600 hover:text-indigo-700">
                        {app.company_name}
                      </Link>
                    </td>
                    <td className="px-5 py-3.5 text-slate-600">{app.role}</td>
                    <td className="px-5 py-3.5">
                      <span
                        className={`rounded-full px-2.5 py-1 text-xs font-medium ${STAGE_STYLE[stage] ?? "bg-slate-100 text-slate-600"}`}
                      >
                        {stage.replace(/_/g, " ")}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-slate-500">
                      {app.deadline ? new Date(app.deadline).toLocaleDateString() : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
