"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowRight, Calendar } from "lucide-react";
import { useRequireAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";
import type { ApplicationOut } from "@/lib/types";
import { EligibilityCard } from "@/components/EligibilityCard";
import { SkillGapCard } from "@/components/SkillGapCard";
import { StatusTimeline } from "@/components/StatusTimeline";
import { SectionLabel } from "@/components/ui";

export default function ApplicationDetailPage() {
  const { user, loading: authLoading } = useRequireAuth();
  const params = useParams<{ id: string }>();
  const [application, setApplication] = useState<ApplicationOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    api
      .getApplication(params.id)
      .then(setApplication)
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Failed to load application"));
  }, [user, params.id]);

  if (authLoading || !user) return null;
  if (error) return <p className="text-sm font-medium text-rose-600">{error}</p>;
  if (!application) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-slate-200 border-t-indigo-500" />
      </div>
    );
  }

  return (
    <div className="animate-fade-in space-y-10">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          {application.company_name} <span className="font-normal text-slate-400">—</span> {application.role}
        </h1>
        {application.deadline && (
          <p className="mt-1.5 flex items-center gap-1.5 text-sm text-slate-500">
            <Calendar size={14} /> Deadline: {new Date(application.deadline).toLocaleString()}
          </p>
        )}
        <Link
          href={`/applications/${application.id}/preparation`}
          className="mt-3 inline-flex items-center gap-1.5 text-sm font-semibold text-indigo-600 hover:text-indigo-700"
        >
          View preparation plan <ArrowRight size={14} />
        </Link>
      </div>

      {application.eligibility && (
        <section>
          <SectionLabel>Eligibility</SectionLabel>
          <EligibilityCard eligibility={application.eligibility} />
        </section>
      )}

      {application.skill_gap && (
        <section>
          <SectionLabel>Skill Gap</SectionLabel>
          <SkillGapCard skillGap={application.skill_gap} skillGapNote={application.skill_gap_note} />
        </section>
      )}

      <section>
        <SectionLabel>Status timeline</SectionLabel>
        <div className="card-shadow rounded-2xl border border-slate-200 bg-white p-5">
          <StatusTimeline history={application.status_history} />
        </div>
      </section>
    </div>
  );
}
