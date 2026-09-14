import { Code2, TriangleAlert } from "lucide-react";
import type { SkillGapResult } from "@/lib/types";

function SkillPill({ skill, tone }: { skill: string; tone: "matched" | "weak" | "missing" }) {
  const classes = {
    matched: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-600/20",
    weak: "bg-amber-50 text-amber-700 ring-1 ring-amber-600/20",
    missing: "bg-rose-50 text-rose-700 ring-1 ring-rose-600/20",
  }[tone];
  const dot = { matched: "bg-emerald-500", weak: "bg-amber-500", missing: "bg-rose-500" }[tone];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${classes}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
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

  return (
    <div className="card-shadow rounded-2xl border border-slate-200 bg-white p-5">
      {skillGapNote && (
        <div className="mb-4 flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-sm font-medium text-amber-800">
          <TriangleAlert size={16} className="mt-0.5 shrink-0" strokeWidth={2.25} />
          {skillGapNote}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {skillGap.matched.map((s) => (
          <SkillPill key={`m-${s}`} skill={s} tone="matched" />
        ))}
        {skillGap.weak.map((s) => (
          <SkillPill key={`w-${s}`} skill={s} tone="weak" />
        ))}
        {skillGap.missing.map((s) => (
          <SkillPill key={`x-${s}`} skill={s} tone="missing" />
        ))}
        {skillGap.matched.length + skillGap.weak.length + skillGap.missing.length === 0 && (
          <span className="text-sm text-slate-400">No skills to compare.</span>
        )}
      </div>

      {skillGap.github_unavailable && (
        <p className="mt-3 flex items-center gap-1.5 text-xs text-slate-400">
          <Code2 size={13} /> GitHub evidence lookup was unavailable this run — not the same as "checked, found
          nothing."
        </p>
      )}

      {hasEvidence && (
        <div className="mt-4 border-t border-slate-100 pt-4">
          <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
            <Code2 size={13} /> GitHub evidence
          </div>
          <ul className="mt-1.5 space-y-1">
            {Object.entries(skillGap.github_evidence).map(([skill, repos]) => (
              <li key={skill} className="text-sm text-slate-600">
                <span className="font-medium text-slate-800">{skill}:</span> {repos.join(", ")}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
