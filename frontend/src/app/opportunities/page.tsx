"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Briefcase, Sparkles } from "lucide-react";
import { useRequireAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";
import type { ApplicationOut, IngestResponse } from "@/lib/types";
import { EligibilityCard } from "@/components/EligibilityCard";
import { SkillGapCard } from "@/components/SkillGapCard";
import { Button, EmptyState, PageHeader, SectionLabel, TextArea } from "@/components/ui";

export default function OpportunitiesPage() {
  const { user, loading: authLoading } = useRequireAuth();
  const [applications, setApplications] = useState<ApplicationOut[]>([]);
  const [rawText, setRawText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<IngestResponse | null>(null);

  const loadApplications = () => {
    api.listApplications().then(setApplications).catch(() => {});
  };

  useEffect(() => {
    if (user) loadApplications();
  }, [user]);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setResult(null);
    setSubmitting(true);
    try {
      const res = await api.ingestOpportunity({ raw_text: rawText, source: "manual" });
      setResult(res);
      setRawText("");
      loadApplications();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Ingestion failed");
    } finally {
      setSubmitting(false);
    }
  };

  if (authLoading || !user) return null;

  return (
    <div className="animate-fade-in space-y-10">
      <PageHeader
        title="Opportunities"
        subtitle="Paste a job description or placement email — Discovery, Eligibility, Skill Gap, and Planner all run automatically."
      />

      <form onSubmit={onSubmit} className="card-shadow space-y-4 rounded-2xl border border-slate-200 bg-white p-5">
        <TextArea
          required
          rows={5}
          value={rawText}
          onChange={(e) => setRawText(e.target.value)}
          placeholder="Acme Corp is hiring a Backend Intern. Required: Python, AWS. Minimum CGPA 7.0…"
        />
        <Button type="submit" disabled={submitting}>
          {submitting ? "Ingesting…" : "Ingest opportunity"}
          {!submitting && <Sparkles size={16} />}
        </Button>
        {error && <p className="text-sm font-medium text-rose-600">{error}</p>}
      </form>

      {result && (
        <div className="animate-fade-in space-y-4 rounded-2xl border border-indigo-100 bg-gradient-to-b from-indigo-50/60 to-white p-5">
          <h2 className="text-base font-semibold text-slate-900">
            {result.company_name} <span className="font-normal text-slate-400">—</span> {result.role}
          </h2>
          {result.eligibility && <EligibilityCard eligibility={result.eligibility} />}
          {result.skill_gap && <SkillGapCard skillGap={result.skill_gap} skillGapNote={result.skill_gap_note} />}
          <Link
            href={`/applications/${result.application_id}`}
            className="inline-flex items-center gap-1.5 text-sm font-semibold text-indigo-600 hover:text-indigo-700"
          >
            View full application <ArrowRight size={14} />
          </Link>
        </div>
      )}

      <section>
        <SectionLabel>All opportunities</SectionLabel>
        {applications.length === 0 ? (
          <EmptyState icon={Briefcase} title="Nothing ingested yet" />
        ) : (
          <div className="space-y-2">
            {applications.map((app) => (
              <Link
                key={app.id}
                href={`/applications/${app.id}`}
                className="card-shadow card-shadow-hover flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3.5 transition-all hover:border-indigo-200"
              >
                <div>
                  <span className="text-sm font-semibold text-slate-800">{app.company_name}</span>{" "}
                  <span className="text-sm text-slate-400">— {app.role}</span>
                </div>
                {app.eligibility && (
                  <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">
                    {app.eligibility.decision.replace("_", " ")}
                  </span>
                )}
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
