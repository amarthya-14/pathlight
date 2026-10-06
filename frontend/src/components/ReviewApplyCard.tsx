"use client";

import { useMemo, useState } from "react";
import {
  Check,
  ClipboardCopy,
  Download,
  ExternalLink,
  FileText,
  Mail,
  PenLine,
  Send,
  ShieldCheck,
  SkipForward,
  TriangleAlert,
} from "lucide-react";
import { api, ApiError, saveBlob } from "@/lib/api";
import { diffLines } from "@/lib/diff";
import type { ApplicationOut, AtsReport, ReviewResponse, TailoredResumeOut } from "@/lib/types";
import { ScoreRing } from "./Motion";
import { ConfidenceBar } from "./ConfidenceBar";
import { Button, buttonClasses, Card, cx, TextArea } from "./ui";

export function applySiteLabel(url: string | null): string {
  if (!url) return "the posting site";
  try {
    const host = new URL(url).hostname;
    if (host.includes("linkedin.")) return "LinkedIn";
    if (host.includes("naukri.")) return "Naukri";
    return host.replace(/^www\./, "");
  } catch {
    return "the posting site";
  }
}

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

const ATS_PARTS: { key: keyof AtsReport["breakdown"]; label: string; max: number }[] = [
  { key: "keywords", label: "Keywords from the posting", max: 45 },
  { key: "sections", label: "Standard sections", max: 15 },
  { key: "format", label: "ATS-readable format", max: 15 },
  { key: "contact", label: "Contact & links", max: 10 },
  { key: "impact", label: "Action-led bullets", max: 10 },
  { key: "job_title", label: "Target job title", max: 5 },
];

