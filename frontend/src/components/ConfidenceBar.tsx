export function ConfidenceBar({ confidence }: { confidence: number }) {
  const pct = Math.round(Math.max(0, Math.min(1, confidence)) * 100);
  const color = pct >= 75 ? "bg-ok" : pct >= 40 ? "bg-warn" : "bg-bad";

  return (
    <div className="flex items-center gap-2" title={`Confidence: ${pct}%`}>
      <div className="flex gap-[3px]" aria-hidden>
        {[0, 1, 2, 3, 4].map((i) => (
          <span key={i} className={`h-2.5 w-1 rounded-full ${pct > i * 20 ? color : "bg-line-strong"}`} />
        ))}
      </div>
      <span className="text-xs tabular-nums text-subtle">{pct}% confidence</span>
    </div>
  );
}
