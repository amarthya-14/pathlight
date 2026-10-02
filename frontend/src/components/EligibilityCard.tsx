import { CheckCircle2, CircleAlert, CircleHelp, XCircle } from "lucide-react";
import type { EligibilityResult } from "@/lib/types";
import { ConfidenceBar } from "./ConfidenceBar";
import { Card, type Tone } from "./ui";

const DECISION_STYLE: Record<string, { label: string; tone: Tone; icon: typeof CheckCircle2; ring: string; text: string; bg: string }> = {
  eligible: { label: "Eligible", tone: "ok", icon: CheckCircle2, ring: "ring-ok/25", text: "text-ok", bg: "bg-ok-soft" },
  partially_eligible: {
    label: "Partially Eligible",
    tone: "warn",
    icon: CircleAlert,
    ring: "ring-warn/25",
    text: "text-warn",
    bg: "bg-warn-soft",
  },
  not_eligible: { label: "Not Eligible", tone: "bad", icon: XCircle, ring: "ring-bad/25", text: "text-bad", bg: "bg-bad-soft" },
  uncertain: { label: "Uncertain", tone: "neutral", icon: CircleHelp, ring: "ring-line-strong", text: "text-muted", bg: "bg-surface-2" },
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
    <Card className="h-full p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className={`flex h-10 w-10 items-center justify-center rounded-xl ring-1 ${style.bg} ${style.text} ${style.ring}`}>
            <Icon size={20} strokeWidth={2.2} />
          </span>
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-subtle">Eligibility</div>
            <div className={`text-base font-semibold ${style.text}`}>{style.label}</div>
          </div>
        </div>
        <ConfidenceBar confidence={eligibility.confidence} />
      </div>

      <p className="mt-4 text-sm leading-relaxed text-fg/90">{eligibility.reason}</p>

      {eligibility.evidence.length > 0 && (
        <div className="mt-5">
          <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-subtle">Evidence</div>
          <ul className="mt-2 space-y-1.5">
            {eligibility.evidence.map((item, i) => (
              <li key={i} className="flex items-start gap-2.5 text-sm text-muted">
                <CheckCircle2 size={14} className="mt-0.5 shrink-0 text-ok" />
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}

      {eligibility.missing_information.length > 0 && (
        <div className="mt-5">
          <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-subtle">Missing information</div>
          <ul className="mt-2 space-y-1.5">
            {eligibility.missing_information.map((item, i) => (
              <li key={i} className="flex items-start gap-2.5 text-sm text-muted">
                <CircleHelp size={14} className="mt-0.5 shrink-0 text-warn" />
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}
