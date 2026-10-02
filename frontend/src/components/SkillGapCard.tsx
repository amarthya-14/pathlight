import { Code2, ScanSearch, TriangleAlert } from "lucide-react";
import type { SkillGapResult } from "@/lib/types";
import { Card } from "./ui";

type Tone = "matched" | "weak" | "missing";

const TONE = {
  matched: { pill: "bg-ok-soft text-ok ring-ok/20", dot: "bg-ok", label: "Matched" },
  weak: { pill: "bg-warn-soft text-warn ring-warn/20", dot: "bg-warn", label: "Weak" },
  missing: { pill: "bg-bad-soft text-bad ring-bad/20", dot: "bg-bad", label: "Missing" },
} as const;

function SkillPill({ skill, tone }: { skill: string; tone: Tone }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ring-1 ${TONE[tone].pill}`}>
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
export function SkillGapCard({
  skillGap,
  skillGapNote,
}: {
  skillGap: SkillGapResult;
  skillGapNote?: string | null;
}) {
  const hasEvidence = Object.keys(skillGap.github_evidence).length > 0;
  const total = skillGap.matched.length + skillGap.weak.length + skillGap.missing.length;
  const coverage = total === 0 ? 0 : Math.round(((skillGap.matched.length + skillGap.weak.length * 0.5) / total) * 100);

  return (
    <Card className="h-full p-5 sm:p-6">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-soft text-accent-fg">
            <ScanSearch size={19} />
          </span>
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-subtle">Skill gap</div>
            <div className="text-base font-semibold text-fg">
              {total === 0 ? "—" : `${skillGap.matched.length} of ${total} skills matched`}
            </div>
          </div>
        </div>
        {total > 0 && <div className="text-right text-2xl font-semibold tabular-nums text-fg">{coverage}%</div>}
      </div>

      {total > 0 && (
        <div className="mt-4 flex h-2 overflow-hidden rounded-full bg-surface-2">
          <div className="bg-ok transition-all duration-700" style={{ width: `${(skillGap.matched.length / total) * 100}%` }} />
          <div className="bg-warn transition-all duration-700" style={{ width: `${(skillGap.weak.length / total) * 100}%` }} />
          <div className="bg-bad/70 transition-all duration-700" style={{ width: `${(skillGap.missing.length / total) * 100}%` }} />
        </div>
      )}

      {skillGapNote && (
        <div className="mt-4 flex items-start gap-2.5 rounded-xl bg-warn-soft px-3.5 py-2.5 text-sm font-medium text-warn">
          <TriangleAlert size={16} className="mt-0.5 shrink-0" strokeWidth={2.25} />
          {skillGapNote}
        </div>
      )}

      <div className="mt-5 flex flex-wrap gap-2">
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

      {total > 0 && (
        <div className="mt-4 flex flex-wrap gap-4 text-[11px] text-subtle">
          {(Object.keys(TONE) as Tone[]).map((t) => (
            <span key={t} className="inline-flex items-center gap-1.5">
              <span className={`h-1.5 w-1.5 rounded-full ${TONE[t].dot}`} /> {TONE[t].label}
            </span>
          ))}
        </div>
      )}

      {skillGap.github_unavailable && (
        <p className="mt-4 flex items-center gap-1.5 text-xs text-subtle">
          <Code2 size={13} /> GitHub evidence lookup was unavailable this run — not the same as &quot;checked, found
          nothing.&quot;
        </p>
      )}

      {hasEvidence && (
        <div className="mt-5 border-t border-line pt-4">
          <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-subtle">
            <Code2 size={13} /> GitHub evidence
          </div>
          <ul className="mt-2 space-y-1.5">
            {Object.entries(skillGap.github_evidence).map(([skill, repos]) => (
              <li key={skill} className="text-sm text-muted">
                <span className="font-medium text-fg">{skill}:</span> {repos.join(", ")}
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}
