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
          <li key={i} className="relative flex gap-4 pb-6 last:pb-0">
            {i < events.length - 1 && <span className="absolute left-[7px] top-5 h-full w-px bg-line" />}
            <span className="relative mt-1 flex h-[15px] w-[15px] shrink-0 items-center justify-center">
              {latest && <span className="absolute inset-0 animate-ping rounded-full bg-accent/40" />}
              <span
                className={`relative h-[15px] w-[15px] rounded-full border-[3px] border-bg-elevated ${DOT[meta?.tone ?? "neutral"]} ${
                  latest ? "ring-2 ring-accent/40" : ""
                }`}
              />
            </span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-baseline gap-x-2">
                <span className={`text-sm font-semibold ${latest ? "text-fg" : "text-muted"}`}>{meta?.label ?? event.stage}</span>
                <span className="text-xs text-subtle">
                  {new Date(event.created_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}
                </span>
              </div>
              {event.note && <div className="mt-1 text-sm leading-relaxed text-muted">{event.note}</div>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
