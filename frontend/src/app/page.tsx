"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, Building2, Clock, Compass, Sparkles, TrendingDown, TrendingUp } from "lucide-react";
import { useRequireAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import type { ApplicationOut, DashboardHomeOut } from "@/lib/types";
import { EmptyState, PageHeader, SectionLabel, StatCard } from "@/components/ui";

function daysUntil(deadline: string): number {
  return Math.ceil((new Date(deadline).getTime() - Date.now()) / (1000 * 60 * 60 * 24));
}

function ApplicationRow({ app }: { app: ApplicationOut }) {
  const days = app.deadline ? daysUntil(app.deadline) : null;
  return (
    <Link
      href={`/applications/${app.id}`}
      className="card-shadow card-shadow-hover group flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3.5 transition-all hover:border-indigo-200"
    >
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-500 group-hover:bg-indigo-50 group-hover:text-indigo-600">
          <Building2 size={16} />
        </div>
        <div>
          <div className="text-sm font-semibold text-slate-800">{app.company_name}</div>
          <div className="text-xs text-slate-500">{app.role}</div>
        </div>
      </div>
      {days !== null && (
        <span
          className={`rounded-full px-2.5 py-1 text-xs font-medium ${
            days <= 3 ? "bg-rose-50 text-rose-600" : days <= 14 ? "bg-amber-50 text-amber-600" : "bg-slate-50 text-slate-500"
          }`}
        >
          {days >= 0 ? `${days}d left` : "past deadline"}
        </span>
      )}
    </Link>
  );
}

export default function HomePage() {
  const { user, loading: authLoading } = useRequireAuth();
  const [data, setData] = useState<DashboardHomeOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    api
      .getDashboardHome()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load dashboard"));
  }, [user]);

  if (authLoading || !user) return null;
  if (error) return <p className="text-sm font-medium text-rose-600">{error}</p>;
  if (!data) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-slate-200 border-t-indigo-500" />
      </div>
    );
  }

  const nothingYet = data.recent_applications.length === 0;

  return (
    <div className="animate-fade-in space-y-10">
      <PageHeader title={`Welcome back, ${user.email.split("@")[0]}`} subtitle="Here's where things stand." />

      {(!data.has_profile || !data.has_resume) && (
        <div className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4">
          <AlertTriangle size={18} className="mt-0.5 shrink-0 text-amber-500" />
          <div className="space-y-1 text-sm text-amber-800">
            {!data.has_profile && (
              <p>
                You haven&apos;t set up your{" "}
                <Link href="/profile" className="font-medium underline underline-offset-2">
                  profile
                </Link>{" "}
                yet — eligibility checks can&apos;t run without CGPA/branch.
              </p>
            )}
            {!data.has_resume && (
              <p>
                No resume on file — upload one from your{" "}
                <Link href="/profile" className="font-medium underline underline-offset-2">
                  profile page
                </Link>{" "}
                so Skill Gap results reflect real evidence, not guesses.
              </p>
            )}
          </div>
        </div>
      )}

      {nothingYet ? (
        <EmptyState
          icon={Compass}
          title="No opportunities yet"
          description="Paste a job description or placement email to get started — Pathlight runs eligibility and skill-gap analysis automatically."
          action={
            <Link
              href="/opportunities"
              className="inline-flex items-center gap-1.5 text-sm font-semibold text-indigo-600 hover:text-indigo-700"
            >
              Ingest your first one <Sparkles size={14} />
            </Link>
          }
        />
      ) : (
        <>
          <section>
            <SectionLabel>Urgent deadlines · next 14 days</SectionLabel>
            {data.urgent_deadlines.length === 0 ? (
              <p className="text-sm text-slate-400">Nothing urgent right now.</p>
            ) : (
              <div className="space-y-2">
                {data.urgent_deadlines.map((app) => (
                  <ApplicationRow key={app.id} app={app} />
                ))}
              </div>
            )}
          </section>

          <section>
            <SectionLabel>Skill gap summary</SectionLabel>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
              <StatCard icon={TrendingDown} value={data.total_missing_skills} label="Missing skills, across apps" tone="danger" />
              <StatCard icon={TrendingUp} value={data.total_weak_skills} label="Weak skills, across apps" tone="warning" />
              {data.most_common_missing_skills.length > 0 && (
                <div className="card-shadow col-span-2 rounded-2xl border border-slate-200 bg-white p-5 sm:col-span-1">
                  <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-lg bg-slate-100 text-slate-500">
                    <Clock size={18} strokeWidth={2.25} />
                  </div>
                  <div className="mb-2 text-xs text-slate-500">Most common gaps</div>
                  <div className="flex flex-wrap gap-1.5">
                    {data.most_common_missing_skills.map((s) => (
                      <span key={s} className="rounded-full bg-rose-50 px-2.5 py-0.5 text-xs font-medium text-rose-600">
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </section>

          <section>
            <SectionLabel>Recent opportunities</SectionLabel>
            <div className="space-y-2">
              {data.recent_applications.map((app) => (
                <ApplicationRow key={app.id} app={app} />
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