// The tailored resume's ATS score, with the honest ceiling spelled out: points that
// need skills the resume doesn't show are named, never earned by inventing them. The user
// can tick the ones they genuinely know; the tailor then adds those to Technical Skills.
export function AtsPanel({
  ats,
  onDownload,
  onAddSkills,
}: {
  ats: AtsReport;
  onDownload?: () => void;
  onAddSkills?: (skills: string[]) => Promise<void>;
}) {
  const [picked, setPicked] = useState<string[]>([]);
  const [adding, setAdding] = useState(false);
  const toggle = (s: string) => setPicked((p) => (p.includes(s) ? p.filter((x) => x !== s) : [...p, s]));
  const addPicked = async () => {
    if (!onAddSkills || picked.length === 0) return;
    setAdding(true);
    try {
      await onAddSkills(picked);
      setPicked([]);
    } finally {
      setAdding(false);
    }
  };
  const ceiling = 100 - ats.blocked_points;
  const atCeiling = ats.score >= ceiling;
  const tone = ats.score >= 90 ? "ok" : ats.score >= 75 ? "accent" : "warn";
  return (
    <div className="grid gap-5 rounded-xl border border-line bg-surface-2/60 p-4 sm:grid-cols-[auto_1fr] sm:p-5">
      <div className="flex items-center gap-4 sm:flex-col sm:items-center sm:gap-2">
        <ScoreRing value={ats.score} size={84} stroke={7} tone={tone} label="ATS" />
        <div className="text-[13px] sm:text-center">
          <div className="font-semibold text-fg">{ats.score === 100 ? "Perfect match" : atCeiling ? "Best honest score" : "Room to improve"}</div>
          {onDownload && (
            <button onClick={onDownload} className="mt-0.5 text-xs text-muted underline-offset-4 hover:text-fg hover:underline">
              Download PDF
            </button>
          )}
        </div>
      </div>
      <div className="min-w-0">
        <div className="space-y-2">
          {ATS_PARTS.map(({ key, label, max }) => {
            const value = ats.breakdown[key] ?? 0;
            return (
              <div key={key} className="flex items-center gap-3 text-[12.5px]">
                <span className="w-40 shrink-0 truncate text-muted">{label}</span>
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-hover">
                  <div
                    className={cx("h-full rounded-full transition-[width] duration-1000", value >= max ? "bg-ok" : "bg-accent")}
                    style={{ width: `${(value / max) * 100}%`, transitionTimingFunction: "var(--ease-out)" }}
                  />
                </div>
                <span className="w-11 text-right font-medium tabular-nums text-fg">
                  {value}/{max}
                </span>
              </div>
            );
          })}
        </div>
        {ats.missing_keywords.length > 0 && !onAddSkills && (
          <p className="mt-3 text-[12.5px] leading-relaxed text-muted">
            <span className="font-medium text-fg">{ats.blocked_points} points need skills that aren&apos;t on your resume</span> —{" "}
            {ats.missing_keywords.join(", ")}. Pathlight won&apos;t claim them for you; learn them (see your prep plan) and
            re-tailor to reach {Math.min(100, ats.score + ats.blocked_points)}.
          </p>
        )}
        {ats.missing_keywords.length > 0 && onAddSkills && (
          <div className="mt-3 text-[12.5px] leading-relaxed text-muted">
            <p>
              <span className="font-medium text-fg">{ats.blocked_points} points need skills your resume doesn&apos;t show.</span>{" "}
              Tick the ones you genuinely know and they&apos;ll be added to your Technical Skills — you&apos;ll be asked
              about them in interviews.
            </p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {ats.missing_keywords.map((s) => {
                const on = picked.includes(s);
                return (
                  <button
                    key={s}
                    type="button"
                    onClick={() => toggle(s)}
                    aria-pressed={on}
                    className={cx(
                      "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs transition-colors",
                      on ? "border-accent bg-accent/10 text-fg" : "border-line text-muted hover:text-fg"
                    )}
                  >
                    {on && <Check size={12} />}
                    {s}
                  </button>
                );
              })}
            </div>
            {picked.length > 0 && (
              <Button className="mt-2.5" size="sm" onClick={addPicked} loading={adding} disabled={adding}>
                {adding ? "Re-tailoring…" : `Add ${picked.length} skill${picked.length > 1 ? "s" : ""} & re-tailor`}
              </Button>
            )}
          </div>
        )}
        {!atCeiling && ats.suggestions.length > 0 && (
          <ul className="mt-3 space-y-1 text-[12.5px] text-muted">
            {ats.suggestions.map((s) => (
              <li key={s}>• {s}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

// Gate 10 human review gate (docs/AUTONOMOUS_APPLICATIONS.md §8). Shows exactly what
// would be sent — the resume diff, the cover note, the destination — and never advances
// on its own: sending needs Approve AND an explicit confirm naming the recipient.
export function ReviewApplyCard({
  application,
  tailored,
  onReviewed,
  onTailoredChange,
}: {
  application: ApplicationOut;
  tailored: TailoredResumeOut;
  onReviewed: (response: ReviewResponse) => void;
  onTailoredChange?: (t: TailoredResumeOut) => void;
}) {
  const [tab, setTab] = useState<"resume" | "cover">("resume");
  const [editing, setEditing] = useState(false);
  const [draftResume, setDraftResume] = useState(tailored.tailored_text);
  const [draftCover, setDraftCover] = useState(tailored.cover_note);
  const [savingEdit, setSavingEdit] = useState(false);

  const startEditing = () => {
    setDraftResume(tailored.tailored_text);
    setDraftCover(tailored.cover_note);
    setEditing(true);
  };
  const saveEdits = async () => {
    setSavingEdit(true);
    setError(null);
    try {
      onTailoredChange?.(await api.editTailoredResume(application.id, draftResume, draftCover));
      setEditing(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't save your edits");
    } finally {
      setSavingEdit(false);
    }
  };
  const [onlyChanges, setOnlyChanges] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [submitting, setSubmitting] = useState<"approve" | "skip" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const lines = useMemo(
    () => (tailored.base_resume_text === null ? null : diffLines(tailored.base_resume_text, tailored.tailored_text)),
    [tailored.base_resume_text, tailored.tailored_text]
  );
  const changedCount = lines?.filter((l) => l.type !== "same").length ?? 0;
  const visibleLines = lines && onlyChanges ? lines.filter((l) => l.type !== "same") : lines;

  // Assisted apply (no apply_email, but a posting link): one click opens the posting,
  // copies the cover note, downloads the tailored PDF, and records the approval. The
  // final Submit happens on the site itself — no bot drives the user's account there.
  const site = applySiteLabel(application.application_url);
  const assistedApply = async () => {
    // window.open must run synchronously inside the click, or popup blockers eat it.
    window.open(application.application_url!, "_blank", "noopener,noreferrer");
    const copied = copyText(tailored.cover_note);
    setSubmitting("approve");
    setError(null);
    try {
      const { blob, filename } = await api.downloadTailoredResumePdf(application.id);
      saveBlob(blob, filename);
      await copied;
      onReviewed(await api.reviewApplication(application.id, true));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Something went wrong preparing your application");
    } finally {
      setSubmitting(null);
    }
  };

  const submit = async (approve: boolean) => {
    setSubmitting(approve ? "approve" : "skip");
    setError(null);
    try {
      onReviewed(await api.reviewApplication(application.id, approve));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Review failed");
      setConfirming(false);
    } finally {
      setSubmitting(null);
    }
  };

  const onApproveClick = () => {
    // Only a real send needs the extra confirm step — the other paths send nothing.
    if (application.apply_email) setConfirming(true);
    else if (application.application_url) assistedApply();
    else submit(true);
  };

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-col gap-3 p-5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="text-[15px] font-semibold text-fg">Tailored resume ready for your review</div>
          <p className="mt-1 max-w-xl text-[13px] leading-relaxed text-muted">
            Nothing is sent until you approve.{" "}
            {application.apply_email ? (
              <>
                Approving emails it to <span className="font-medium text-fg">{application.apply_email}</span> from your
                connected Gmail.
              </>
            ) : application.application_url ? (
              <>
                One click opens the job on {site}, downloads this resume as a PDF and copies the cover note — you just
                upload, paste and press Submit there.
              </>
            ) : (
              "This posting has no application email or link, so you'll apply through the original source."
            )}
          </p>
        </div>
        <div className="shrink-0">
          <ConfidenceBar confidence={tailored.confidence} />
        </div>
      </div>

      <div className="space-y-3 px-5">
        {tailored.ats && (
          <AtsPanel
            ats={tailored.ats}
            onAddSkills={
              onTailoredChange
                ? async (skills) => {
                    setError(null);
                    try {
                      onTailoredChange(await api.tailorApplication(application.id, skills));
                    } catch (err) {
                      setError(err instanceof ApiError ? err.detail : "Couldn't re-tailor your resume");
                    }
                  }
                : undefined
            }
            onDownload={async () => {
              try {
                const { blob, filename } = await api.downloadTailoredResumePdf(application.id);
                saveBlob(blob, filename);
              } catch (err) {
                setError(err instanceof ApiError ? err.detail : "Download failed");
              }
            }}
          />
        )}
        <div className="flex items-center gap-2 text-[13px] text-ok">
          <ShieldCheck size={14} className="shrink-0" /> Checked: every skill here is on your original, implied by it,
          or confirmed by you.
        </div>
        {tailored.warnings.length > 0 && (
          <ul className="space-y-1.5 rounded-lg bg-warn-soft px-3.5 py-2.5 text-[13px] text-warn">
            {tailored.warnings.map((w) => (
              <li key={w} className="flex gap-2">
                <TriangleAlert size={14} className="mt-[2px] shrink-0" /> {w}
              </li>
            ))}
          </ul>
        )}
        {tailored.changes_summary.length > 0 && (
          <ul className="space-y-1.5 pt-1">
            {tailored.changes_summary.map((c) => (
              <li key={c} className="flex gap-2 text-[13px] text-muted">
                <Check size={14} className="mt-[2px] shrink-0 text-subtle" strokeWidth={2.4} />
                {c}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="mt-5 border-t border-line">
        <div className="flex items-center justify-between gap-3 border-b border-line px-5">
          <div className="flex gap-5" role="tablist">
            {(
              [
                ["resume", FileText, `Resume${lines ? ` · ${changedCount} change${changedCount === 1 ? "" : "s"}` : ""}`],
                ["cover", Mail, "Cover note"],
              ] as const
            ).map(([key, Icon, label]) => (
              <button
                key={key}
                role="tab"
                aria-selected={tab === key}
                onClick={() => setTab(key)}
                className={`-mb-px flex items-center gap-1.5 border-b-2 py-2.5 text-[13px] font-medium transition-colors ${
                  tab === key ? "border-fg text-fg" : "border-transparent text-subtle hover:text-muted"
                }`}
              >
                <Icon size={13} /> {label}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-3">
          {onTailoredChange && !editing && (
            <button onClick={startEditing} className="flex items-center gap-1 text-xs font-medium text-muted hover:text-fg">
              <PenLine size={12} /> Edit
            </button>
          )}
          {tab === "resume" && lines && !editing && (
            <label className="flex cursor-pointer items-center gap-1.5 text-xs text-muted">
              <input type="checkbox" className="h-3.5 w-3.5 accent-[var(--ink)]" checked={onlyChanges} onChange={(e) => setOnlyChanges(e.target.checked)} />
              Only changes
            </label>
          )}
          </div>
        </div>

        {editing && (
          <div className="animate-fade-in space-y-3 bg-surface-2 p-4">
            <TextArea
              aria-label="Tailored resume"
              rows={18}
              value={tab === "resume" ? draftResume : draftCover}
              onChange={(e) => (tab === "resume" ? setDraftResume(e.target.value) : setDraftCover(e.target.value))}
              className="font-mono text-[12.5px]"
            />
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs text-subtle">Your words, your call — the ATS score is re-checked when you save.</p>
              <div className="flex gap-2">
                <Button variant="ghost" size="sm" onClick={() => setEditing(false)} disabled={savingEdit}>
                  Cancel
                </Button>
                <Button size="sm" onClick={saveEdits} loading={savingEdit}>
                  Save edits
                </Button>
              </div>
            </div>
          </div>
        )}

        <div
          data-testid="resume-diff"
          className={`max-h-[440px] overflow-auto bg-surface-2 py-3 font-mono text-[12px] leading-[1.7] ${tab === "resume" && !editing ? "" : "hidden"}`}
        >
          {visibleLines ? (
            visibleLines.map((line, i) => (
              <div
                key={i}
                data-diff={line.type}
                className={`whitespace-pre-wrap px-5 ${
                  line.type === "added"
                    ? "bg-ok-soft text-ok"
                    : line.type === "removed"
                      ? "bg-bad-soft text-bad line-through decoration-bad/40"
                      : "text-muted"
                }`}
              >
                <span className="mr-3 inline-block w-2 select-none opacity-50">
                  {line.type === "added" ? "+" : line.type === "removed" ? "−" : ""}
                </span>
                {line.text || " "}
              </div>
            ))
          ) : (
            <div className="whitespace-pre-wrap px-5 text-fg">{tailored.tailored_text}</div>
          )}
        </div>
        <div className={`max-h-[440px] overflow-auto whitespace-pre-wrap bg-surface-2 px-5 py-4 text-sm leading-relaxed text-fg ${tab === "cover" && !editing ? "" : "sr-only"}`}>
          {tailored.cover_note}
        </div>
      </div>

      {error && (
        <div className="flex items-start gap-2 border-t border-line bg-bad-soft px-5 py-3 text-[13px] font-medium text-bad">
          <TriangleAlert size={15} className="mt-[1px] shrink-0" />
          {error}
        </div>
      )}

      <div className="border-t border-line px-5 py-3.5">
        {confirming ? (
          <div className="animate-scale-in flex flex-col gap-3 sm:flex-row sm:items-center">
            <span className="text-[13px] text-fg">
              Send this application to <strong>{application.apply_email}</strong> now? This can&apos;t be undone.
            </span>
            <div className="flex gap-2 sm:ml-auto">
              <Button variant="secondary" onClick={() => setConfirming(false)} disabled={submitting !== null}>
                Cancel
              </Button>
              <Button onClick={() => submit(true)} disabled={submitting !== null} loading={submitting === "approve"}>
                {submitting !== "approve" && <Send size={14} />} {submitting === "approve" ? "Sending…" : "Yes, send it"}
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-end">
            <Button variant="ghost" onClick={() => submit(false)} disabled={submitting !== null}>
              <SkipForward size={14} /> {submitting === "skip" ? "Skipping…" : "Skip"}
            </Button>
            <Button onClick={onApproveClick} disabled={submitting !== null}>
              {application.apply_email ? <Send size={14} /> : <ExternalLink size={14} />}
              {application.apply_email
                ? "Approve & send"
                : submitting === "approve"
                  ? "Preparing…"
                  : application.application_url
                    ? `Apply on ${site}`
                    : "Approve — I'll apply manually"}
            </Button>
          </div>
        )}
      </div>
    </Card>
  );
}

// Shown after an assisted-apply approval (MANUAL_APPLY_REQUIRED): everything needed to
// finish on the posting site, plus the one honest way to reach APPLIED — the user saying so.
export function FinishApplyPanel({
  application,
  tailored,
  onMarked,
}: {
  application: ApplicationOut;
  tailored: TailoredResumeOut | null;
  onMarked: (application: ApplicationOut) => void;
}) {
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const site = applySiteLabel(application.application_url);

  const onCopy = async () => setCopied(await copyText(tailored?.cover_note ?? ""));
  const onDownload = async () => {
    setError(null);
    try {
      const { blob, filename } = await api.downloadTailoredResumePdf(application.id);
      saveBlob(blob, filename);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Download failed");
    }
  };
  const onMark = async () => {
    setBusy(true);
    setError(null);
    try {
      onMarked(await api.markApplied(application.id));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not update status");
    } finally {
      setBusy(false);
    }
  };

  const steps = [
    `Open the job on ${site} and click Apply.`,
    "Upload your tailored resume PDF from Downloads.",
    "Screening questions? Copy honest answers from the Application kit below.",
    `Submit on ${site}, then confirm below.`,
  ];

  return (
    <Card className="overflow-hidden">
      <div className="p-5">
        <div className="text-[15px] font-semibold text-fg">Finish applying on {site}</div>
        <p className="mt-1 text-[13px] text-muted">Everything&apos;s ready — four quick steps.</p>
        <ol className="mt-4 grid gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-2">
          {steps.map((step, i) => (
            <li key={step} className="flex items-start gap-3 bg-surface p-3.5 text-[13px] text-fg">
              <span className="font-mono text-[11px] leading-5 text-subtle">0{i + 1}</span>
              {step}
            </li>
          ))}
        </ol>
        <div className="mt-4 flex flex-wrap gap-2">
          {application.application_url && (
            <a href={application.application_url} target="_blank" rel="noopener noreferrer" className={buttonClasses("secondary", "md")}>
              <ExternalLink size={14} /> Open job on {site}
            </a>
          )}
          <Button variant="secondary" onClick={onDownload} disabled={!tailored}>
            <Download size={14} /> Resume PDF
          </Button>
          <Button variant="secondary" onClick={onCopy} disabled={!tailored}>
            {copied ? <Check size={14} className="text-ok" /> : <ClipboardCopy size={14} />} {copied ? "Copied" : "Copy cover note"}
          </Button>
        </div>
        {error && <p className="mt-3 text-[13px] font-medium text-bad">{error}</p>}
      </div>
      <div className="flex justify-end border-t border-line px-5 py-3.5">
        <Button onClick={onMark} loading={busy}>
          {!busy && <Check size={14} strokeWidth={2.6} />} {busy ? "Saving…" : `I've submitted it on ${site}`}
        </Button>
      </div>
    </Card>
  );
}
