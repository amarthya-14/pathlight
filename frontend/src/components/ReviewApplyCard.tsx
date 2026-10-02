"use client";

import { useMemo, useState } from "react";
import { Check, ClipboardCopy, Download, ExternalLink, FileText, Mail, Send, ShieldCheck, SkipForward, Sparkles, TriangleAlert } from "lucide-react";
import { api, ApiError, saveBlob } from "@/lib/api";
import { diffLines } from "@/lib/diff";
import type { ApplicationOut, ReviewResponse, TailoredResumeOut } from "@/lib/types";
import { ConfidenceBar } from "./ConfidenceBar";
import { Button, buttonClasses, Card } from "./ui";

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

// Gate 10 human review gate (docs/AUTONOMOUS_APPLICATIONS.md §8). Shows exactly what
// would be sent — the resume diff, the cover note, the destination — and never advances
// on its own: sending needs Approve AND an explicit confirm naming the recipient.
export function ReviewApplyCard({
  application,
  tailored,
  onReviewed,
}: {
  application: ApplicationOut;
  tailored: TailoredResumeOut;
  onReviewed: (response: ReviewResponse) => void;
}) {
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
    <Card glow className="overflow-hidden">
      {/* Header */}
      <div className="flex flex-col gap-4 border-b border-line p-5 sm:flex-row sm:items-start sm:justify-between sm:p-6">
        <div className="flex items-start gap-3.5">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-brand-gradient text-white shadow-glow">
            <Sparkles size={20} />
          </span>
          <div>
            <div className="font-semibold text-fg">Tailored resume ready for your review</div>
            <p className="mt-1 max-w-xl text-sm leading-relaxed text-muted">
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
        </div>
        <div className="shrink-0">
          <ConfidenceBar confidence={tailored.confidence} />
        </div>
      </div>

      <div className="space-y-5 p-5 sm:p-6">
        <div className="flex items-center gap-2 rounded-xl bg-ok-soft px-3.5 py-2.5 text-xs font-medium text-ok">
          <ShieldCheck size={15} className="shrink-0" /> Checked: this resume claims no skill that isn&apos;t on your
          original.
        </div>

        {tailored.warnings.length > 0 && (
          <ul className="space-y-2 rounded-xl bg-warn-soft px-4 py-3 text-sm text-warn">
            {tailored.warnings.map((w) => (
              <li key={w} className="flex gap-2.5">
                <TriangleAlert size={15} className="mt-0.5 shrink-0" /> {w}
              </li>
            ))}
          </ul>
        )}

        {tailored.changes_summary.length > 0 && (
          <div>
            <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-subtle">What changed</div>
            <ul className="grid gap-2 sm:grid-cols-2">
              {tailored.changes_summary.map((c) => (
                <li key={c} className="flex gap-2.5 rounded-xl border border-line bg-surface-2 px-3.5 py-2.5 text-sm text-fg/90">
                  <Check size={15} className="mt-0.5 shrink-0 text-accent-fg" strokeWidth={2.6} />
                  {c}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
          <div className="min-w-0">
            <div className="mb-2 flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-subtle">
                <FileText size={13} /> Resume {lines ? `· ${changedCount} line${changedCount === 1 ? "" : "s"} changed` : ""}
              </div>
              {lines && (
                <label className="flex cursor-pointer items-center gap-2 text-xs text-muted">
                  <input
                    type="checkbox"
                    className="h-3.5 w-3.5 accent-violet-500"
                    checked={onlyChanges}
                    onChange={(e) => setOnlyChanges(e.target.checked)}
                  />
                  Only changes
                </label>
              )}
            </div>
            <div
              data-testid="resume-diff"
              className="max-h-[420px] overflow-auto rounded-xl border border-line bg-bg-elevated py-2 font-mono text-[12px] leading-relaxed"
            >
              {visibleLines ? (
                visibleLines.map((line, i) => (
                  <div
                    key={i}
                    data-diff={line.type}
                    className={`whitespace-pre-wrap px-3.5 ${
                      line.type === "added"
                        ? "bg-ok-soft text-ok"
                        : line.type === "removed"
                          ? "bg-bad-soft text-bad line-through decoration-bad/40"
                          : "text-muted"
                    }`}
                  >
                    <span className="mr-2 inline-block w-3 select-none opacity-60">
                      {line.type === "added" ? "+" : line.type === "removed" ? "−" : ""}
                    </span>
                    {line.text || " "}
                  </div>
                ))
              ) : (
                <div className="whitespace-pre-wrap px-3.5 text-fg">{tailored.tailored_text}</div>
              )}
            </div>
          </div>

          <div className="min-w-0">
            <div className="mb-2 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-subtle">
              <Mail size={13} /> Cover note
            </div>
            <div className="max-h-[420px] overflow-auto whitespace-pre-wrap rounded-xl border border-line bg-bg-elevated p-4 text-sm leading-relaxed text-fg/90">
              {tailored.cover_note}
            </div>
          </div>
        </div>

        {error && (
          <div className="flex items-start gap-2.5 rounded-xl bg-bad-soft px-4 py-3 text-sm font-medium text-bad">
            <TriangleAlert size={16} className="mt-0.5 shrink-0" />
            {error}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="border-t border-line bg-surface-2 p-4 sm:px-6">
        {confirming ? (
          <div className="animate-scale-in flex flex-col gap-3 sm:flex-row sm:items-center">
            <span className="text-sm text-fg">
              Send this application to <strong className="text-accent-fg">{application.apply_email}</strong> now? This
              can&apos;t be undone.
            </span>
            <div className="flex gap-2 sm:ml-auto">
              <Button variant="secondary" onClick={() => setConfirming(false)} disabled={submitting !== null}>
                Cancel
              </Button>
              <Button onClick={() => submit(true)} disabled={submitting !== null} loading={submitting === "approve"}>
                {submitting !== "approve" && <Send size={15} />} {submitting === "approve" ? "Sending…" : "Yes, send it"}
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-end">
            <Button variant="ghost" onClick={() => submit(false)} disabled={submitting !== null}>
              <SkipForward size={15} /> {submitting === "skip" ? "Skipping…" : "Skip"}
            </Button>
            <Button size="lg" onClick={onApproveClick} disabled={submitting !== null}>
              {application.apply_email ? <Send size={16} /> : <ExternalLink size={16} />}
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
    "Upload your tailored resume PDF (check your Downloads).",
    "Paste the cover note into any message or cover-letter field.",
    `Submit on ${site}, then confirm below.`,
  ];

  return (
    <Card glow className="overflow-hidden">
      <div className="p-5 sm:p-6">
        <div className="flex items-start gap-3.5">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-warn-soft text-warn">
            <ExternalLink size={20} />
          </span>
          <div>
            <div className="font-semibold text-fg">Finish applying on {site}</div>
            <p className="mt-1 text-sm text-muted">Everything&apos;s ready — four quick steps and you&apos;re done.</p>
          </div>
        </div>
        <ol className="mt-5 grid gap-2.5 sm:grid-cols-2">
          {steps.map((step, i) => (
            <li key={step} className="flex items-start gap-3 rounded-xl border border-line bg-surface-2 p-3.5 text-sm text-fg/90">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent-soft text-xs font-semibold text-accent-fg">
                {i + 1}
              </span>
              {step}
            </li>
          ))}
        </ol>
        <div className="mt-5 flex flex-wrap gap-2">
          {application.application_url && (
            <a href={application.application_url} target="_blank" rel="noopener noreferrer" className={buttonClasses("secondary", "md")}>
              <ExternalLink size={15} /> Open job on {site}
            </a>
          )}
          <Button variant="secondary" onClick={onDownload} disabled={!tailored}>
            <Download size={15} /> Resume PDF
          </Button>
          <Button variant="secondary" onClick={onCopy} disabled={!tailored}>
            {copied ? <Check size={15} className="text-ok" /> : <ClipboardCopy size={15} />} {copied ? "Copied" : "Copy cover note"}
          </Button>
        </div>
        {error && <p className="mt-4 text-sm font-medium text-bad">{error}</p>}
      </div>
      <div className="flex justify-end border-t border-line bg-surface-2 p-4 sm:px-6">
        <Button size="lg" onClick={onMark} loading={busy}>
          {!busy && <Check size={16} strokeWidth={2.6} />} {busy ? "Saving…" : `I've submitted it on ${site}`}
        </Button>
      </div>
    </Card>
  );
}
