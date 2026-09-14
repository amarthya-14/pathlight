import { CheckCircle2, CircleAlert, CircleHelp, XCircle } from "lucide-react";
import type { EligibilityResult } from "@/lib/types";
import { ConfidenceBar } from "./ConfidenceBar";

const DECISION_STYLE: Record<
  string,
  { label: string; classes: string; icon: typeof CheckCircle2 }
> = {
  eligible: { label: "Eligible", classes: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-600/20", icon: CheckCircle2 },
  partially_eligible: {
    label: "Partially Eligible",
    classes: "bg-amber-50 text-amber-700 ring-1 ring-amber-600/20",
    icon: CircleAlert,
  },
  not_eligible: { label: "Not Eligible", classes: "bg-rose-50 text-rose-700 ring-1 ring-rose-600/20", icon: XCircle },
  uncertain: { label: "Uncertain", classes: "bg-slate-100 text-slate-600 ring-1 ring-slate-300", icon: CircleHelp },
};

/**
 * Renders an EligibilityResult with its full reasoning — decision, reason, evidence,
 * missing_information, confidence — never just the verdict badge. This is a stated
 * non-negotiable rule in docs/AI_DESIGN.md: don't let the frontend flatten a structured
 * AI decision down to "Eligible ✅" and hide why.
 */
export function EligibilityCard({ eligibility }: { eligibility: EligibilityResult }) {
  const style = DECISION_STYLE[eligibility.decision] ?? DECISION_STYLE.uncertain;
  const Icon = style.icon;

  return (
    <div className="card-shadow rounded-2xl border border-slate-200 bg-white p-5">
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${style.classes}`}>
          <Icon size={14} strokeWidth={2.25} />
          {style.label}
        </span>
        <ConfidenceBar confidence={eligibility.confidence} />
      </div>
      <p className="text-sm leading-relaxed text-slate-700">{eligibility.reason}</p>

      {eligibility.evidence.length > 0 && (
        <div className="mt-4">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Evidence</div>
          <ul className="mt-1.5 space-y-1">
            {eligibility.evidence.map((item, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-600">
                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-slate-300" />
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}

      {eligibility.missing_information.length > 0 && (
        <div className="mt-4">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Missing information</div>
          <ul className="mt-1.5 space-y-1">
            {eligibility.missing_information.map((item, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-600">
                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-amber-300" />
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
