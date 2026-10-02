"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowRight, Calendar, CheckCircle2, ExternalLink, Inbox, SkipForward } from "lucide-react";
import { useRequireAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";
import type { ApplicationOut, ReviewResponse, TailoredResumeOut } from "@/lib/types";
import { EligibilityCard } from "@/components/EligibilityCard";
import { ReviewApplyCard } from "@/components/ReviewApplyCard";
import { SkillGapCard } from "@/components/SkillGapCard";
import { StatusTimeline } from "@/components/StatusTimeline";
import { SectionLabel } from "@/components/ui";

export default function ApplicationDetailPage() {
  const { user, loading: authLoading } = useRequireAuth();
  const params = useParams<{ id: string }>();
  const [application, setApplication] = useState<ApplicationOut | null>(null);
  const [tailored, setTailored] = useState<TailoredResumeOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    api
      .getApplication(params.id)
      .then(setApplication)
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Failed to load application"));
    // 404 just means no tailored resume yet (no resume on file, not eligible, …).
    api.getTailoredResume(params.id).then(setTailored).catch(() => setTailored(null));
  }, [user, params.id]);

  const onReviewed = (response: ReviewResponse) => setApplication(response.application);

  if (authLoading || !user) return null;
  if (error) return <p className="text-sm font-medium text-rose-600">{error}</p>;
  if (!application) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-slate-200 border-t-indigo-500" />
      </div>
    );
  }

  const lastStage = application.status_history.at(-1)?.stage;
  const lastNote = application.status_history.at(-1)?.note;

  return (
    <div className="animate-fade-in space-y-10">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          {application.company_name} <span className="font-normal text-slate-400">—</span> {application.role}
        </h1>
        {application.source === "gmail_mcp" && (
          <span className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-indigo-50 px-2.5 py-0.5 text-xs font-medium text-indigo-700">
            <Inbox size={12} /> Found automatically in your Gmail job alerts
          </span>
        )}
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

      {lastStage === "READY_TO_APPLY" && tailored && (
        <section>
          <SectionLabel>Review &amp; Apply</SectionLabel>
          <ReviewApplyCard application={application} tailored={tailored} onReviewed={onReviewed} />
        </section>
      )}

      {lastStage === "APPLIED" && (
        <div className="flex items-center gap-2 rounded-2xl bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800">
          <CheckCircle2 size={16} /> {lastNote ?? "Applied."}
        </div>
      )}
      {lastStage === "MANUAL_APPLY_REQUIRED" && (
        <div className="flex flex-wrap items-center gap-2 rounded-2xl bg-amber-50 px-4 py-3 text-sm font-medium text-amber-800">
          {lastNote}
          {application.application_url && (
            <a
              href={application.application_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 font-semibold text-amber-900 underline"
            >
              Open posting <ExternalLink size={13} />
            </a>
          )}
        </div>
      )}
      {lastStage === "SKIPPED_BY_USER" && (
        <div className="flex items-center gap-2 rounded-2xl bg-slate-100 px-4 py-3 text-sm text-slate-600">
          <SkipForward size={16} /> You skipped this one — nothing was sent.
        </div>
      )}

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
