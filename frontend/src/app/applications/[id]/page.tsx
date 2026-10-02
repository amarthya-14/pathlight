"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  BookOpenCheck,
  CalendarClock,
  Check,
  CheckCircle2,
  ExternalLink,
  Inbox,
  PenLine,
  SkipForward,
  Sparkles,
  Wand2,
} from "lucide-react";
import { useRequireAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";
import type { ApplicationOut, ReviewResponse, TailoredResumeOut } from "@/lib/types";
import { JOURNEY, STAGE_META, daysUntil, deadlineLabel, deadlineTone, journeyIndex } from "@/lib/stages";
import { EligibilityCard } from "@/components/EligibilityCard";
import { applySiteLabel, FinishApplyPanel, ReviewApplyCard } from "@/components/ReviewApplyCard";
import { SkillGapCard } from "@/components/SkillGapCard";
import { StatusTimeline } from "@/components/StatusTimeline";
import { Alert, Badge, Button, buttonClasses, Card, CompanyAvatar, PageSkeleton, SectionLabel } from "@/components/ui";

function JourneyStepper({ application }: { application: ApplicationOut }) {
  const reached = journeyIndex(application);
  const skipped = application.status_history.some((e) => e.stage === "SKIPPED_BY_USER");
  const applied = application.status_history.some((e) => e.stage === "APPLIED");
  const lastIndex = JOURNEY.length - 1;
  return (
    <ol className="flex items-center" aria-label="Application progress">
      {JOURNEY.map((step, i) => {
        const done = i <= reached;
        // Reaching the last step via "finish applying" isn't the same as having applied.
        const current = i === reached && !(i === lastIndex && applied);
        return (
          <li key={step.key} className="flex flex-1 items-center last:flex-none">
            <div className="flex flex-col items-center gap-1.5">
              <span
                className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold transition-all ${
                  done
                    ? current
                      ? "bg-brand-gradient text-white shadow-glow"
                      : "bg-ok text-white"
                    : "border border-line bg-surface-2 text-subtle"
                }`}
              >
                {done && !current ? <Check size={14} strokeWidth={3} /> : i + 1}
              </span>
              <span className={`hidden text-[11px] font-medium sm:block ${done ? "text-fg" : "text-subtle"}`}>
                {i === lastIndex ? (skipped ? "Skipped" : applied ? "Applied" : "Apply") : step.label}
              </span>
            </div>
            {i < JOURNEY.length - 1 && (
              <div className="mx-1.5 mb-0 h-[2px] flex-1 overflow-hidden rounded-full bg-line sm:mb-5">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-violet-500 transition-all duration-700"
                  style={{ width: i < reached ? "100%" : "0%" }}
                />
              </div>
            )}
          </li>
        );
      })}
    </ol>
  );
}

export default function ApplicationDetailPage() {
  const { user, loading: authLoading } = useRequireAuth();
  const params = useParams<{ id: string }>();
  const [application, setApplication] = useState<ApplicationOut | null>(null);
  const [tailored, setTailored] = useState<TailoredResumeOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tailoring, setTailoring] = useState(false);
  const [tailorError, setTailorError] = useState<string | null>(null);

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

  const onGenerateTailored = async () => {
    setTailoring(true);
    setTailorError(null);
    try {
      setTailored(await api.tailorApplication(params.id));
      setApplication(await api.getApplication(params.id));
    } catch (err) {
      setTailorError(err instanceof ApiError ? err.detail : "Could not generate a tailored resume");
    } finally {
      setTailoring(false);
    }
  };

  if (authLoading || !user) return null;
  if (error) return <Alert tone="bad">{error}</Alert>;
  if (!application) return <PageSkeleton />;

  const lastStage = application.status_history.at(-1)?.stage;
  const lastNote = application.status_history.at(-1)?.note;
  const stageMeta = lastStage ? STAGE_META[lastStage] : null;
  const decided = application.status_history.some((e) =>
    ["APPLIED", "MANUAL_APPLY_REQUIRED", "SKIPPED_BY_USER"].includes(e.stage)
  );
  const notEligible = application.eligibility?.decision === "not_eligible";
  const showGetReady = !decided && !notEligible && !(lastStage === "READY_TO_APPLY" && tailored);
  const days = application.deadline ? daysUntil(application.deadline) : null;

  return (
    <div className="space-y-8">
      <Link href="/applications" className="inline-flex items-center gap-1.5 text-sm text-muted transition-colors hover:text-fg">
        <ArrowLeft size={15} /> Applications
      </Link>

      {/* Hero */}
      <Card className="animate-fade-in relative overflow-hidden p-5 sm:p-7">
        <div className="absolute -right-24 -top-24 h-64 w-64 rounded-full bg-accent/15 blur-3xl" />
        <div className="relative flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex min-w-0 items-start gap-4">
            <CompanyAvatar name={application.company_name} size="lg" />
            <div className="min-w-0">
              <h1 className="text-2xl font-semibold leading-tight tracking-tight text-fg sm:text-[1.7rem]">{application.role}</h1>
              <div className="mt-1 text-muted">{application.company_name}</div>
              <div className="mt-3 flex flex-wrap gap-2">
                {stageMeta && (
                  <Badge tone={stageMeta.tone} dot>
                    {stageMeta.label}
                  </Badge>
                )}
                {days !== null && (
                  <Badge tone={deadlineTone(days)} icon={CalendarClock}>
                    {deadlineLabel(days)} · {new Date(application.deadline!).toLocaleDateString(undefined, { day: "numeric", month: "short" })}
                  </Badge>
                )}
                {application.source === "gmail_mcp" && (
                  <Badge tone="info" icon={Inbox}>
                    From your Gmail alerts
                  </Badge>
                )}
              </div>
            </div>
          </div>
          <div className="flex shrink-0 flex-wrap gap-2">
            {application.application_url && (
              <a href={application.application_url} target="_blank" rel="noopener noreferrer" className={buttonClasses("secondary", "md")}>
                <ExternalLink size={15} /> View on {applySiteLabel(application.application_url)}
              </a>
            )}
            <Link href={`/applications/${application.id}/preparation`} className={buttonClasses("secondary", "md")}>
              <BookOpenCheck size={15} /> Prep plan
            </Link>
          </div>
        </div>
        <div className="relative mt-7 border-t border-line pt-6">
          <JourneyStepper application={application} />
        </div>
      </Card>

      {/* Apply */}
      {showGetReady && (
        <section className="animate-fade-in">
          <SectionLabel>Apply</SectionLabel>
          <Card glow className="relative overflow-hidden p-5 sm:p-6">
            <div className="absolute -left-16 -bottom-20 h-48 w-48 rounded-full bg-cyan-500/15 blur-3xl" />
            <div className="relative flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-start gap-4">
                <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-brand-gradient text-white shadow-glow">
                  <Wand2 size={22} />
                </span>
                <div>
                  <div className="font-semibold text-fg">Get ready to apply</div>
                  <p className="mt-1 max-w-xl text-sm leading-relaxed text-muted">
                    Pathlight tailors your resume and writes a cover note for this role — rewording what&apos;s already on
                    your resume, never adding skills you don&apos;t have. You review everything first.
                  </p>
                </div>
              </div>
              <Button size="lg" onClick={onGenerateTailored} loading={tailoring} className="shrink-0">
                {!tailoring && <Sparkles size={16} />}
                {tailoring ? "Tailoring… ~30s" : "Generate tailored resume"}
              </Button>
            </div>
            {tailorError && (
              <Alert
                tone="bad"
                className="relative mt-4"
                action={
                  tailorError.toLowerCase().includes("resume") ? (
                    <Link href="/profile" className={buttonClasses("secondary", "sm")}>
                      <PenLine size={13} /> Upload resume
                    </Link>
                  ) : undefined
                }
              >
                {tailorError}
              </Alert>
            )}
          </Card>
        </section>
      )}

      {lastStage === "READY_TO_APPLY" && tailored && (
        <section className="animate-fade-in">
          <SectionLabel>Review &amp; apply</SectionLabel>
          <ReviewApplyCard application={application} tailored={tailored} onReviewed={onReviewed} />
        </section>
      )}

      {lastStage === "MANUAL_APPLY_REQUIRED" && (
        <section className="animate-fade-in">
          <SectionLabel>Apply</SectionLabel>
          <FinishApplyPanel application={application} tailored={tailored} onMarked={setApplication} />
        </section>
      )}

      {lastStage === "APPLIED" && (
        <Card className="animate-scale-in flex items-center gap-4 border-ok/25 bg-ok-soft p-5">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-ok text-white shadow-[0_8px_24px_-8px_rgb(16_185_129/0.7)]">
            <CheckCircle2 size={22} />
          </span>
          <div>
            <div className="font-semibold text-ok">Applied</div>
            <div className="text-sm text-muted">{lastNote ?? "Your application is in."} Good luck! 🍀</div>
          </div>
        </Card>
      )}

      {lastStage === "SKIPPED_BY_USER" && (
        <Card className="flex items-center gap-3 p-5 text-sm text-muted">
          <SkipForward size={18} /> You skipped this one — nothing was sent.
        </Card>
      )}

      {/* Analysis */}
      {(application.eligibility || application.skill_gap) && (
        <section>
          <SectionLabel>Analysis</SectionLabel>
          <div className="stagger grid gap-4 lg:grid-cols-2">
            {application.eligibility && <EligibilityCard eligibility={application.eligibility} />}
            {application.skill_gap && <SkillGapCard skillGap={application.skill_gap} skillGapNote={application.skill_gap_note} />}
          </div>
        </section>
      )}

      <section>
        <SectionLabel>Activity</SectionLabel>
        <Card className="p-5 sm:p-6">
          <StatusTimeline history={application.status_history} />
        </Card>
      </section>
    </div>
  );
}
