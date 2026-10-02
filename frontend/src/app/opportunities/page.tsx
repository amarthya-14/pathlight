"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { ArrowRight, BadgeCheck, BookOpenCheck, Briefcase, Check, Inbox, Loader2, Search, ScanSearch, Sparkles, Wand2 } from "lucide-react";
import { useRequireAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";
import type { ApplicationOut, IngestResponse } from "@/lib/types";
import { ApplicationRow, RowList } from "@/components/ApplicationRow";
import { EligibilityCard } from "@/components/EligibilityCard";
import { SkillGapCard } from "@/components/SkillGapCard";
import { useToast } from "@/components/Toast";
import { Alert, Button, buttonClasses, Card, CompanyAvatar, EmptyState, PageHeader, SectionLabel, Skeleton, TextArea } from "@/components/ui";

// The agents run server-side in one request; this is an honest *indication* of the
// sequence (it advances on a timer and holds on the last step until the response lands).
const AGENT_STEPS = [
  { icon: Sparkles, label: "Reading the posting" },
  { icon: BadgeCheck, label: "Checking eligibility" },
  { icon: ScanSearch, label: "Comparing skills to your resume" },
  { icon: BookOpenCheck, label: "Building a prep plan" },
  { icon: Wand2, label: "Tailoring your resume" },
];

const SAMPLE =
  "Acme Labs is hiring a Backend Engineering Intern (Bengaluru, 6 months).\nRequired: Python, SQL, REST APIs. Preferred: Docker, AWS.\nEligibility: B.Tech CSE/IT, minimum CGPA 7.0. Freshers welcome.\nApply by 30 Oct — email your resume to careers@acmelabs.dev";

function AgentSteps({ step, running }: { step: number; running: boolean }) {
  return (
    <ol className="space-y-1">
      {AGENT_STEPS.map(({ icon: Icon, label }, i) => {
        const done = running && i < step;
        const active = running && i === step;
        return (
          <li
            key={label}
            className={`flex items-center gap-3 rounded-lg px-2.5 py-2 text-[13px] transition-colors ${
              active ? "bg-surface-hover text-fg" : done ? "text-muted" : "text-subtle"
            }`}
          >
            <span className="flex h-6 w-6 shrink-0 items-center justify-center">
              {done ? (
                <Check size={15} className="text-ok" strokeWidth={2.6} />
              ) : active ? (
                <Loader2 size={15} className="animate-spin text-fg" />
              ) : (
                <Icon size={15} strokeWidth={1.8} />
              )}
            </span>
            {label}
          </li>
        );
      })}
    </ol>
  );
}

export default function OpportunitiesPage() {
  const { user, loading: authLoading } = useRequireAuth();
  const toast = useToast();
  const [applications, setApplications] = useState<ApplicationOut[] | null>(null);
  const [rawText, setRawText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<IngestResponse | null>(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<"all" | "gmail" | "manual">("all");
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadApplications = () => {
    api.listApplications().then(setApplications).catch(() => setApplications([]));
  };

  useEffect(() => {
    if (user) loadApplications();
  }, [user]);

  useEffect(
    () => () => {
      if (timer.current) clearInterval(timer.current);
    },
    []
  );

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setResult(null);
    setSubmitting(true);
    setStep(0);
    timer.current = setInterval(() => setStep((s) => Math.min(s + 1, AGENT_STEPS.length - 1)), 2200);
    try {
      const res = await api.ingestOpportunity({ raw_text: rawText, source: "manual" });
      setResult(res);
      setRawText("");
      loadApplications();
      toast("Opportunity analysed", { description: `${res.role} at ${res.company_name}` });
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Ingestion failed");
    } finally {
      if (timer.current) clearInterval(timer.current);
      setSubmitting(false);
    }
  };

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (applications ?? []).filter((a) => {
      if (filter === "gmail" && a.source !== "gmail_mcp") return false;
      if (filter === "manual" && a.source === "gmail_mcp") return false;
      return !q || a.company_name.toLowerCase().includes(q) || a.role.toLowerCase().includes(q);
    });
  }, [applications, query, filter]);

  if (authLoading || !user) return null;

  const gmailCount = (applications ?? []).filter((a) => a.source === "gmail_mcp").length;

  return (
    <div className="space-y-10">
      <div className="animate-fade-in">
        <PageHeader
          title="Opportunities"
          subtitle="Paste any job description or placement email. Pathlight extracts the details, checks your eligibility, compares skills, plans your prep and tailors your resume."
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
        <Card className="p-4 sm:p-5">
          <form onSubmit={onSubmit} className="space-y-3">
            <div className="flex items-center justify-between">
              <label htmlFor="jd" className="text-[13px] font-medium text-fg">
                Job description or email
              </label>
              <button type="button" onClick={() => setRawText(SAMPLE)} className="text-[13px] text-muted hover:text-fg" disabled={submitting}>
                Try a sample
              </button>
            </div>
            <TextArea
              id="jd"
              required
              rows={9}
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
              placeholder="Paste the full posting — role, company, requirements, eligibility, how to apply…"
              disabled={submitting}
            />
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span className="text-xs text-subtle">
                {rawText.length > 0 ? `${rawText.length.toLocaleString()} characters` : "Usually takes 20–40 seconds"}
              </span>
              <Button type="submit" loading={submitting} disabled={!rawText.trim()}>
                {submitting ? "Analysing…" : "Analyse opportunity"}
              </Button>
            </div>
            {error && <Alert tone="bad">{error}</Alert>}
          </form>
        </Card>

        {result && !submitting ? (
          <Card className="animate-scale-in flex flex-col p-5">
            <div className="text-[13px] font-medium text-ok">Added to your pipeline</div>
            <div className="mt-3 flex items-center gap-3">
              <CompanyAvatar name={result.company_name} />
              <div className="min-w-0">
                <div className="truncate text-[15px] font-semibold text-fg">{result.role}</div>
                <div className="truncate text-[13px] text-muted">{result.company_name}</div>
              </div>
            </div>
            <div className="mt-auto pt-5">
              <Link href={`/applications/${result.application_id}`} className={buttonClasses("primary", "md", "w-full")}>
                Open application <ArrowRight size={14} />
              </Link>
            </div>
          </Card>
        ) : (
          <Card className="flex flex-col p-4 sm:p-5">
            <div className="text-[13px] font-medium text-fg">{submitting ? "Working on it…" : "What happens next"}</div>
            <div className="mt-3 flex-1">
              <AgentSteps step={step} running={submitting} />
            </div>
            {!submitting && (
              <Link
                href="/integrations"
                className="mt-4 flex items-center gap-2 rounded-lg border border-line px-3 py-2.5 text-[13px] text-muted transition-colors hover:bg-surface-hover hover:text-fg"
              >
                <Inbox size={14} /> Tired of pasting? Connect Gmail
                <ArrowRight size={13} className="ml-auto" />
              </Link>
            )}
          </Card>
        )}
      </div>

      {result && (
        <div className="animate-fade-in grid gap-4 lg:grid-cols-2">
          {result.eligibility && <EligibilityCard eligibility={result.eligibility} />}
          {result.skill_gap && <SkillGapCard skillGap={result.skill_gap} skillGapNote={result.skill_gap_note} />}
        </div>
      )}

      <section>
        <SectionLabel>All opportunities</SectionLabel>
        <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="inline-flex w-fit rounded-lg border border-line bg-surface-2 p-0.5">
            {(
              [
                ["all", "All", applications?.length ?? 0],
                ["gmail", "From Gmail", gmailCount],
                ["manual", "Added by you", (applications?.length ?? 0) - gmailCount],
              ] as const
            ).map(([key, label, count]) => (
              <button
                key={key}
                onClick={() => setFilter(key)}
                className={`flex h-7 items-center gap-1.5 rounded-md px-2.5 text-[13px] font-medium transition-all ${
                  filter === key ? "bg-surface text-fg shadow-xs ring-1 ring-line" : "text-muted hover:text-fg"
                }`}
              >
                {label} <span className="text-xs tabular-nums text-subtle">{count}</span>
              </button>
            ))}
          </div>
          <div className="relative sm:w-64">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-subtle" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Filter by company or role"
              className="h-8 w-full rounded-lg border border-line-strong bg-surface pl-8 pr-3 text-[13px] text-fg shadow-xs placeholder:text-subtle focus:border-accent focus:outline-none focus:ring-[3px] focus:ring-accent/15"
            />
          </div>
        </div>

        {applications === null ? (
          <Skeleton className="h-48" />
        ) : applications.length === 0 ? (
          <EmptyState icon={Briefcase} title="Nothing here yet" description="Analyse your first opportunity above, or connect Gmail." />
        ) : filtered.length === 0 ? (
          <p className="py-10 text-center text-sm text-muted">No opportunities match that.</p>
        ) : (
          <RowList>
            {filtered.map((app) => (
              <ApplicationRow key={app.id} app={app} />
            ))}
          </RowList>
        )}
      </section>
    </div>
  );
}
