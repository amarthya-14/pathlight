"use client";

import { useMemo, useState } from "react";
import { Check, ClipboardCopy, Download, ExternalLink, Mail, Send, SkipForward, Sparkles, TriangleAlert } from "lucide-react";
import { api, ApiError, saveBlob } from "@/lib/api";
import { diffLines } from "@/lib/diff";
import type { ApplicationOut, ReviewResponse, TailoredResumeOut } from "@/lib/types";
import { ConfidenceBar } from "./ConfidenceBar";
import { Button } from "./ui";

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
    <div className="card-shadow space-y-5 rounded-2xl border border-indigo-200 bg-white p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
            <Sparkles size={16} className="text-indigo-500" /> Tailored resume ready for your review
          </div>
          <p className="mt-1 text-sm text-slate-500">
            Nothing is sent until you approve.{" "}
            {application.apply_email ? (
              <>
                Approving emails it to <span className="font-medium text-slate-700">{application.apply_email}</span>{" "}
                from your connected Gmail.
              </>
            ) : application.application_url ? (
              <>
                One click opens the job on {site}, downloads this resume as a PDF and copies the cover note — you
                just upload, paste and press Submit there.
              </>
            ) : (
              "This posting has no application email or link, so you'll apply through the original source."
            )}
          </p>
        </div>
        <div className="w-36 shrink-0">
          <ConfidenceBar confidence={tailored.confidence} />
        </div>
      </div>

      {tailored.warnings.length > 0 && (
        <ul className="space-y-1.5 rounded-xl bg-amber-50 px-3.5 py-3 text-sm text-amber-800">
          {tailored.warnings.map((w) => (
            <li key={w} className="flex gap-2">
              <TriangleAlert size={15} className="mt-0.5 shrink-0" /> {w}
            </li>
          ))}
        </ul>
      )}

      {tailored.changes_summary.length > 0 && (
        <div>
          <div className="mb-1.5 text-xs font-semibold uppercase tracking-widest text-slate-400">What changed</div>
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
            {tailored.changes_summary.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <div className="mb-1.5 flex items-center justify-between">
          <div className="text-xs font-semibold uppercase tracking-widest text-slate-400">
            Resume {lines ? `· ${changedCount} line${changedCount === 1 ? "" : "s"} changed` : ""}
          </div>
          {lines && (
            <label className="flex items-center gap-1.5 text-xs text-slate-500">
              <input type="checkbox" checked={onlyChanges} onChange={(e) => setOnlyChanges(e.target.checked)} />
              Only changes
            </label>
          )}
        </div>
        <div
          data-testid="resume-diff"
          className="max-h-96 overflow-auto rounded-xl border border-slate-200 bg-slate-50 font-mono text-xs leading-relaxed"
        >
          {visibleLines
            ? visibleLines.map((line, i) => (
                <div
                  key={i}
                  data-diff={line.type}
                  className={`whitespace-pre-wrap px-3 ${
                    line.type === "added"
                      ? "bg-emerald-50 text-emerald-800"
                      : line.type === "removed"
                        ? "bg-rose-50 text-rose-700 line-through decoration-rose-300"
                        : "text-slate-600"
                  }`}
                >
                  {line.type === "added" ? "+ " : line.type === "removed" ? "− " : "  "}
                  {line.text || " "}
                </div>
              ))
            : <div className="whitespace-pre-wrap p-3 text-slate-700">{tailored.tailored_text}</div>}
        </div>
      </div>

      <div>
        <div className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-widest text-slate-400">
          <Mail size={13} /> Cover note
        </div>
        <div className="whitespace-pre-wrap rounded-xl border border-slate-200 p-3.5 text-sm text-slate-700">
          {tailored.cover_note}
        </div>
      </div>

      {error && <p className="text-sm font-medium text-rose-600">{error}</p>}

      {confirming ? (
        <div className="flex flex-wrap items-center gap-3 rounded-xl bg-indigo-50 px-4 py-3">
          <span className="text-sm text-indigo-900">
            Send this application to <strong>{application.apply_email}</strong> now? This can&apos;t be undone.
          </span>
          <div className="ml-auto flex gap-2">
            <Button variant="secondary" onClick={() => setConfirming(false)} disabled={submitting !== null}>
              Cancel
            </Button>
            <Button onClick={() => submit(true)} disabled={submitting !== null}>
              <Send size={15} /> {submitting === "approve" ? "Sending…" : "Yes, send it"}
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          <Button onClick={onApproveClick} disabled={submitting !== null}>
            {application.apply_email ? <Send size={15} /> : <ExternalLink size={15} />}
            {application.apply_email
              ? "Approve & send"
              : submitting === "approve"
                ? "Preparing…"
                : application.application_url
                  ? `Apply on ${site}`
                  : "Approve — I'll apply manually"}
          </Button>
          <Button variant="secondary" onClick={() => submit(false)} disabled={submitting !== null}>
            <SkipForward size={15} /> {submitting === "skip" ? "Skipping…" : "Skip"}
          </Button>
        </div>
      )}
    </div>
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

  return (
    <div className="card-shadow space-y-4 rounded-2xl border border-amber-200 bg-amber-50/60 p-5">
      <div>
        <div className="text-sm font-semibold text-amber-900">Finish applying on {site}</div>
        <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-amber-900/80">
          <li>On the {site} job page, click Apply.</li>
          <li>Upload the tailored resume PDF (it should be in your Downloads).</li>
          <li>Paste the cover note if there&apos;s a message or cover letter field.</li>
          <li>Submit there, then come back and confirm below.</li>
        </ol>
      </div>
      <div className="flex flex-wrap gap-2">
        {application.application_url && (
          <a
            href={application.application_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 shadow-sm hover:bg-slate-50"
          >
            <ExternalLink size={15} /> Open job on {site}
          </a>
        )}
        <Button variant="secondary" onClick={onDownload} disabled={!tailored}>
          <Download size={15} /> Resume PDF
        </Button>
        <Button variant="secondary" onClick={onCopy} disabled={!tailored}>
          {copied ? <Check size={15} /> : <ClipboardCopy size={15} />} {copied ? "Copied" : "Copy cover note"}
        </Button>
      </div>
      {error && <p className="text-sm font-medium text-rose-600">{error}</p>}
      <Button onClick={onMark} disabled={busy}>
        <Check size={15} /> {busy ? "Saving…" : `I've submitted it on ${site}`}
      </Button>
    </div>
  );
}
