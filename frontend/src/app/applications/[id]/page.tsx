"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  BookOpenCheck,
  CalendarClock,
  Check,
  ChevronRight,
  ExternalLink,
  FileSearch,
  Inbox,
  Mail,
  PartyPopper,
  PenLine,
  RefreshCw,
  SkipForward,
  Wand2,
} from "lucide-react";
import { useRequireAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";
import type { ApplicationOut, PostApplyStage, ReviewResponse, TailoredResumeOut } from "@/lib/types";
import { JOURNEY, STAGE_META, daysUntil, deadlineLabel, deadlineTone, journeyIndex, isAlertSource } from "@/lib/stages";
import { EligibilityCard } from "@/components/EligibilityCard";
import { applySiteLabel, FinishApplyPanel, ReviewApplyCard } from "@/components/ReviewApplyCard";
import { ApplicationKitPanel } from "@/components/ApplicationKit";
import { SkillGapCard } from "@/components/SkillGapCard";
import { StatusTimeline } from "@/components/StatusTimeline";
import { useToast } from "@/components/Toast";
import { Alert, Badge, Button, buttonClasses, Card, CompanyAvatar, PageSkeleton, SectionLabel, TextArea } from "@/components/ui";

function JourneyStepper({ application }: { application: ApplicationOut }) {
  const reached = journeyIndex(application);
  const skipped = application.status_history.some((e) => e.stage === "SKIPPED_BY_USER");
  const applied = application.status_history.some((e) => e.stage === "APPLIED");
  const lastIndex = JOURNEY.length - 1;
  return (
    <ol className="grid grid-cols-5 gap-2" aria-label="Application progress">
      {JOURNEY.map((step, i) => {
        const done = i < reached || (i === lastIndex && applied);
        const current = i === reached && !done;
        const label = i === lastIndex ? (skipped ? "Skipped" : applied ? "Applied" : "Apply") : step.label;
        return (
          <li key={step.key} className="min-w-0">
            <div className={`h-1 rounded-full ${done ? "bg-ok" : current ? "bg-fg" : "bg-line-strong"}`} />
            <div
              className={`mt-2 items-center gap-1 truncate text-xs ${current ? "flex" : "hidden sm:flex"} ${
                done || current ? "font-medium text-fg" : "text-subtle"
              }`}
            >
              {done && <Check size={12} className="shrink-0 text-ok" strokeWidth={3} />}
              {label}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

const POST_APPLY: { stage: PostApplyStage; label: string }[] = [
  { stage: "OA", label: "Online assessment" },
  { stage: "INTERVIEW", label: "Interview" },
  { stage: "OFFER", label: "Offer" },
  { stage: "REJECTED", label: "Rejected" },
];

function TrackProgress({ application, onUpdated }: { application: ApplicationOut; onUpdated: (a: ApplicationOut) => void }) {
  const toast = useToast();
  const [stage, setStage] = useState<PostApplyStage | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const save = async () => {
    if (!stage) return;
    setBusy(true);
    try {
      onUpdated(await api.updateApplicationStatus(application.id, stage, note));
      toast(stage === "OFFER" ? "Congratulations on the offer! 🎉" : "Progress recorded", { description: STAGE_META[stage].label });
      setStage(null);
      setNote("");
    } catch (err) {
      toast("Couldn't update", { description: err instanceof ApiError ? err.detail : undefined, tone: "bad" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="p-4">
      <div className="text-[13px] font-medium text-fg">What happened next?</div>
      <p className="mt-0.5 text-xs text-muted">Keep your pipeline honest after applying.</p>
      <div className="mt-3 grid grid-cols-2 gap-1.5">
        {POST_APPLY.map((p) => (
          <button
            key={p.stage}
            onClick={() => setStage(stage === p.stage ? null : p.stage)}
            className={`h-8 rounded-lg border text-xs font-medium transition-colors ${
              stage === p.stage ? "border-fg bg-ink text-ink-fg" : "border-line-strong bg-surface text-muted hover:bg-surface-hover hover:text-fg"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>
      {stage && (
        <div className="animate-fade-in mt-3 space-y-2">
          <TextArea rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Optional note — e.g. Round 1 on Monday" />
          <Button size="sm" onClick={save} loading={busy} className="w-full">
            Save
          </Button>
        </div>
      )}
    </Card>
  );
}

function RecheckCard({
  application,
  onUpdated,
  onRetailored,
  highlight,
  textareaRef,
}: {
  application: ApplicationOut;
  onUpdated: (a: ApplicationOut) => void;
  onRetailored: (t: TailoredResumeOut) => void;
  highlight: boolean;
  textareaRef: React.RefObject<HTMLTextAreaElement | null>;
}) {
  const toast = useToast();
  const [jd, setJd] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      const withJd = Boolean(jd.trim());
      const updated = await api.recheckApplication(application.id, jd.trim() || undefined);
      onUpdated(updated);
      setJd("");
      const decision = updated.eligibility?.decision?.replace("_", " ") ?? "updated";
      toast("Eligibility re-checked", { description: `Result: ${decision}` });
      // A real JD makes the tailored resume much better (ATS matches its wording), so
      // re-tailor in the background when the user is still deciding.
      const stage = updated.status_history[updated.status_history.length - 1]?.stage;
      if (withJd && stage === "READY_TO_APPLY" && updated.eligibility?.decision !== "not_eligible") {
        toast("Re-tailoring with the full description", { description: "Your resume will update here in a minute or two.", tone: "info" });
        api
          .tailorApplication(application.id)
          .then((t) => {
            onRetailored(t);
            toast("Tailored resume updated", { description: t.ats ? `ATS score ${t.ats.score}/100` : undefined });
          })
          .catch(() => {});
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Re-check failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className={`p-4 transition-shadow ${highlight ? "ring-2 ring-accent/30" : ""}`}>
      <div className="flex items-center gap-2 text-[13px] font-medium text-fg">
        <FileSearch size={14} /> Check against the full posting
      </div>
      <p className="mt-1 text-xs leading-relaxed text-muted">
        Job alerts only include the title and company. Paste the full description from the job page to check experience,
        CGPA and branch properly.
      </p>
      <TextArea
        ref={textareaRef}
        rows={4}
        className="mt-3 text-[13px]"
        value={jd}
        onChange={(e) => setJd(e.target.value)}
        placeholder="Paste the full job description…"
      />
      {error && <p className="mt-2 text-xs font-medium text-bad">{error}</p>}
      <Button variant={jd.trim() ? "primary" : "secondary"} size="sm" onClick={run} loading={busy} className="mt-2 w-full">
        {!busy && <RefreshCw size={12} />} {busy ? "Re-checking…" : jd.trim() ? "Re-check with this description" : "Re-check with my current profile"}
      </Button>
    </Card>
  );
}

export default function ApplicationDetailPage() {
  const { user, profile, loading: authLoading } = useRequireAuth();
  const toast = useToast();
  const params = useParams<{ id: string }>();
  const [application, setApplication] = useState<ApplicationOut | null>(null);
  const [tailored, setTailored] = useState<TailoredResumeOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tailoring, setTailoring] = useState(false);
  const [tailorError, setTailorError] = useState<string | null>(null);
  const [highlightRecheck, setHighlightRecheck] = useState(false);
  const recheckRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (!user) return;
    api
      .getApplication(params.id)
      .then(setApplication)
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Failed to load application"));
    // 404 just means no tailored resume yet (no resume on file, not eligible, …).
    api.getTailoredResume(params.id).then(setTailored).catch(() => setTailored(null));
  }, [user, params.id]);

  // Jobs added in the last few minutes are tailored in the background (the ATS loop takes
  // 1-3 min). Show that instead of a "Generate" button that would run it a second time,
  // and pick the result up when it lands.
  const backgroundTailoring =
    !!application &&
    !tailored &&
    Date.now() - new Date(application.created_at).getTime() < 5 * 60_000 &&
    application.eligibility?.decision !== "not_eligible" &&
    !application.status_history.some((e) => ["APPLIED", "SKIPPED_BY_USER", "MANUAL_APPLY_REQUIRED"].includes(e.stage));
  useEffect(() => {
    if (!backgroundTailoring) return;
    const t = setInterval(async () => {
      try {
        const ready = await api.getTailoredResume(params.id);
        setTailored(ready);
        setApplication(await api.getApplication(params.id));
        toast("Tailored resume ready", { description: ready.ats ? `ATS score ${ready.ats.score}/100` : undefined });
      } catch {
        // not ready yet
      }
    }, 8000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [backgroundTailoring, params.id]);

  const onReviewed = (response: ReviewResponse) => {
    setApplication(response.application);
    if (response.outcome === "applied") toast("Application sent", { description: response.detail });
    else if (response.outcome === "skipped") toast("Skipped", { description: "Nothing was sent.", tone: "info" });
    else toast("Ready to finish on the posting site", { description: "Your PDF is downloading and the cover note is copied.", tone: "info" });
  };

  const onGenerateTailored = async () => {
    setTailoring(true);
    setTailorError(null);
    try {
      setTailored(await api.tailorApplication(params.id));
      setApplication(await api.getApplication(params.id));
      toast("Tailored resume ready", { description: "Review it below before anything is sent." });
    } catch (err) {
      setTailorError(err instanceof ApiError ? err.detail : "Could not generate a tailored resume");
    } finally {
      setTailoring(false);
    }
  };

  const focusRecheck = () => {
    recheckRef.current?.focus();
    recheckRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    setHighlightRecheck(true);
    setTimeout(() => setHighlightRecheck(false), 1800);
  };

  if (authLoading || !user) return null;
  if (error) return <Alert tone="bad">{error}</Alert>;
  if (!application) return <PageSkeleton />;

  const lastStage = application.status_history.at(-1)?.stage;
  const lastNote = application.status_history.at(-1)?.note;
  const stageMeta = lastStage ? STAGE_META[lastStage] : null;
  const needsMoreExperience =
    application.min_experience_years !== null &&
    application.min_experience_years > (profile?.experience_years ?? 0) + 1;
  const decided = application.status_history.some((e) => ["APPLIED", "MANUAL_APPLY_REQUIRED", "SKIPPED_BY_USER"].includes(e.stage));
  const applied = application.status_history.some((e) => e.stage === "APPLIED");
  const notEligible = application.eligibility?.decision === "not_eligible";
  const uncertain = application.eligibility?.decision === "uncertain";
  const showGetReady = !decided && !notEligible && !(lastStage === "READY_TO_APPLY" && tailored);
  const days = application.deadline ? daysUntil(application.deadline) : null;
  const site = applySiteLabel(application.application_url);

  return (
    <div className="space-y-6">
      <nav className="flex items-center gap-1.5 text-[13px] text-subtle">
        <Link href="/applications" className="hover:text-fg">
          Applications
        </Link>
        <ChevronRight size={13} />
        <span className="truncate text-muted">{application.company_name}</span>
      </nav>

      <div className="animate-fade-in">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex min-w-0 items-start gap-4">
            <CompanyAvatar name={application.company_name} size="lg" />
            <div className="min-w-0">
              <h1 className="text-[1.6rem] font-semibold leading-tight tracking-[-0.025em] text-fg">{application.role}</h1>
              <div className="mt-1 text-[15px] text-muted">{application.company_name}</div>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {stageMeta && (
                  <Badge tone={stageMeta.tone} dot>
                    {stageMeta.label}
                  </Badge>
                )}
                {days !== null && (
                  <Badge tone={deadlineTone(days)} icon={CalendarClock}>
                    {deadlineLabel(days)}
                  </Badge>
                )}
                {isAlertSource(application.source) && (
                  <Badge icon={Inbox}>From your job alerts</Badge>
                )}
              </div>
            </div>
          </div>
          <div className="flex shrink-0 flex-wrap gap-2">
            {application.application_url && (
              <a href={application.application_url} target="_blank" rel="noopener noreferrer" className={buttonClasses("secondary", "md")}>
                <ExternalLink size={14} /> View on {site}
              </a>
            )}
            <Link href={`/applications/${application.id}/preparation`} className={buttonClasses("secondary", "md")}>
              <BookOpenCheck size={14} /> Prep plan
            </Link>
          </div>
        </div>
        <div className="mt-7">
          <JourneyStepper application={application} />
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
        <div className="min-w-0 space-y-6">
          {showGetReady && (
            <section className="animate-fade-in">
              <Card className="p-5">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-start gap-3.5">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-line bg-surface-2">
                      <Wand2 size={16} className="text-fg" />
                    </span>
                    <div>
                      <div className="text-[15px] font-semibold text-fg">Get ready to apply</div>
                      <p className="mt-1 max-w-lg text-[13px] leading-relaxed text-muted">
                        Pathlight tailors your resume and writes a cover note for this role — rewording what&apos;s already on
                        your resume, never adding skills you don&apos;t have. You review everything first.
                      </p>
                    </div>
                  </div>
                  <Button onClick={onGenerateTailored} loading={tailoring || backgroundTailoring} className="shrink-0">
                    {backgroundTailoring ? "Tailoring in the background…" : tailoring ? "Tailoring… 1–2 min" : "Generate tailored resume"}
                  </Button>
                </div>
                {uncertain && (
                  <Alert tone="warn" className="mt-4">
                    Eligibility is uncertain for this role.{" "}
                    <button onClick={focusRecheck} className="font-semibold underline underline-offset-2">
                      Check it against the full posting
                    </button>{" "}
                    before applying.
                  </Alert>
                )}
                {tailorError && (
                  <Alert
                    tone="bad"
                    className="mt-4"
                    action={
                      tailorError.toLowerCase().includes("resume") ? (
                        <Link href="/profile" className={buttonClasses("secondary", "sm")}>
                          <PenLine size={12} /> Upload resume
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

          {notEligible && !decided && (
            <Alert tone="bad" title="You're not eligible for this role">
              {application.eligibility?.reason} If that&apos;s wrong, update your Profile or re-check with the full posting.
            </Alert>
          )}

          {!decided && needsMoreExperience && (
            <Alert tone="bad" title={`This role asks for ${application.min_experience_years}+ years of experience`}>
              You have {profile?.experience_years ? `${profile.experience_years} years` : "no full-time experience yet"}.
              On LinkedIn this is usually a screening question that filters you out automatically — your time is better
              spent on entry-level roles. If you still apply, answer the experience questions honestly (see the kit below).
            </Alert>
          )}

          {!decided && !application.has_job_description && isAlertSource(application.source) && (
            <Alert
              tone="info"
              title={`Check the full job on ${applySiteLabel(application.application_url)} first`}
              action={
                <button onClick={focusRecheck} className={buttonClasses("secondary", "sm")}>
                  <FileSearch size={12} /> Paste it
                </button>
              }
            >
              Job alerts only include the title. Paste the description so Pathlight can check the experience it asks for
              and re-tailor your resume to its exact wording (that&apos;s what ATS filters match on).
            </Alert>
          )}

          {lastStage === "READY_TO_APPLY" && tailored && (
            <section className="animate-fade-in">
              {uncertain && (
                <Alert tone="warn" className="mb-3">
                  Eligibility is uncertain.{" "}
                  <button onClick={focusRecheck} className="font-semibold underline underline-offset-2">
                    Check against the full posting
                  </button>{" "}
                  before you apply.
                </Alert>
              )}
              <ReviewApplyCard application={application} tailored={tailored} onReviewed={onReviewed} onTailoredChange={setTailored} />
            </section>
          )}

          {lastStage === "MANUAL_APPLY_REQUIRED" && (
            <section className="animate-fade-in">
              <FinishApplyPanel
                application={application}
                tailored={tailored}
                onMarked={(a) => {
                  setApplication(a);
                  toast("Marked as applied", { description: "Good luck! Record interviews or offers here as they happen." });
                }}
              />
            </section>
          )}

          {(lastStage === "READY_TO_APPLY" || lastStage === "MANUAL_APPLY_REQUIRED") && (
            <section className="animate-fade-in">
              <SectionLabel>Application kit</SectionLabel>
              <ApplicationKitPanel applicationId={application.id} site={applySiteLabel(application.application_url)} />
            </section>
          )}

          {applied && (
            <Card className="flex items-center gap-3.5 p-4">
              <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${lastStage === "OFFER" ? "bg-ok text-white" : "bg-ok-soft text-ok"}`}>
                {lastStage === "OFFER" ? <PartyPopper size={16} /> : lastStage === "APPLIED" ? <Mail size={15} /> : <Check size={16} strokeWidth={2.6} />}
              </span>
              <div className="min-w-0">
                <div className="text-[15px] font-semibold text-fg">{lastStage === "OFFER" ? "You got an offer" : stageMeta?.label ?? "Applied"}</div>
                <div className="text-[13px] text-muted">{lastNote ?? "Your application is in. Good luck!"}</div>
              </div>
            </Card>
          )}

          {lastStage === "SKIPPED_BY_USER" && (
            <Card className="flex items-center gap-3 p-4 text-[13px] text-muted">
              <SkipForward size={16} /> You skipped this one — nothing was sent.
            </Card>
          )}

          {(application.eligibility || application.skill_gap) && (
            <section>
              <SectionLabel>Analysis</SectionLabel>
              <div className="grid gap-4 xl:grid-cols-2">
                {application.eligibility && (
                  <EligibilityCard
                    eligibility={application.eligibility}
                    action={
                      uncertain || notEligible ? (
                        <button onClick={focusRecheck} className="flex items-center gap-1.5 text-[13px] font-medium text-fg hover:underline">
                          <FileSearch size={13} /> Re-check with the full posting
                        </button>
                      ) : undefined
                    }
                  />
                )}
                {application.skill_gap && <SkillGapCard skillGap={application.skill_gap} skillGapNote={application.skill_gap_note} />}
              </div>
            </section>
          )}
        </div>

        <aside className="space-y-4">
          {applied && <TrackProgress application={application} onUpdated={setApplication} />}
          {!decided && (
            <RecheckCard
              application={application}
              onUpdated={setApplication}
              onRetailored={setTailored}
              highlight={highlightRecheck}
              textareaRef={recheckRef}
            />
          )}
          <Card className="p-4">
            <div className="text-[13px] font-medium text-fg">Details</div>
            <dl className="mt-3 space-y-2.5 text-[13px]">
              <div className="flex justify-between gap-3">
                <dt className="text-subtle">Source</dt>
                <dd className="text-right text-fg">{application.source === "gmail_mcp" ? "Gmail job alert" : application.source === "email_forward" ? "Forwarded job alert" : application.source?.startsWith("web:") ? "Company job board" : "Added by you"}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-subtle">Deadline</dt>
                <dd className="text-right text-fg">
                  {application.deadline ? new Date(application.deadline).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "Not stated"}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-subtle">Apply via</dt>
                <dd className="truncate text-right text-fg">{application.apply_email ?? (application.application_url ? site : "Original source")}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-subtle">Added</dt>
                <dd className="text-right text-fg">{new Date(application.created_at).toLocaleDateString(undefined, { day: "numeric", month: "short" })}</dd>
              </div>
            </dl>
          </Card>
          <Card className="p-4">
            <div className="mb-3 text-[13px] font-medium text-fg">Activity</div>
            <StatusTimeline history={application.status_history} />
          </Card>
        </aside>
      </div>
    </div>
  );
}
