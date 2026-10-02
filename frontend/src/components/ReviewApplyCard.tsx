"use client";

import { useMemo, useState } from "react";
import { ExternalLink, Mail, Send, SkipForward, Sparkles, TriangleAlert } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { diffLines } from "@/lib/diff";
import type { ApplicationOut, ReviewResponse, TailoredResumeOut } from "@/lib/types";
import { ConfidenceBar } from "./ConfidenceBar";
import { Button } from "./ui";

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
    // Manual-apply approvals send nothing, so they don't need the extra confirm step.
    if (application.apply_email) setConfirming(true);
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
            ) : (
              "This posting has no application email, so you'll apply through its link."
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
            {application.apply_email ? "Approve & send" : submitting === "approve" ? "Saving…" : "Approve — I'll apply manually"}
          </Button>
          <Button variant="secondary" onClick={() => submit(false)} disabled={submitting !== null}>
            <SkipForward size={15} /> {submitting === "skip" ? "Skipping…" : "Skip"}
          </Button>
        </div>
      )}
    </div>
  );
}
