import type { ApplicationStage, ApplicationStatusEvent } from "@/lib/types";
import { STAGE_META } from "@/lib/stages";

const DOT: Record<string, string> = {
  neutral: "bg-subtle",
  accent: "bg-accent",
  info: "bg-info",
  ok: "bg-ok",
  warn: "bg-warn",
  bad: "bg-bad",
};

export function StatusTimeline({ history }: { history: ApplicationStatusEvent[] }) {
  if (history.length === 0) {
    return <p className="text-sm text-subtle">No status history yet.</p>;
  }

  // Newest first — what happened most recently is what you came to see.
  const events = [...history].reverse();

  return (
    <ol className="relative">
      {events.map((event, i) => {
        const meta = STAGE_META[event.stage as ApplicationStage];
        const latest = i === 0;
        return (
          <li key={i} className="relative flex gap-3.5 pb-5 last:pb-0">
            {i < events.length - 1 && <span className="absolute left-[4.5px] top-4 h-full w-px bg-line" />}
            <span
              className={`relative mt-[5px] h-[10px] w-[10px] shrink-0 rounded-full ring-4 ring-surface ${DOT[meta?.tone ?? "neutral"]} ${
                latest ? "" : "opacity-60"
              }`}
            />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                <span className={`text-[13px] font-medium ${latest ? "text-fg" : "text-muted"}`}>{meta?.label ?? event.stage}</span>
                <span className="text-xs tabular-nums text-subtle">
                  {new Date(event.created_at).toLocaleString(undefined, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" })}
                </span>
              </div>
              {event.note && <div className="mt-0.5 text-[13px] leading-relaxed text-muted">{event.note}</div>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
