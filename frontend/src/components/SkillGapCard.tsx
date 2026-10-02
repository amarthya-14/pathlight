import { Code2, TriangleAlert } from "lucide-react";
import type { SkillGapResult } from "@/lib/types";
import { Card } from "./ui";

type Tone = "matched" | "weak" | "missing";

const TONE = {
  matched: { pill: "border-ok/25 bg-ok-soft text-ok", dot: "bg-ok", label: "Matched" },
  weak: { pill: "border-warn/25 bg-warn-soft text-warn", dot: "bg-warn", label: "Weak" },
  missing: { pill: "border-line-strong bg-surface text-muted", dot: "bg-bad", label: "Missing" },
} as const;

function SkillPill({ skill, tone }: { skill: string; tone: Tone }) {
  return (
    <span className={`inline-flex h-6 items-center gap-1.5 rounded-md border px-2 text-xs font-medium ${TONE[tone].pill}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${TONE[tone].dot}`} />
      {skill}
    </span>
  );
}

/**
 * Renders a SkillGapResult's matched/weak/missing breakdown plus GitHub evidence.
 * `skillGapNote` (e.g. "no resume on file") is rendered ABOVE the results, prominently,
 * whenever present — a stated non-negotiable rule in docs/AI_DESIGN.md: don't let a
 * resume-less skill gap silently present as if it were real evidence.
 */
export function SkillGapCard({ skillGap, skillGapNote }: { skillGap: SkillGapResult; skillGapNote?: string | null }) {
  const hasEvidence = Object.keys(skillGap.github_evidence).length > 0;
  const total = skillGap.matched.length + skillGap.weak.length + skillGap.missing.length;

  return (
    <Card className="h-full p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[13px] text-subtle">Skill match</div>
          <div className="mt-1 text-sm font-semibold text-fg">
            {total === 0 ? "—" : `${skillGap.matched.length} of ${total} skills on your resume`}
          </div>
        </div>
        {total > 0 && (
          <div className="flex gap-3 text-[11px] text-subtle">
            {(Object.keys(TONE) as Tone[]).map((t) => (
              <span key={t} className="inline-flex items-center gap-1">
                <span className={`h-1.5 w-1.5 rounded-full ${TONE[t].dot}`} /> {TONE[t].label}
              </span>
            ))}
          </div>
        )}
      </div>

      {total > 0 && (
        <div className="mt-4 flex h-1.5 gap-0.5 overflow-hidden rounded-full">
          {skillGap.matched.length > 0 && <div className="bg-ok" style={{ flex: skillGap.matched.length }} />}
          {skillGap.weak.length > 0 && <div className="bg-warn" style={{ flex: skillGap.weak.length }} />}
          {skillGap.missing.length > 0 && <div className="bg-bad/70" style={{ flex: skillGap.missing.length }} />}
        </div>
      )}

      {skillGapNote && (
        <div className="mt-4 flex items-start gap-2 rounded-lg bg-warn-soft px-3 py-2.5 text-[13px] text-warn">
          <TriangleAlert size={14} className="mt-[2px] shrink-0" strokeWidth={2.2} />
          {skillGapNote}
        </div>
      )}

      <div className="mt-4 flex flex-wrap gap-1.5">
        {skillGap.matched.map((s) => (
          <SkillPill key={`m-${s}`} skill={s} tone="matched" />
        ))}
        {skillGap.weak.map((s) => (
          <SkillPill key={`w-${s}`} skill={s} tone="weak" />
        ))}
        {skillGap.missing.map((s) => (
          <SkillPill key={`x-${s}`} skill={s} tone="missing" />
        ))}
        {total === 0 && <span className="text-sm text-subtle">No skills to compare.</span>}
      </div>

      {skillGap.github_unavailable && (
        <p className="mt-4 flex items-center gap-1.5 text-xs text-subtle">
          <Code2 size={13} /> GitHub evidence lookup was unavailable this run — not the same as &quot;checked, found
          nothing.&quot;
        </p>
      )}

      {hasEvidence && (
        <div className="mt-4 border-t border-line pt-4">
          <div className="flex items-center gap-1.5 text-xs font-medium text-subtle">
            <Code2 size={13} /> GitHub evidence
          </div>
          <ul className="mt-1.5 space-y-1">
            {Object.entries(skillGap.github_evidence).map(([skill, repos]) => (
              <li key={skill} className="text-[13px] text-muted">
                <span className="font-medium text-fg">{skill}:</span> {repos.join(", ")}
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}
