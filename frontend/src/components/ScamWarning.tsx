import { ShieldAlert } from "lucide-react";
import type { ScamCheck } from "@/lib/types";
import { cx } from "./ui";

// Red flags found in the posting text, each with the words that matched, so the student can
// judge for themselves (app/core/scam_check.py on the backend decides what counts).
export function ScamWarning({ check, className }: { check: ScamCheck; className?: string }) {
  const high = check.risk === "high";
  return (
    <div role="alert" className={cx("rounded-lg px-4 py-3 text-[13px] leading-relaxed", high ? "bg-bad-soft" : "bg-warn-soft", className)}>
      <div className={cx("flex items-center gap-2 font-semibold", high ? "text-bad" : "text-warn")}>
        <ShieldAlert size={15} className="shrink-0" />
        {high ? "This posting shows scam warning signs" : "Worth double-checking this posting"}
      </div>
      <ul className="mt-2 space-y-1.5 text-fg">
        {check.flags.map((f) => (
          <li key={f.code}>
            <span className="font-medium">{f.label}</span>
            <span className="text-muted"> — &ldquo;{f.evidence}&rdquo;</span>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-muted">{check.advice}</p>
    </div>
  );
}
