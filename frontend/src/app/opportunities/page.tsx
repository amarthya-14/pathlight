"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { ArrowRight, BadgeCheck, BookOpenCheck, Briefcase, Check, Inbox, Search, ScanSearch, Sparkles, Wand2 } from "lucide-react";
import { useRequireAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";
import type { ApplicationOut, IngestResponse } from "@/lib/types";
import { ApplicationRow } from "@/components/ApplicationRow";
import { EligibilityCard } from "@/components/EligibilityCard";
import { SkillGapCard } from "@/components/SkillGapCard";
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
  "Acme Labs is hiring a Backend Engineering Intern (Bengaluru, 6 months).\nRequired: Python, SQL, REST APIs. Preferred: Docker, AWS.\nEligibility: B.Tech CSE/IT, minimum CGPA 7.0.\nApply by 30 Oct — email your resume to careers@acmelabs.dev";

function AgentProgress({ step }: { step: number }) {
  return (
    <Card glow className="animate-scale-in p-5 sm:p-6">
      <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-fg">
        <span className="relative flex h-2.5 w-2.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-70" />
          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-accent" />
        </span>
        Pathlight agents at work…
      </div>
      <ol className="space-y-2">
        {AGENT_STEPS.map(({ icon: Icon, label }, i) => {
          const done = i < step;
          const active = i === step;
          return (
            <li
              key={label}
              className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-all duration-300 ${
                active ? "bg-accent-soft text-fg" : done ? "text-muted" : "text-subtle opacity-60"
              }`}
            >
              <span
                className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg transition-all ${
                  done ? "bg-ok text-white" : active ? "bg-brand-gradient text-white shadow-glow" : "bg-surface-2"
                }`}
              >
                {done ? <Check size={14} strokeWidth={2.8} /> : <Icon size={14} className={active ? "animate-pulse" : ""} />}
              </span>
              {label}
              {active && <span className="travel-line ml-auto h-1 w-16 rounded-full bg-surface-2" />}
            </li>
          );
        })}
      </ol>
    </Card>
  );
}

export default function OpportunitiesPage() {
  const { user, loading: authLoading } = useRequireAuth();
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

  useEffect(() => () => {
    if (timer.current) clearInterval(timer.current);
  }, []);

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
          eyebrow="Discover"
          title="Opportunities"
          subtitle="Paste any job description or placement email. Five agents extract the details, check your eligibility, compare skills, plan your prep and tailor your resume."
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.25fr_1fr]">
        <Card className="animate-fade-in p-5 sm:p-6" style={{ animationDelay: "0.05s" }}>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="flex items-center justify-between">
              <label htmlFor="jd" className="text-sm font-semibold text-fg">
                Job description or email
              </label>
              <button
                type="button"
                onClick={() => setRawText(SAMPLE)}
                className="text-xs font-medium text-accent-fg hover:underline"
                disabled={submitting}
              >
                Try a sample
              </button>
            </div>
            <TextArea
              id="jd"
              required
              rows={9}
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
              placeholder={"Paste the full posting here — role, company, requirements, eligibility, how to apply…"}
              disabled={submitting}
            />
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span className="text-xs text-subtle">{rawText.length > 0 ? `${rawText.length.toLocaleString()} characters` : "Takes ~20–40 seconds"}</span>
              <Button type="submit" size="lg" loading={submitting} disabled={!rawText.trim()}>
                {submitting ? "Analysing…" : "Analyse opportunity"}
                {!submitting && <Sparkles size={16} />}
              </Button>
            </div>
            {error && <Alert tone="bad">{error}</Alert>}
          </form>
        </Card>

        <div className="animate-fade-in" style={{ animationDelay: "0.1s" }}>
          {submitting ? (
            <AgentProgress step={step} />
          ) : result ? (
            <Card glow className="animate-scale-in p-5 sm:p-6">
              <div className="flex items-center gap-3">
                <CompanyAvatar name={result.company_name} />
                <div className="min-w-0">
                  <div className="text-xs font-medium text-ok">Added to your pipeline</div>
                  <div className="truncate font-semibold text-fg">{result.role}</div>
                  <div className="truncate text-sm text-muted">{result.company_name}</div>
                </div>
              </div>
              <Link href={`/applications/${result.application_id}`} className={buttonClasses("primary", "lg", "mt-5 w-full")}>
                Open application <ArrowRight size={16} />
              </Link>
            </Card>
          ) : (
            <Card className="flex h-full flex-col p-5 sm:p-6">
              <div className="text-sm font-semibold text-fg">What happens when you click Analyse</div>
              <ol className="mt-4 flex-1 space-y-2">
                {AGENT_STEPS.map(({ icon: Icon, label }, i) => (
                  <li key={label} className="flex items-center gap-3 text-sm text-muted">
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-surface-2 text-accent-fg">
                      <Icon size={14} />
                    </span>
                    <span className="text-subtle">{i + 1}.</span> {label}
                  </li>
                ))}
              </ol>
              <div className="mt-5 rounded-xl border border-line bg-surface-2 p-3.5 text-sm text-muted">
                Tired of pasting? Connect Gmail and LinkedIn/Naukri alerts arrive here already analysed.
                <Link href="/integrations" className="mt-2 flex items-center gap-1.5 font-semibold text-accent-fg hover:underline">
                  <Inbox size={15} /> Connect Gmail <ArrowRight size={14} />
                </Link>
              </div>
            </Card>
          )}
        </div>
      </div>

      {result && (
        <div className="grid animate-fade-in gap-4 lg:grid-cols-2">
          {result.eligibility && <EligibilityCard eligibility={result.eligibility} />}
          {result.skill_gap && <SkillGapCard skillGap={result.skill_gap} skillGapNote={result.skill_gap_note} />}
        </div>
      )}

      <section>
        <SectionLabel>All opportunities</SectionLabel>
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex gap-1 rounded-xl border border-line bg-surface-2 p-1">
            {(
              [
                ["all", `All${applications ? ` · ${applications.length}` : ""}`],
                ["gmail", `From Gmail · ${gmailCount}`],
                ["manual", "Added by you"],
              ] as const
            ).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setFilter(key)}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                  filter === key ? "bg-surface-solid text-fg shadow-card" : "text-muted hover:text-fg"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="relative sm:w-72">
            <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-subtle" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search company or role"
              className="h-10 w-full rounded-xl border border-line bg-surface-2 pl-10 pr-3 text-sm text-fg placeholder:text-subtle focus:border-accent focus:outline-none focus:ring-4 focus:ring-accent/15"
            />
          </div>
        </div>

        {applications === null ? (
          <div className="space-y-2.5">
            <Skeleton className="h-16" />
            <Skeleton className="h-16" />
            <Skeleton className="h-16" />
          </div>
        ) : applications.length === 0 ? (
          <EmptyState icon={Briefcase} title="Nothing here yet" description="Analyse your first opportunity above, or connect Gmail." />
        ) : filtered.length === 0 ? (
          <p className="py-10 text-center text-sm text-muted">No opportunities match that.</p>
        ) : (
          <div className="stagger space-y-2.5">
            {filtered.map((app) => (
              <ApplicationRow key={app.id} app={app} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
