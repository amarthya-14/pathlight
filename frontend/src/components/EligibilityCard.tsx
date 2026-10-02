import { Check, CheckCircle2, CircleAlert, CircleHelp, Minus, XCircle } from "lucide-react";
import type { EligibilityResult } from "@/lib/types";
import { ConfidenceBar } from "./ConfidenceBar";
import { Card } from "./ui";

const DECISION_STYLE: Record<string, { label: string; icon: typeof CheckCircle2; text: string; bg: string }> = {
  eligible: { label: "Eligible", icon: CheckCircle2, text: "text-ok", bg: "bg-ok-soft" },
  partially_eligible: { label: "Partially Eligible", icon: CircleAlert, text: "text-warn", bg: "bg-warn-soft" },
  not_eligible: { label: "Not Eligible", icon: XCircle, text: "text-bad", bg: "bg-bad-soft" },
  uncertain: { label: "Uncertain", icon: CircleHelp, text: "text-muted", bg: "bg-surface-2" },
};

/**
 * Renders an EligibilityResult with its full reasoning — decision, reason, evidence,
 * missing_information, confidence — never just the verdict badge. This is a stated
 * non-negotiable rule in docs/AI_DESIGN.md: don't let the frontend flatten a structured
 * AI decision down to "Eligible ✅" and hide why.
 */
export function EligibilityCard({ eligibility, action }: { eligibility: EligibilityResult; action?: React.ReactNode }) {
  const style = DECISION_STYLE[eligibility.decision] ?? DECISION_STYLE.uncertain;
  const Icon = style.icon;

  return (
    <Card className="flex h-full flex-col p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-[13px] text-subtle">Eligibility</div>
          <div className={`mt-1 inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-sm font-semibold ${style.bg} ${style.text}`}>
            <Icon size={14} strokeWidth={2.2} />
            {style.label}
          </div>
        </div>
        <ConfidenceBar confidence={eligibility.confidence} />
      </div>

      <p className="mt-4 text-sm leading-relaxed text-fg">{eligibility.reason}</p>

      {eligibility.evidence.length > 0 && (
        <ul className="mt-4 space-y-1.5">
          {eligibility.evidence.map((item, i) => (
            <li key={i} className="flex items-start gap-2 text-[13px] text-muted">
              <Check size={13} className="mt-[3px] shrink-0 text-subtle" strokeWidth={2.4} />
              {item}
            </li>
          ))}
        </ul>
      )}

      {eligibility.missing_information.length > 0 && (
        <div className="mt-4 rounded-lg border border-dashed border-line-strong p-3">
          <div className="text-xs font-medium text-subtle">Couldn&apos;t verify</div>
          <ul className="mt-1.5 space-y-1">
            {eligibility.missing_information.map((item, i) => (
              <li key={i} className="flex items-start gap-2 text-[13px] text-muted">
                <Minus size={13} className="mt-[3px] shrink-0 text-subtle" />
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}

      {action && <div className="mt-auto pt-4">{action}</div>}
    </Card>
  );
}
