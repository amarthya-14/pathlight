export function ConfidenceBar({ confidence }: { confidence: number }) {
  const pct = Math.round(Math.max(0, Math.min(1, confidence)) * 100);
  const color = pct >= 75 ? "from-emerald-400 to-teal-400" : pct >= 40 ? "from-amber-400 to-orange-400" : "from-rose-400 to-pink-500";

  return (
    <div className="flex items-center gap-2.5" title={`Confidence: ${pct}%`}>
      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-surface-2">
        <div
          className={`h-full rounded-full bg-gradient-to-r ${color} transition-[width] duration-700 ease-out`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs font-medium tabular-nums text-muted">{pct}% confidence</span>
    </div>
  );
}
